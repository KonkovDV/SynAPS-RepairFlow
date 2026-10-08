# SynAPS RepairFlow

> **Проверяемое планирование ремонта городского транспорта: offline, воспроизводимо, fail-closed.**

[![CI](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/workflows/ci.yml) [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# Русская версия

## Кратко для жюри

SynAPS RepairFlow — исследовательский доменный адаптер и независимый checker для планирования ремонта. Он описывает задания, операции, посты, бригады, навыки, инструменты, sequence-dependent setup, календари, замороженные назначения, запчасти и обменный фонд. Система строит кандидатный план, а затем независимо проверяет его по объявленным ограничениям.

**Допустимое утверждение:** для формального экземпляра RepairFlow строит кандидатный график и независимо сообщает, выполнены ли заявленные жёсткие ограничения, либо возвращает структурированные причины нарушения.

Это лабораторный и shadow-mode инструмент. Это не диспетчеризация, не EAM/ERP/CMMS, не контур безопасности, не управление выпуском транспорта и не автономное решение «AI всё решил».

### Что подтверждает текущая версия

- схема отклоняет неполные и неоднозначные входы;
- checker отделён от solver search path;
- capacity моделируется как `K` взаимозаменяемых half-open lanes `[start, end)`;
- в одной точке времени `end` обрабатывается раньше `start`;
- setup входит в occupancy, когда это требует контракт;
- `due_date` отделён от жёсткого `deadline`;
- проверяются precedence, crews, skills, calendars, auxiliary resources, spares и frozen assignments;
- вход, конфигурация, результат и pin ядра участвуют в evidence-пути;
- для sweep-line есть adversarial и property-based тесты против независимого brute-force oracle.

### Чего проект не подтверждает

Нет утверждений о промышленных KPI, экономии, customer accuracy, production readiness, сертификации безопасности, оптимальности эвристик, действующем заказчике, спонсоре или deployment на SVARZ/Mosgortrans. Публичные источники не превращаются в customer claim.

## Зафиксированная граница доказательств

<!-- evidence:begin -->
| Факт | Значение |
|---|---|
| Проверенный `main` | [`6f34389`](https://github.com/KonkovDV/SynAPS-RepairFlow/commit/6f34389b041a5cdc3402c5a94f9e62cb1ced17ac) |
| CI для этого `main` | [Actions run 37831512163](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/37831512163), success, включая `test-slow` |
| Sweep-line commit | [`a3621fd`](https://github.com/KonkovDV/SynAPS-RepairFlow/commit/a3621fd538019f4dcc0c681d5634c022260382e9) |
| SynAPS pin | [`f939727`](https://github.com/KonkovDV/SynAPS/commit/f939727cd9369fd9b36438bfac7198f0c39c6d3b) |
| Solver | `ortools==9.15.6755` |
| Benchmark | [`benchmark/results/benchmark.json`](benchmark/results/benchmark.json), SHA-256 `c1a604c70ee6a8e99e52ecb9ac59341fabdf7c1a8771cdccf3dc836c605a2186`, claim `experiment` |
| Fault campaign | checked 10080, false_accept 0, false_reject 0, presets `tiny, repair-site-mvp`, solvers `GREED, EDD, ATC` |
| Манифест отстаёт от HEAD | да |
| Данные | committed synthetic fixtures; customer data отсутствуют |
| Зрелость | laboratory fixture / TRL 4; не pilot result |
<!-- evidence:end -->

Число без commit, provenance, seed, solver status, checker output и denominator не является доказательством.

## Быстрый воспроизводимый прогон

Версия Python задана полем `requires-python` в [`pyproject.toml`](pyproject.toml).

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\\Scripts\\activate
python -m pip install -e ".[dev]"
repairflow version
repairflow demo --out out
repairflow benchmark --out bench
```

Для проверки качества:

```bash
python tools/verify_schema.py
python tools/export_schemas.py
python -m ruff format --check src tests tools
python -m ruff check src tests tools
python -m mypy --strict src/repairflow
python -m pytest -q -m "not slow"
```

Demo использует только synthetic data, проверяет чистый и намеренно сломанный план и должен сохранять fail-closed поведение.

## Архитектура и safety boundary

```text
formal instance → schema/domain validation → candidate planner
               → independent checker → evidence bundle → human decision
```

Доменный checker не импортирует solver search code и проверяет нормализованный кандидат против исходного domain contract. Опубликованный вердикт дополнительно читает feasibility checker закреплённого SynAPS, поэтому независимость относится к поиску, а не ко всей экосистеме SynAPS. `repairflow verify-plan` этот контур не вызывает: чистый цеховой CSV получает claim `domain_verified`, а не `verified`. Сокращение makespan не считается улучшением, если потеряно покрытие или появился hard violation.

### Capacity oracle

Ресурс ёмкости `K` — это `K` взаимозаменяемых lanes. Интервал `[start, end)` означает, что касание endpoint не создаёт overlap. Setup расширяет occupancy назад. Тот же sweep-line применяется к обычным и frozen assignments. Это устраняет ошибку anchor-based pairwise counting, когда несинхронные визиты ошибочно объявляются одновременными.

### Evidence и false accept

Каждый результат должен иметь provenance (`synthetic`, `open_data`, `experiment` и т. д.), solver status, claim level и independent verification. `OPTIMAL` допускается только для bounded exact run с proven bound и пустым независимым checker. Эвристика не наследует слово `optimal`.

```text
false_accept_rate = invalid_plans_accepted_as_verified / invalid_plans_presented
```

Для correctness-oracle fixtures целевой показатель — ноль.

## Обзор работ, FTIM и OSINT

RepairFlow не выдаёт себя за новый general-purpose solver. Научно защищаемая позиция — корректность доменной семантики, независимая fail-closed проверка, provenance, reproducibility и controlled path к shadow pilot. Позиционирование и bibliography: [обзор работ](docs/literature-2026.md) и [протокол evidence](docs/evidence-protocol.md).

Публичный OSINT используется только для определения gate:

- [FTIM pilot programme](https://ftim.ru/pilotirovanie/) описывает проверку на инфраструктуре московского транспорта, измеримую гипотезу и ограниченный по сроку pilot;
- [официальный профиль SVARZ](https://www.mosgortrans.ru/about/branches/filial-sokolnicheskii-vagonoremontno-stroitelnyi-zavod-svarz-gup-mosgortrans/) подтверждает ремонт транспортных компонентов, но не sponsor и не текущий workflow RepairFlow;
- [Moscow Innovation Cluster](https://i.moscow/pilot) описывает readiness/right requirements; зрелость RepairFlow — строка таблицы evidence выше.

Первый пилот должен быть read-only/shadow: один contour, process owner, anonymised slice, baseline, holdout, operator accept/reject log, rollback и заранее определённые KPI. Ни один источник не доказывает sponsorship, savings, deployment или safety certification.

## RailBreak как documentation precedent

[`KonkovDV/RailBreak`](https://github.com/KonkovDV/RailBreak) изучен как пример jury-grade подачи: one-command demo, таблицы с commit/data/method/denominator, отдельные assumptions/results/TЗ audit/references, fault campaigns, degraded modes и раздел «что не покрыто». Его odometry numbers, ROS assumptions и transport claims не являются evidence для RepairFlow.

## Пределы и документация

В проекте нет write-back в EAM/ERP/CMMS, dispatch control, SCADA, safety function или customer data. Checker доказывает только явно объявленные ограничения. Подробная карта: [`docs/README.md`](docs/README.md), [`docs/traceability-matrix.md`](docs/traceability-matrix.md), [`docs/threat-model.md`](docs/threat-model.md), [`docs/osint-and-pilot-gates.md`](docs/osint-and-pilot-gates.md), [`SECURITY.md`](SECURITY.md), [`LICENSES.md`](LICENSES.md).

---

# English version

## Jury summary

SynAPS RepairFlow is a research-grade domain adapter and independent checker for repair-shop scheduling. It models jobs, operations, work centres, crews, skills, tooling, sequence-dependent setup, calendars, frozen assignments, spares and exchange-pool constraints. It builds candidate schedules and checks them independently against the declared hard constraints.

**Allowed claim:** given a formal repair instance, RepairFlow can construct a candidate schedule and independently report whether the declared hard constraints hold, or return structured reasons why they fail.

It is an offline laboratory and shadow-mode decision-support system. It is not dispatch control, an EAM/ERP/CMMS replacement, a safety controller, an autonomous AI decision maker, or proof of production readiness.

### Current evidence

- malformed and ambiguous inputs are rejected by the domain contract;
- the checker is outside the solver search path;
- capacity uses interchangeable half-open lanes `[start, end)`;
- equal-time ends are processed before starts;
- setup is included in occupancy where required;
- soft `due_date` is separated from hard `deadline`;
- precedence, crews, skills, calendars, auxiliary resources, spares and frozen assignments are explicit checker concerns;
- hashes, dependency pins and checker output are evidence fields;
- sweep-line semantics are tested with adversarial and property-based cases.

### Explicit non-claims

The repository does not prove industrial savings, customer accuracy, heuristic optimality, labour-law compliance, production deployment, safety certification, a live SVARZ/Mosgortrans customer relationship, or sponsorship inferred from public sources.

## Reproducible run

The required Python version is the `requires-python` field of [`pyproject.toml`](pyproject.toml).

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\\Scripts\\activate
python -m pip install -e ".[dev]"
repairflow version
repairflow demo --out out
repairflow benchmark --out bench
```

Quality gates:

```bash
python tools/verify_schema.py
python tools/export_schemas.py
python -m ruff format --check src tests tools
python -m ruff check src tests tools
python -m mypy --strict src/repairflow
python -m pytest -q -m "not slow"
```

The demo uses synthetic data, checks clean and intentionally broken plans, and must remain fail-closed.

## Trust boundary and semantics

```text
formal instance → schema/domain validation → candidate planner
               → independent checker → evidence bundle → human decision
```

The checker does not import solver search code. `repairflow verify-plan` does not call the kernel: a clean shop CSV is claim `domain_verified`, not `verified`. A shorter makespan is not an improvement when coverage is incomplete or a hard violation is introduced.

A resource with capacity `K` has `K` interchangeable lanes. Occupancy is half-open, `[start, end)`, so touching endpoints do not overlap. Setup extends occupancy backwards. The same sweep-line oracle is used for ordinary and frozen assignments. This avoids the anchor-based pairwise error that rejects staggered visits as simultaneous.

## Evidence and the literature review

Every result should state data provenance, solver status, claim level and independent verification. `OPTIMAL` is reserved for a bounded exact run with a proven bound and an empty independent checker. Heuristics never inherit `optimal`.

```text
false_accept_rate = invalid_plans_accepted_as_verified / invalid_plans_presented
```

The target for correctness-oracle fixtures is zero. RepairFlow does not claim a new general-purpose solver; its defensible position is explicit domain semantics, independent fail-closed verification, reproducibility, provenance and a controlled path to a shadow pilot. See the [literature review](docs/literature-2026.md) and the [evidence protocol](docs/evidence-protocol.md).

## FTIM / OSINT boundary

- [FTIM pilot programme](https://ftim.ru/pilotirovanie/) is used only for public pilot-gate framing.
- The [official SVARZ profile](https://www.mosgortrans.ru/about/branches/filial-sokolnicheskii-vagonoremontno-stroitelnyi-zavod-svarz-gup-mosgortrans/) establishes transport-component repair, not a RepairFlow sponsor or workflow.
- [Moscow Innovation Cluster](https://i.moscow/pilot) describes readiness and rights requirements; maturity is the value recorded in [`docs/evidence-manifest.json`](docs/evidence-manifest.json).

A first pilot must be read-only/shadow-only, limited to one contour, with an anonymised data slice, agreed baseline, holdout, operator decision log, rollback and pre-declared KPIs. These sources do not prove deployment, savings, sponsorship or certification.

## RailBreak comparison

The public [`KonkovDV/RailBreak`](https://github.com/KonkovDV/RailBreak) repository was used as a documentation precedent: one-command jury execution, evidence tables, assumptions/results/TЗ traceability, fault campaigns and explicit limitations. RailBreak measurements are not RepairFlow evidence.

## Reproducibility, limits and documentation

For every serious result record the repository commit, dependency lock, SynAPS pin, input/config/result hashes, solver class, seed, time limit, checker output, metric denominator, environment and CI run. The checker can only prove declared constraints. No EAM/ERP/CMMS write-back, dispatch, SCADA or safety function is included.

See [`docs/README.md`](docs/README.md), [`docs/traceability-matrix.md`](docs/traceability-matrix.md), [`docs/threat-model.md`](docs/threat-model.md), [`docs/osint-and-pilot-gates.md`](docs/osint-and-pilot-gates.md), [`SECURITY.md`](SECURITY.md) and [`LICENSES.md`](LICENSES.md).

The repository is MIT-licensed unless a file states otherwise. This README is a research and engineering description, not a customer contract, safety case, procurement commitment or production-readiness certificate.
