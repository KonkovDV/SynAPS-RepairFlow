# SynAPS RepairFlow — skeleton MVP

Статус документа: проектная спецификация, не утверждение промышленной готовности.

## 1. Решение

**SynAPS RepairFlow** — доменный адаптер над ядром SynAPS для проверяемого планирования ремонта узлов и агрегатов городского транспорта.

Формула MVP:

> Исторический или синтетический набор ремонтных заказов → допустимый альтернативный график → независимая проверка → объяснимый отчёт и сравнение с baseline.

RepairFlow не управляет выпуском транспорта, движением, оборудованием или закупками. Он работает в offline/shadow-режиме и выдаёт рекомендацию специалисту.

## 2. Что взять из четырёх проектов

| Источник | Урок, который переносим |
|---|---|
| **SynAPS** | deterministic-first portfolio; точное решение только там, где есть доказательство; отдельные solver status и claim level; фиксированный seed; JSON-контракты; benchmark/evidence harness. |
| **MobiRoute** | разделение домена и ядра; ingest → plan → diff → operator; day-ahead и shadow-mode; frozen assignments; reason codes; fallback/degraded mode; не смешивать FJSP и DARP. |
| **GridPlan** | бригады, окна, ЗИП, заморозка, SDST, auxiliary resources, аварийный локальный ремонт, provenance, строгий data contract и пилотный gate. |
| **SignPlan** | тонкий доменный пакет без fork ядра; полный SHA-пин; fail-closed checker; exit 0/2/1; намеренно плохой сценарий; статический Gantt/showcase; Python first, Rust только после измерения. |

## 3. SOTA-позиционирование

Класс задачи известен: FJSP/RCPSP с зависящими от последовательности переналадками, дополнительными ресурсами, календарями и ограничениями квалификаций. Нельзя заявлять «уникальную математику» или «первый в мире оптимизатор». Защищаемая новизна MVP:

1. открытый доменный контракт для транспортного ремонта;
2. воспроизводимое построение графика;
3. независимое доказательство соблюдения hard constraints;
4. явные причины невозможности назначения;
5. replay/shadow-процесс поверх существующих систем, без vendor lock-in.

Научные ориентиры: worker-constrained FJSP-SDST — https://doi.org/10.1007/s00291-018-0537-z; multi-resource CP/ALNS — https://doi.org/10.1016/j.ejor.2024.08.010; exact LBBD для конфликтного транспортного FJSP — https://doi.org/10.1016/j.cor.2025.107342.

В MVP не нужны новая эвристика, нейросеть, RL, GPU, прогноз отказов и полноценная многокритериальная оптимизация. Нужны корректная модель, checker и воспроизводимый эксперимент.

## 4. Границы MVP

### Входит

- один ремонтный участок или один тип ремонтного контура;
- 20–100 работ в демонстрации, с рабочей точкой 30–50;
- операции с длительностью и предшественниками;
- цепочка и небольшие DAG техкарты; неподдержанный DAG запрещается, а не молча линеаризуется;
- альтернативные посты/центры;
- бригады и квалификации;
- оснастка и дополнительные ресурсы;
- матрица переналадок/переходов SDST;
- сменные календари и окна работ;
- сроки готовности и штраф за опоздание;
- замороженные назначения/окна;
- ограниченный контур ЗИП: наличие, release time или блокирующая потребность;
- baseline FIFO и простой ручной/исторический план;
- GREED для быстрого допустимого решения;
- CP-SAT на малых и средних экземплярах;
- RHC-GREEDY-COVER для расширенного горизонта;
- ALNS только как дополнительный quality lane;
- независимый checker;
- diff двух планов;
- JSON/CSV input, JSON result, Markdown и статический HTML-отчёт с Gantt;
- синтетический генератор и намеренно испорченный сценарий.

### Не входит

- управление движением и выпуском;
- SCADA, EMS, GIS, EAM/ERP и CMMS-интеграция;
- закупки, складская оптимизация и полное управление ЗИП;
- прогноз отказов, PdM/CBM и диагностика состояния;
- зарядка электробусов и энергетическая оптимизация;
- маршрутизация по дорожной сети;
- сертификация трудовых графиков и соблюдения ТК РФ;
- доказательство промышленного эффекта в рублях;
- online dispatch и автоматическая запись в рабочую систему;
- multi-tenant, HA/DR, SLA и production support.

