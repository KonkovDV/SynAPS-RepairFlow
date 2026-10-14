# SynAPS RepairFlow

> **Проверяемое планирование ремонта: offline, воспроизводимо, fail-closed.**

[![CI](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/workflows/ci.yml) [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Лабораторный доменный адаптер и независимый нотариус. Ядро ищет слоты. Этот репозиторий описывает ремонтную задачу и отдельно решает, можно ли назвать план проверенным.

# Русская версия

## Допустимое утверждение

Для формального экземпляра RepairFlow строит кандидатный график и независимо сообщает, выполнены ли заявленные жёсткие ограничения, либо возвращает структурированные причины.

Это shadow-режим. Человек принимает решение. Программа не диспетчеризует выпуск, не пишет в учётную систему и не подменяет контур безопасности.

## Как читать вердикт

| Слово | Когда оно честное |
| --- | --- |
| `verified` | Покрыты все операции, жёсткий нотариус пуст, статус ядра — `feasible` или `optimal`. |
| `domain_verified` | Цеховой CSV прошёл `repairflow verify-plan`. Ядро не вызывалось. `verified_feasible` остаётся ложным. |
| `optimal` | Точный прогон вернул `OPTIMAL` на исходной цепочке за один проход компилятора, и нотариус пуст. Эвристика это слово не наследует. |

Более короткий makespan не является улучшением, если потеряно покрытие или появилось жёсткое нарушение.

## Семейство репозиториев

Публичные репозитории [KonkovDV](https://github.com/KonkovDV) рядом с этим. Их отчёты не переносятся сюда.

| Репозиторий | Роль | Что RepairFlow оттуда не берёт |
| --- | --- | --- |
| [SynAPS](https://github.com/KonkovDV/SynAPS) | Ядро поиска слотов. Именованные конфигурации решателя, воспроизводимый прогон, свой контроль допустимости. | Код ядра. Здесь только пин из таблицы доказательств. |
| [SynAPS-GridPlan](https://github.com/KonkovDV/SynAPS-GridPlan) | Лабораторное планирование ТОиР энергооборудования. Поиск и проверка разведены. | Другой домен, другой пин, другие отчёты. |
| [SynAPS-ProgramPlan](https://github.com/KonkovDV/SynAPS-ProgramPlan) | Сводный план программы: расчёт и вторая проверка, журнал решений с хеш-цепочкой. | Журнал оператора здесь ещё контракт, не цепочка записей. |
| [SynAPS-MobiRoute](https://github.com/KonkovDV/SynAPS-MobiRoute) | Планирование перевозки по вызову. | Не ремонт и не этот нотариус. |
| [AeroBIM](https://github.com/KonkovDV/AeroBIM) | Находка несёт пункт и идентификатор. Флаг годности ставит детерминированный контур, не текст модели. | Строительная проверка. Оттуда взята форма вердикта: код, идентификаторы, интервал. |
| [RailBreak](https://github.com/KonkovDV/RailBreak) | Подача для жюри: один запуск, таблица с источником, явный список того, что не покрыто. | Измерения одометрии. |

Если этот текст расходится с [`docs/limitations.md`](docs/limitations.md) или с таблицей ниже, верны они.

## Зафиксированная граница доказательств

Таблица между маркерами собрана `tools/attest.py`. Проверка публичных страниц отвергает цифру вне неё. Слова «ноль» и «пусто» здесь — про цель оракула корректности, не про новый замер.

<!-- evidence:begin -->
| Факт | Значение |
|---|---|
| Проверенный `main` | [`04ad612`](https://github.com/KonkovDV/SynAPS-RepairFlow/commit/04ad612851f1c39c96457a77cea03c358072f9a5) |
| CI для этого `main` | [Actions run 38563996424](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/38563996424), success, включая `test-slow` |
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

## Воспроизведение

Версия Python — поле `requires-python` в [`pyproject.toml`](pyproject.toml).

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\\Scripts\\activate
python -m pip install -e ".[dev]"
repairflow version
repairflow demo --out out
repairflow benchmark --out bench
```

Проверка качества:

```bash
python tools/verify_schema.py
python tools/export_schemas.py
python -m ruff format --check src tests tools
python -m ruff check src tests tools
python -m mypy --strict src/repairflow
python -m pytest -q -m "not slow"
```

Демо использует только синтетические данные, проверяет чистый и намеренно сломанный план и обязано оставаться fail-closed.

## Контур

```text
formal instance → schema/domain validation → candidate planner
               → independent checker → evidence bundle → human decision
```

Нотариус не импортирует код поиска решателя. Опубликованный вердикт `verified` дополнительно читает проверку допустимости закреплённого SynAPS: независимость относится к поиску, не ко всей экосистеме ядра. `repairflow verify-plan` ядро не вызывает.

Ёмкость `K` — это `K` взаимозаменяемых полос. Интервал `[start, end)` : касание концов не есть пересечение. Наладка удлиняет занятость назад. В один момент окончание обрабатывается раньше начала. Тот же обход применяется к обычным и замороженным назначениям. Это убирает ошибку попарного якоря, когда сдвинутые визиты объявляют одновременными.

```text
false_accept_rate = invalid_plans_accepted_as_verified / invalid_plans_presented
```

Для фикстур оракула корректности цель — ноль принятых неверных планов. Оракул минут не судит обменный фонд. Расхождение оракула и нотариуса разбирается вручную, оракул под нотариус не подгоняется.

## Что нотариус проверяет

Схема отвергает неполный и неоднозначный вход. Дальше проверяются покрытие, предшествование с лагами, посты, бригады, навыки, календари, оснастка, наладка, запчасти, обменный фонд, замороженные назначения и отделение мягкого срока от жёсткого.

Позиция относительно опубликованных работ — в [обзоре](docs/literature-2026.md) и [протоколе доказательств](docs/evidence-protocol.md). RepairFlow не объявляет себя новым универсальным решателем.

## Что не покрыто

Нет записи в учётную систему, диспетчеризации, SCADA и функции безопасности. Нет утверждения о промышленном эффекте, действующем заказчике, спонсорстве или сертификации. Публичные страницы [программы пилотов](https://ftim.ru/pilotirovanie/), [профиля завода](https://www.mosgortrans.ru/about/branches/filial-sokolnicheskii-vagonoremontno-stroitelnyi-zavod-svarz-gup-mosgortrans/) и [кластера](https://i.moscow/pilot) задают ворота входа, а не факт внедрения.

Маршрутные варианты не смоделированы. Журнал оператора — контракт без писателя. Нативная точная модель не начата: её открывает решение владельца, не этот README. Полный список — [`docs/limitations.md`](docs/limitations.md).

Первый пилот, если он будет, остаётся теневым: один контур, обезличенный срез, согласованная база, журнал решений человека и откат.

## Документы

[`docs/README.md`](docs/README.md), [`docs/traceability-matrix.md`](docs/traceability-matrix.md), [`docs/threat-model.md`](docs/threat-model.md), [`docs/osint-and-pilot-gates.md`](docs/osint-and-pilot-gates.md), [`SECURITY.md`](SECURITY.md), [`LICENSES.md`](LICENSES.md).

Лицензия MIT, если файл не говорит иного. Этот текст — инженерное описание, не договор, не обоснование безопасности и не сертификат готовности.

---

# English version

## Allowed claim

Given a formal repair instance, RepairFlow builds a candidate schedule and independently reports whether the declared hard constraints hold, or returns structured reasons.

The mode is shadow. A person decides. The program does not dispatch vehicles, write back to an enterprise system, or replace a safety controller.

## How to read a verdict

| Word | When it is honest |
| --- | --- |
| `verified` | Every operation is covered, the hard notary is empty, and the kernel status is `feasible` or `optimal`. |
| `domain_verified` | A shop CSV passed `repairflow verify-plan`. The kernel was not called. `verified_feasible` stays false. |
| `optimal` | An exact run returned `OPTIMAL` on the original chain in one compiler pass, and the notary is empty. A heuristic does not inherit the word. |

A shorter makespan is not an improvement when coverage is incomplete or a hard violation appears.

## Repository family

Public repositories under [KonkovDV](https://github.com/KonkovDV) sit beside this one. Their reports are not RepairFlow evidence.

| Repository | Role | What RepairFlow does not import |
| --- | --- | --- |
| [SynAPS](https://github.com/KonkovDV/SynAPS) | Slot search. Named solver configs, a reproducible run, its own feasibility check. | The kernel source. This repo keeps the pin in the evidence table. |
| [SynAPS-GridPlan](https://github.com/KonkovDV/SynAPS-GridPlan) | Laboratory maintenance scheduling for power equipment. Search and checking are separate. | A different domain, pin, and report set. |
| [SynAPS-ProgramPlan](https://github.com/KonkovDV/SynAPS-ProgramPlan) | A programme plan with a second check and a hash-chained decision log. | The operator log here is still a contract, not a hash chain. |
| [SynAPS-MobiRoute](https://github.com/KonkovDV/SynAPS-MobiRoute) | Dial-a-ride planning. | Not repair, and not this notary. |
| [AeroBIM](https://github.com/KonkovDV/AeroBIM) | A finding carries a clause and an identifier. A deterministic gate sets the pass flag. | Construction review. The borrowed idea is the shape of a verdict: code, identifiers, interval. |
| [RailBreak](https://github.com/KonkovDV/RailBreak) | A jury packet: one run, a sourced table, an explicit uncovered list. | Odometry measurements. |

If this page disagrees with [`docs/limitations.md`](docs/limitations.md) or with the table below, those win.

## Evidence boundary

The only generated table is in the Russian section above, between the evidence markers. `tools/attest.py` writes it. The public-page check rejects a digit outside it. The words "zero" and "empty" below name the correctness-oracle target, not a fresh measurement.

A number without a commit, provenance, seed, solver status, checker output, and a denominator is not evidence.

## Reproduce

The Python version is the `requires-python` field of [`pyproject.toml`](pyproject.toml).

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

The demo uses synthetic data only, checks a clean plan and an intentionally broken one, and must stay fail-closed.

## Boundary

```text
formal instance → schema/domain validation → candidate planner
               → independent checker → evidence bundle → human decision
```

The notary does not import solver search code. A published `verified` verdict also reads the pinned SynAPS feasibility check: independence is about search, not about the whole kernel ecosystem. `repairflow verify-plan` does not call the kernel.

Capacity `K` is `K` interchangeable lanes. Occupancy is half-open, `[start, end)`, so touching endpoints do not overlap. Setup extends occupancy backwards. At one instant an end is processed before a start. The same sweep covers ordinary and frozen assignments.

```text
false_accept_rate = invalid_plans_accepted_as_verified / invalid_plans_presented
```

For correctness-oracle fixtures the target is zero accepted invalid plans. The minute oracle does not judge the exchange-pool ledger. When the oracle and the notary disagree, the case is read by hand. The oracle is not fitted to the notary.

## What the notary checks

The schema rejects an incomplete or ambiguous input. The checker then covers assignment coverage, precedence with lags, posts, crews, skills, calendars, tooling, setup, spares, the exchange pool, frozen assignments, and the split between a soft due date and a hard deadline.

The published-work position is the [literature review](docs/literature-2026.md) and the [evidence protocol](docs/evidence-protocol.md). RepairFlow does not present itself as a new general-purpose solver.

## Not covered

There is no write-back, dispatch, SCADA, or safety function. There is no claim of an industrial effect, a live customer, sponsorship, or a certificate. The public pages of the [pilot programme](https://ftim.ru/pilotirovanie/), the [plant profile](https://www.mosgortrans.ru/about/branches/filial-sokolnicheskii-vagonoremontno-stroitelnyi-zavod-svarz-gup-mosgortrans/), and the [innovation cluster](https://i.moscow/pilot) are entry gates, not a deployment record.

Route variants are not modelled. The operator log is a contract without a writer. The native exact model has not been started: an owner decision opens it, not this page. The full list is [`docs/limitations.md`](docs/limitations.md).

A first pilot, if one happens, stays in shadow: one contour, an anonymised slice, an agreed baseline, a human decision log, and rollback.

## Documents

[`docs/README.md`](docs/README.md), [`docs/traceability-matrix.md`](docs/traceability-matrix.md), [`docs/threat-model.md`](docs/threat-model.md), [`docs/osint-and-pilot-gates.md`](docs/osint-and-pilot-gates.md), [`SECURITY.md`](SECURITY.md), and [`LICENSES.md`](LICENSES.md).

MIT, unless a file says otherwise. This page is an engineering description, not a contract, a safety case, or a readiness certificate.