## 5. Архитектура

```text
repairflow/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CITATION.cff
├── SECURITY.md
├── requirements-lock.txt
├── src/repairflow/
│   ├── __init__.py
│   ├── versions.py          # RepairFlow version + full SynAPS SHA
│   ├── model.py             # Pydantic domain contract
│   ├── limits.py            # explicit anti-abuse and MVP limits
│   ├── normalize.py         # CSV/JSON → canonical UTC model
│   ├── adapter.py           # RepairFlow → SynAPS instance
│   ├── planner.py           # baseline / GREED / CP-SAT / RHC routing
│   ├── checker.py           # independent fail-closed checker
│   ├── diff.py              # plan-to-plan and frozen-change diff
│   ├── reasons.py           # stable human-readable reason codes
│   ├── evidence.py          # hashes, configs, provenance, bundle
│   ├── report.py            # Markdown + static HTML/Gantt
│   ├── synthetic.py         # depot/repair fixture generator
│   └── cli.py               # synthesize / solve / check / compare / report / version
├── schemas/
│   ├── repairflow.problem.v1.json
│   ├── repairflow.result.v1.json
│   ├── repairflow.diff.v1.json
│   └── examples/
│       ├── tiny_repair.json
│       ├── repair_site_mvp.json
│       └── broken_seed42.json
├── benchmark/
│   ├── run_mvp.py
│   ├── compare_baselines.py
│   ├── scenarios/disruption.json
│   └── results/.gitkeep
├── tests/
│   ├── test_contract.py
│   ├── test_checker_adversarial.py
│   ├── test_frozen_assignments.py
│   ├── test_dag_and_setup.py
│   ├── test_baselines.py
│   ├── test_determinism.py
│   ├── test_diff.py
│   ├── test_broken_demo.py
│   └── test_evidence_bundle.py
└── docs/
    ├── MVP.md
    ├── domain-assumptions.md
    ├── data-request.md
    ├── pilot-protocol.md
    ├── limitations.md
    ├── benchmark-protocol.md
    └── jury-demo.md
```

`repairflow` не копирует `synaps/` и не создаёт отдельный fork ядра. Зависимость фиксируется полным SHA. Для стартовой сборки можно использовать проверенный pin SynAPS:

```toml
synaps = { git = "https://github.com/KonkovDV/SynAPS.git", rev = "6178c93b705ff58be21fa74a98651883a2da1169" }
```

Перед каждым обновлением pin обязательны pin-regression, schema tests и recapture evidence. Ветка `main` в зависимости не допускается.

## 6. Каноническая модель RepairFlow

### Problem v1

```json
{
  "schema_version": "repairflow.problem.v1",
  "instance_id": "repair-site-mvp",
  "data_provenance": "synthetic",
  "planning_horizon": {"start": "2026-01-12T00:00:00Z", "end": "2026-01-19T00:00:00Z"},
  "jobs": [],
  "operations": [],
  "work_centers": [],
  "crews": [],
  "aux_resources": [],
  "setup_matrix": [],
  "calendars": [],
  "frozen_assignments": [],
  "spares": [],
  "policy": {
    "unknown_fields": "reject",
    "missing_setup": "reject",
    "unsupported_dag": "reject",
    "allow_partial_plan": false
  }
}
```

### Минимальные сущности

- `Job`: ремонтный заказ, актив, тип узла, due date, приоритет.
- `Operation`: операция, длительность, predecessors, alternatives, required skills, required aux.
- `WorkCenter`: пост/участок/стенд, календарь, capacity.
- `Crew`: бригада, skills, календарь, capacity.
- `AuxResource`: оснастка, кран, стенд, контрольное оборудование, capacity.
- `SetupEntry`: переход `from_state → to_state`, duration, required resources.
- `FrozenAssignment`: операция, пост, старт, окончание; нарушение запрещено.
- `SpareRequirement`: артикул, количество, release/available time. В MVP это блокировка, не оптимизация запасов.
- `Evidence`: input hash, config hash, solver status, kernel SHA, checker version, claim level.

Все даты — timezone-aware ISO-8601. Локальное время и Unix timestamps запрещены. Все cross-reference ошибки должны выявляться до запуска solver.

## 7. Статусы и fail-closed политика

### Результат

```text
OPTIMAL                 # только exact solver + доказательство bound + checker clean
FEASIBLE                # допустимый план, оптимальность не доказана
HEURISTIC_FEASIBLE      # допустимый план эвристики
PARTIAL                 # не все операции покрыты; не выдавать как допустимый план
INFEASIBLE              # доказана невозможность для заданной модели
NOT_VERIFIED            # checker не смог подтвердить; запрещено принимать
MANUAL_REVIEW_REQUIRED  # неполная модель/неизвестное ограничение
ERROR
```

### Процессные коды CLI

- `0`: checker пуст, полное покрытие, solver status явно известен и допустим;
- `2`: план создан, но есть нарушение, неполное покрытие или неизвестное ограничение;
- `1`: ошибка входа, отсутствует обязательное поле или системная ошибка.

Нельзя превращать `PARTIAL`, `UNKNOWN`, пропущенный `kernel_status` или неполную матрицу setup в зелёный результат.

### Обязательные hard checks

1. coverage: каждая операция назначена ровно один раз или явно отклонена с причиной;
2. precedence: ни одна операция не начинается до предшественников;
3. work-center overlap и capacity;
4. crew overlap и квалификация;
5. auxiliary-resource overlap, включая интервалы setup;
6. календарь и рабочее окно;
7. due/release semantics;
8. frozen assignments не сдвинуты;
9. setup duration совпадает с матрицей;
10. все ID и ссылки существуют;
11. ЗИП не используется до release/availability;
12. unsupported DAG и неизвестные ограничения не пропускаются.

### Reason codes v1

`MISSING_SETUP`, `CREW_OVERLAP`, `AUX_OVERLAP`, `SKILL_MISMATCH`, `CENTER_OVERLAP`, `PRECEDENCE_BROKEN`, `WINDOW_BROKEN`, `DUE_MISSED`, `FROZEN_MOVED`, `SPARE_UNAVAILABLE`, `UNKNOWN_OPERATION`, `UNKNOWN_RESOURCE`, `DAG_UNSUPPORTED`, `PARTIAL_COVERAGE`, `KERNEL_STATUS_MISSING`.

Каждая ошибка содержит `code`, `job_id`, `operation_id`, `resource_id`, `start`, `end`, `message` и `suggested_relaxation`, если её можно вычислить. В MVP не обещать MUS/IIS; поле может быть `null`.

## 8. Solver policy

| Сценарий | Метод | Что говорить |
|---|---|---|
| baseline | FIFO / historical replay | контрольное сравнение |
| маленький toy case | CP-SAT strict | OPTIMAL только при bound + checker |
| обычный MVP | GREED / constructive | HEURISTIC_FEASIBLE или FEASIBLE после checker |
| большой горизонт | RHC-GREEDY-COVER | coverage/feasible, не optimality |
| улучшение качества | ALNS | quality lane; не гарантия покрытия |
| изменение условий | IncrementalRepair/RHC | diff и сохранение frozen |

Не добавлять новый solver ради заявки. Сначала доказать корректность адаптера и checker.

## 9. CLI MVP

```bash
repairflow version
repairflow synthesize --preset repair-site-mvp --out data/repair-site-mvp.json
repairflow solve data/repair-site-mvp.json --preset GREED --out out/greed.json
repairflow solve data/repair-site-mvp.json --preset CPSAT-30 --out out/cpsat.json
repairflow check data/repair-site-mvp.json out/greed.json --report out/greed.check.json
repairflow compare data/repair-site-mvp.json out/fifo.json out/greed.json --out out/compare.json
repairflow report data/repair-site-mvp.json out/greed.json --html out/report.html
repairflow demo --preset broken-seed42
```

`demo` обязан показать два результата:

1. чистый прогон: полный план, `verified_feasible=true`, exit 0;
2. преднамеренно испорченный план: конкретная ошибка, `verified_feasible=false`, exit 2.

## 10. Критерии готовности MVP

MVP считается готовым только если:

- один синтетический ремонтный участок воспроизводится одной командой;
- есть JSON Schema и Pydantic validation;
- fixed seed выдаёт одинаковый input hash и result hash;
- FIFO и GREED сравниваются на одном и том же входе;
- CP-SAT показывает exact result только на bounded toy case;
- checker не зависит от статуса solver и ловит намеренно испорченные планы;
- missing setup, unknown skill, overlap, broken precedence и moved frozen assignment дают exit 2;
- Gantt показывает job/operation/work center/crew и выделяет нарушения;
- result содержит version, kernel SHA, config hash, input hash, provenance, claim level;
- данные и ограничения разделены: синтетика не называется клиентским пилотом;
- README собирается на чистой машине;
- CI запускает lint, type check, unit/property/adversarial tests, pin check и schema check.

## 11. Демо для жюри

1. Ввод: 30–50 ремонтных работ, 4 поста, 3 бригады, оснастка, сроки, setup и один frozen job.
2. FIFO: несколько hard violations или неудовлетворительный baseline.
3. GREED: допустимый кандидат-график с отчётом checker.
4. CP-SAT: небольшой срез с доказанным optimum.
5. Сбой: недоступен пост или задержана деталь.
6. RepairFlow: локальное перепланирование, frozen job не сдвинут.
7. Проверка: зелёный отчёт, затем намеренно плохой input и красный exit 2.
8. Объяснение: не «ИИ решил», а «вот ограничения, назначения, доказательство допустимости и решение специалиста».

## 12. План работ на 14 дней

### Дни 1–2 — контракт

- зафиксировать pin SynAPS;
- определить `repairflow.problem.v1` и `result.v1`;
- описать domain assumptions и non-claims;
- запретить неявную линеаризацию DAG.

### Дни 3–5 — адаптер и синтетика

- Job/Operation/WorkCenter/Crew/Aux/Setup/Calendar;
- генератор repair-site-mvp;
- CSV/JSON import;
- FIFO baseline;
- сборка маленького CP-SAT примера.

### Дни 6–8 — checker

- coverage, precedence, overlaps, skills, calendars;
- setup на occupancy interval;
- frozen assignments;
- reason codes и exit 0/2/1;
- adversarial broken seed.

### Дни 9–10 — сравнение и diff

- GREED vs FIFO;
- bounded CP-SAT evidence;
- disruption scenario;
- сохранение hash/config/provenance;
- plan diff.

### Дни 11–12 — отчёт

- Markdown report;
- статический HTML/Gantt;
- красный/зелёный экран;
- короткий скринкаст.

### Дни 13–14 — red-team

- проверить неполные setup, неизвестные ID, ветвящийся DAG, пропущенный kernel status;
- убрать неподтверждённые KPI;
- зафиксировать limits;
- прогнать чистую установку и собрать evidence bundle.

## 13. Что отложить после MVP

1. полноценный DAG solver path, если базовый kernel не покрывает ветвления;
2. minimal relaxation/MUS/IIS для объяснения infeasibility;
3. actual inventory and procurement constraints;
4. multi-site and cross-depot planning;
5. planner UI с ручным approve/reject;
6. EAM/1C/ERP adapters;
7. durable jobs, audit log, authentication;
8. uncertainty, robust/CVaR and maintenance under failures;
9. Rust checker only after profiler and parity tests;
10. customer holdout and KPI study.

## 14. Красные линии

- не писать «внедрено», «используется Дептрансом» или «сокращает ремонт на X%» без customer evidence;
- не писать «оптимально» для GREED/ALNS/RHC;
- не называть синтетическую фикстуру данными СВАРЗ;
- не заявлять замену EAM, CMMS, диспетчеризации или системы выпуска;
- не принимать неполный план за допустимый;
- не добавлять LLM в контур принятия решений ради модного позиционирования;
- не форкать SynAPS и не дублировать solver/checker без измеренной причины.
