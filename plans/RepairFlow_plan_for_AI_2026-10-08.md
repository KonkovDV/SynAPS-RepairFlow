# SynAPS RepairFlow: план для ИИ-исполнителя

Срез: 08.10.2026, `main` = `e558751` (PR #68). Пост-мерж CI этого коммита: run `37687520818`, push, все шесть джобов success, включая `test-slow`.
Этот файл заменяет план от 02.10.2026. Старый план и «Анализ 0–7» ИИ не давать: почти всё из них закрыто, и ИИ начнёт чинить уже починенное.

Легенда:
- **[КОД]** — прочитано в коде на этом срезе;
- **[ПРОВЕРИТЬ]** — вывод не подтверждён запуском: сначала падающий тест, потом правка;
- **[ВЛАДЕЛЕЦ]** — решение человека, код его не заменит.

Если `git rev-parse origin/main` новее `e558751`, сначала прочитай `CHANGELOG.md` от этого коммита и вычеркни из плана уже сделанное.

---

## 1. Что уже закрыто в `main` (не переделывать, только не сломать)

| Пункт | Где закрыт | Как проверяется |
|---|---|---|
| Пин ядра один везде (`f939727`) | #67, #68 | `tools/verify_lock.py`, `test_evidence_manifest_matches_the_pinned_kernel` |
| Таблица evidence в README генерируется из манифеста | #68 + `tools/attest.py` | `test_readme_evidence_table_is_generated` |
| Бенчмарк закоммичен с суммой | #68 | `benchmark/results/benchmark.json`, `SHA256SUMS` (хэш LF-блоба) |
| `SKILL_EXPIRED` по концу визита | #68 | `test_visit_crossing_noon_expires_a_permit_that_ends_at_noon` |
| `domain_only` не даёт `verified`/`optimal` | #68 | `test_only_admissible_kernel_statuses_exit_zero`, `test_domain_only_cannot_become_optimal_under_cpsat` |
| Висячий `calendar_id` = `CALENDAR_BROKEN`; несинтетика без календаря требует `availability=always_open` | #68 | `test_dangling_calendar_id_is_not_treated_as_open`, `test_non_synthetic_resource_without_a_calendar_is_invalid` |
| Preemptive считает пересечение масок | до #68 | `test_preemptive_open_minutes_use_the_intersection` |
| AST-гейт импортов checker-модулей, включая `domain_verify.py` | #68 | `test_checker_modules_do_not_import_search_or_solver` |
| `test-slow`: main, nightly, PR с меткой `slow` | #68 | `.github/workflows/ci.yml` |
| Кампания 10 000 плохих планов, `false_accept = 0` | #68 | `docs/fault-campaign.json`, slow-тест |
| ATC встроен в планировщик | раньше | `_DOMAIN_LIST_ORDERS = {"GREED", "EDD", "ATC"}` в `planner.py` [КОД] |
| Календари бригад и оснастки в ядре (одна смена) | #67 | `tests/test_kernel_compat.py` |
| CP-SAT ≤ 100 операций, выше — `CPSAT_OPS_CAP` без вызова решателя | #67 | `tests/test_cpsat_cap.py` |
| RT-1…RT-9, sweep-line, rotable ledger, DAG fixpoint, deletion-minimal witness, EDD, `verify-plan` | до #68 | см. `docs/traceability-matrix.md` |

Открытых issues в репозитории нет. #11 и #46 закрыты владельцем, но журнал оператора без цепочки хэшей и lock с плавающим `pydantic>=2.9` остаются работой этого плана (фазы 3 и 4).

---

## 2. Что реально осталось (по риску ложного «зелёного»)

### P0. Доверие к evidence
- **G1** [КОД] Кампания слабая. Пять мутаций по кругу на одном инстансе (`tiny`, seed 1, GREED), все заведомо невалидны: сдвиг на −30 дней, удаление строки, чужая бригада, тот же слот, длительность 1 минута. Нет независимого оракула, нет класса «может пройти», не мерится `false_reject`. Число `false_accept = 0` честное, но эксперт спросит про силу мутаций.
- **G2** [КОД] `result_hash` и `config_hash` включают `runtime_manifest()` (Python, платформа). Один и тот же план на Windows и Linux даёт разные хэши. В CI это уже ловилось. Нет хэша, который воспроизводится на любой машине.
- **G3** Закрыто гейтом `tests/test_banned_claims.py`. О1 принято по рекомендации этого плана: страницы переименованы в `docs/literature-2026.md` и `docs/evidence-protocol.md`, правило не сужалось. Отрицание в скелете MVP — одна точная строка в `docs/banned-claims-allowlist.txt`. Год в заголовке README не копируется: он остаётся только в имени файла, потому что видимые цифры вне блока evidence запрещены.
- **G4** [КОД] `docs/jury-demo.md` описывает четыре шага и не упоминает `verify-plan` и кампанию.

### P1. Пилотопригодность
- **S1** [КОД] `requirements-lock.txt`: `pydantic>=2.9` плавает, транзитивных хэшей нет. Офлайн-установки нет.
- **S2** [КОД] Actions `checkout@v4`, `setup-python@v5`, `upload-artifact@v4` работают на Node 20, который принудительно гонится на Node 24 (предупреждение в каждом прогоне). Последние релизы: `checkout v7.0.1`, `setup-python v7.0.0`, `upload-artifact v7.0.2` [ПРОВЕРИТЬ release notes на ломающие изменения]. `ubuntu-latest` переезжает на Ubuntu 26 с 19.10.2026. Нет CodeQL, dependency-review, Scorecard.
- **K3** [КОД] Журнал оператора: модель `DecisionEvent`, `append_decision`, `read_decision_log`, `tools/append_decision.py` есть. Нет `prev_hash`, file lock, fsync, сверки `result_hash` с файлом результата, CLI в самом `repairflow`, команды проверки журнала, метрик.
- **K6** [КОД] События: есть только `InspectionEvent`. `replan_after_disruption` принимает голый список id операций. POST_DOWN, PART_DELAY, CREW_ABSENT, DURATION_OVERRUN, URGENT_JOB не моделируются (так и записано в `docs/limitations.md`, п. 10).
- **K7** [КОД] Ввод реальных данных: CSV читается только в UTF-8. Разделитель угадывается лишь в `shop_plan.py`. Нет `manifest.json` с кодировкой, разделителем и часовым поясом, нет ночной смены через полночь, нет псевдонимизации.

### P2. Возможности (после решения владельца)
- **K1** Ядро: ≤ 100 операций, календари только внутри одной смены; `KERNEL_CALENDAR_UNSUPPORTED` для закрытого календаря, смешанного пула и preemptive.
- **K2** Объяснения: только deletion-minimal по операциям, не MUS/MCS.

---

## 3. Системный промпт для ИИ (вставить первым сообщением)

```
Ты ведущий инженер SynAPS-RepairFlow. Работаешь ТОЛЬКО по plans/RepairFlow_plan_for_AI_2026-10-08.md.
Старые «Анализ 0–7», «План.txt» и план от 02.10 не используй.

Шаг 0 любой задачи: git fetch; прочитай CHANGELOG от e558751 до origin/main и нужные модули.
Если пункт уже сделан, не переделывай: допиши недостающий регрессионный тест и отметь пункт со ссылкой на коммит.

Инварианты (нарушение = откат PR):
1. verified только при: полное покрытие, 0 hard-нарушений, kernel_status ∈ {feasible, optimal}.
   domain_only даёт максимум domain_verified (verify-plan). Ложный зелёный хуже ложного красного.
2. checker.py, checker_primitives.py, capacity.py, lane_setup.py, ledger.py, domain_verify.py
   не импортируют repairflow.adapter, repairflow.planner, synaps.solvers.*. Оракул кампании
   не импортирует checker.
3. Fail-closed: неполный или неоднозначный вход = ошибка валидации, не тихий дефолт.
   Календарь без окон = закрыт. В SynAPS пустой список = 24/7, поэтому закрытый календарь
   в ядро не передаётся, а отклоняется KERNEL_CALENDAR_UNSUPPORTED.
4. optimal только для CP-SAT OPTIMAL на исходной цепочке за один проход компилятора.
5. Никаких monkey-patch в продукте, write-back в 1С/EAM, сетевых вызовов в рантайме.
6. Ни одного числа в README без commit / seed / solver / checker output / denominator.
   Таблица evidence генерируется: python tools/attest.py. Руками не правится.
7. Манифест удостоверяет только коммит, чей СОБСТВЕННЫЙ push-прогон на main успешен,
   включая test-slow. PR-прогон не доказательство. Коммит не удостоверяет сам себя.
   Номер прогона не выдумывается: читай его через gh api.
8. Не поднимай CPSAT_OPS_CAP без нового замера (таймер, размер, результат в CHANGELOG).
9. Не копируй synaps/ в RepairFlow. Нужен новый API ядра → правка в KonkovDV/SynAPS
   отдельным PR и новый пин. Расхождение API → стоп и запись в docs/core-compat.md.
10. Запрещённые формулировки: docs/BANNED_CLAIMS.txt. Claims: experiment, TRL 4.
11. Не трогать раздел 1 плана, кроме добавления тестов.

Цикл на задачу: (1) issue с acceptance → (2) ПАДАЮЩИЙ тест → (3) фикс →
(4) локально: ruff check, ruff format --check, mypy --strict src/repairflow, pytest -m "not slow",
pytest -m slow, repairflow demo --out out, repairflow benchmark --out bench,
python tools/verify_schema.py, python tools/export_schemas.py, python tools/verify_lock.py →
(5) CHANGELOG, docs/traceability-matrix.md, docs/limitations.md →
(6) PR с разделом «Что не покрыто», метка slow → (7) squash-merge только при зелёном CI →
(8) дождаться push-прогона на main → отдельный docs-PR: python tools/attest.py --commit <sha> --run-id <id>.
Одна фаза = одна ветка. Не переходи дальше, пока фаза не зелёная.
```

---

## 4. Фазы

Для каждой задачи: ветка, файлы, сначала тест, потом код, acceptance. Сроки — оценка для одного исполнителя.

### Фаза 0. Гигиена публичного текста (0,5 дня) — P0
Статус: сделано на ветке `docs/banned-claims-gate`. Не переделывать, кроме падения `tests/test_banned_claims.py`.
Ветка `docs/banned-claims-gate`.
1. После решения О1 привести тексты к правилу (переименовать заголовки и файлы и обновить все ссылки, или сузить правило).
2. Тест `tests/test_banned_claims.py`: сканирует `README.md`, `APPLICATION.md`, `docs/**/*.md` (включая `docs/adr/`). Регистр не важен. Разрешения — только через `docs/banned-claims-allowlist.txt` в формате `файл:точная строка`, с причиной на предыдущей строке. Отрицание в скелете MVP — единственная такая строка. Не сужать сканирование обратно до `docs/*.md`.
3. Обновить `docs/jury-demo.md`: шаги из раздела 4, фаза 9, только с числами из сгенерированных файлов.
4. Пройти README на числа вне генерированного блока. Каждое такое число либо убрать, либо дать ссылкой на файл evidence.
- **Acceptance:** гейт зелёный, allowlist короткий и с причиной у каждой строки, ни одного числа без источника.

### Фаза 1. Сильная fault-кампания (2–3 дня) — главный аргумент «нотариуса»
Ветка `test/fault-campaign-v2`.
1. Оракул `tests/oracle_minutes.py`: поминутная проверка на малых инстансах (горизонт ≤ 3 суток). Импортирует только stdlib и `repairflow.model`, не `checker`. Проверяет покрытие, precedence с лагами, ёмкость постов, бригад и оснастки (`max_parallel`, setup в occupancy), календари (закрытый = закрыт), допуски по концу визита, окна, жёсткие дедлайны, frozen, расход ЗИП и ротаблов.
2. Мутаторы в `tests/fault_campaign.py`: сдвиг на ±k минут (k ∈ {1, 5, 30, 240}), смена поста, смена бригады, удаление оснастки, дубль строки, перерасход ЗИП/ротабла, выход из окна, нарушение precedence/lag, истёкший допуск, сдвиг frozen, setup = 0, выход за горизонт.
3. Разметка каждой мутации оракулом: `must_reject`, если оракул нашёл нарушение, иначе `may_pass`. `false_accept` = checker принял, а оракул отверг. `false_reject` = checker отверг, а оракул принял. Мерить оба.
4. Матрица: пресеты `tiny` и `repair-site-mvp`, seeds 1…30, решатели GREED, EDD, ATC. PR-набор ≥ 10 000. Nightly ≥ 100 000 с отчётом артефактом.
5. Отчёт `docs/fault-campaign.json` v2: всего, по мутаторам, по пресетам, `false_accept`, `false_reject`, seed, коммит, пин, хэш входа. README берёт числа только отсюда через `tools/attest.py`.
6. `mutmut` на `checker.py`, `capacity.py`, `ledger.py`, `lane_setup.py`. Каждого выжившего мутанта либо убить новым тестом, либо записать в `docs/mutation-survivors.md` с причиной (эквивалентный мутант). Mutation score положить в evidence.
- **Acceptance:** `false_accept = 0` на N ≥ 10 000 в PR и ≥ 100 000 в nightly. `false_reject` измерен и объяснён. Ни один старый тест не ослаблен.
- **Ловушка:** не подгонять оракул под checker. Если они расходятся, сначала разобрать пример руками.

### Фаза 2. Воспроизводимый хэш плана (1 день)
Ветка `feat/schedule-hash`.
1. Падающий тест: один план, разный `runtime_manifest` → одинаковый новый хэш.
2. Добавить `schedule_hash` = отпечаток (`input_hash`, `solver_config`, `synaps_commit`, отсортированные назначения, `claim_status`, `exit_code`, коды нарушений) без runtime. Поле добавочное, `repairflow.result.v1` не ломать. Схемы перегенерировать `tools/export_schemas.py` и `tools/write_schema_examples.py`.
3. В строки бенчмарка добавить `schedule_hash`. Тест: свежий прогон в CI на Linux даёт тот же `schedule_hash`, что в `benchmark/results/benchmark.json`.
4. `repairflow check --verify-hashes` проверяет и его.
- **Acceptance:** Windows и Linux дают одинаковый `schedule_hash`. `result_hash` по-прежнему идентифицирует машину и описан так в `docs/sbom-and-provenance.md`.

### Фаза 3. CI и цепочка поставки (1–2 дня)
Ветка `ci/supply-chain`. Правки `.github/workflows/` только через локальный git с правом `workflow`.
1. Actions на v7 после чтения release notes [ПРОВЕРИТЬ].
2. `runs-on: ubuntu-24.04` вместо `ubuntu-latest` до 19.10.2026. Переход на 26 — отдельным PR с полным прогоном.
3. Хэш-lock: `uv pip compile --generate-hashes` → `requirements-lock.txt` с хэшами всех транзитивных колёс. `pydantic` закрепить точно. `tools/verify_lock.py` требует хэш у каждой строки, кроме git-пина SynAPS (у него SHA коммита).
4. Офлайн: джоб собирает wheelhouse (`pip download`), затем `pip install --no-index --find-links wheelhouse`, затем `repairflow demo` без сети. Wheelhouse — артефакт релиза.
5. CodeQL (python), `dependency-review-action` на PR, OpenSSF Scorecard по расписанию.
- **Acceptance:** лабораторная часть `docs/release-checklist.md` отмечена со ссылками на прогоны. Офлайн-demo зелёный.

### Фаза 4. Журнал оператора v2 (2–3 дня)
Ветка `feat/decision-log-chain`.
1. Падающие тесты: подмена строки в середине ловится; перестановка двух строк ловится; обрезанный хвост ловится, если известен якорь (хэш головы в evidence-бандле); два параллельных писателя не перемешивают строки.
2. `DecisionEvent` v2: `prev_hash` (первая запись — 64 нуля) и `event_hash` = SHA-256 канонического JSON без `event_hash`. Журнал v1 без цепочки читается только как `legacy`. Смесь v1 и v2 — ошибка.
3. Запись: lock-файл через `os.open(O_CREAT | O_EXCL)` с таймаутом (работает и на Windows), затем `flush`, `os.fsync(file)` и `fsync` каталога, где ОС это позволяет.
4. Сверка: `input_hash` с файлом задачи, `result_hash` с файлом результата (`verify_plan_hashes`). Решение по результату с `exit_code != 0` нельзя записать как `accepted`.
5. CLI в самом `repairflow`: `repairflow decide --problem P --result R --accept|--accept-with-edits S|--reject --reason T --operator-code C --log L` и `repairflow log verify L [--head H]`. `tools/append_decision.py` оставить обёрткой.
6. `repairflow log stats L`: acceptance_rate, edit_rate, топ причин отказа. Только счётчики, без персональных данных.
- **Acceptance:** все атаки из п. 1 ловятся. `docs/operator-decision-log.md` обновлён. Псевдонимизация `operator_code` не ослаблена.

### Фаза 5. Типизированные сбои (1–2 недели)
Ветка `feat/disruption-events`.
1. `DisruptionEvent` (дискриминированное объединение) в `events.py`: `POST_DOWN(work_center_id, start, end)`, `PART_DELAY(spare_id, available_at)`, `CREW_ABSENT(crew_id, start, end)`, `DURATION_OVERRUN(operation_id, new_duration_min)`, `URGENT_JOB(job, operations)`.
2. `apply_disruption(problem, event) -> RepairFlowProblem` и затронутые операции → `replan_after_disruption` с frozen. Неизвестные id — ошибка, не пропуск.
3. Падающие тесты на каждый тип: после сбоя старый план отвергается checker-ом с ожидаемым кодом, новый план verified, frozen не сдвинуты.
4. Кампания: 5 типов × 30 seeds. Метрики: покрытие, `false_accept`, churn (доля сдвинутых операций), время пересчёта. Отчёт в evidence.
5. Rolling horizon с защищённым окном 8 ч и метрикой nervousness (`NERVOUSNESS_HIGH` уже есть в `reasons.py`).
- **Acceptance:** п. 10 `docs/limitations.md` переписан по факту. Демо-сценарий «пост сломался» есть в `repairflow demo`.

### Фаза 6. Реальные данные и офлайн-пакет (3–5 дней)
Статус: CSV-пакет без `manifest.json` не читается. CP1251, ночная смена 22:00–06:00 одним окном на следующие сутки, HMAC табельного номера в `crew-` и восемь hex, соль только аргументом. Пример пяти ошибок: `schemas/templates/five-errors/`. `tzdata==2026.3`. Docker и Astra не сделаны: хэш-лок фазы 3 на другой ветке, образа РЕД ОС здесь нет. Linux `workflow_dispatch` [37704013170](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/37704013170) на `2a45feb`: success, шесть джобов, включая `test-slow`. Это прогон ветки, не аттестация main. Эта строка статуса не входит в тот прогон.
Ветка `feat/ingest-manifest`.
1. `manifest.json` рядом с CSV: `encoding` (utf-8, utf-8-sig, cp1251), `delimiter`, `source_tz` (по умолчанию `Europe/Moscow`), `data_provenance`, версия выгрузки. Без манифеста несинтетика не грузится.
2. Перевод времени в UTC через `zoneinfo`. На Windows нужен пакет `tzdata`: добавить в зависимости и в lock.
3. Смена через полночь (22:00–06:00) = одно окно на две даты. Тест на границе суток.
4. Псевдонимизация: HMAC-SHA256 от табельного номера с солью заказчика. Соль не хранится в бандле, на выходе только код вида `crew-xxxxxxxx`. Тест: без соли повторить код нельзя, с той же солью код стабилен. Это 152-ФЗ-гигиена, не сертификация.
5. Шаблон `schemas/templates/shop-plan.csv` и пример с пятью типовыми ошибками для `verify-plan` (exit 2, причины по-русски).
6. Docker-образ на офлайн-wheelhouse из фазы 3. Совместимость с Astra/РЕД ОС [ПРОВЕРИТЬ на реальном образе].
- **Acceptance:** CP1251-выгрузка с ночной сменой проходит ingest. Тот же файл без манифеста отвергается.

### Фаза 7. Нативная CP-SAT модель `cpsat_native/` (2–3 недели) — только после ADR [ВЛАДЕЛЕЦ]
Не начинать без подписанного ADR (решение О2). Спецификация из плана от 02.10 остаётся в силе:
- optional intervals (операция × пост, операция × бригада), `add_exactly_one`;
- NoOverlap/Cumulative для постов (`max_parallel`), бригад, оснастки; календари = фиксированные интервалы недоступности; preemptive через сегменты;
- precedence по исходному DAG с лагами, без chain-компилятора, чтобы OPTIMAL относился к исходной модели;
- SDST на lane в согласии с `lane_setup.py`; ротаблы и обменный фонд через `add_reservoir_constraint`;
- лексикографическая цель: deadline → покрытие → взвешенная просрочка → churn → setup → makespan;
- hint из GREED, 1 worker + seed для evidence, LNS-обёртка выше 300 операций; в результат bound, gap, время до первого допустимого.
- Путь через ядро SynAPS остаётся для совместимости. Checker не меняется: нативная модель проверяется тем же нотариусом.
- **Acceptance:** 300–500 операций с календарями бригад и оснастки → FEASIBLE ≤ 60 с, checker чистый, 30 seeds (медиана и IQR); на `tiny` OPTIMAL совпадает с текущим. Новый предел записывается замером, а не числом с потолка.

### Фаза 8. Объяснения MUS/MCS (1–2 недели, после фазы 7)
- MUS через assumption-литералы (`add_assumptions`, `sufficient_assumptions_for_infeasibility`), литерал на группу ограничений: календарь ресурса, допуск, precedence, frozen.
- MCS «минимум перенесённых операций».
- Русские шаблоны: «Операция R17 не помещается: единственная бригада с допуском ТЭД (Б-2) недоступна 08:00–16:00, стенд С-1 занят R12 до 14:00».
- **Acceptance:** три демо-сценария; тест минимальности: удаление любого элемента MUS делает задачу выполнимой. До этого в тексте только «deletion-minimal witness».

### Фаза 9. Пакет подачи (1–2 дня)
- README, APPLICATION, jury-demo, traceability-matrix, murder-board — только из сгенерированного evidence.
- Демо 7 минут: вход → FIFO (красный, причины) → GREED/CP-SAT (зелёный) → сбой и replan без сдвига frozen → чужой «план из Excel» через `verify-plan` (exit 2, причины по-русски) → объяснение → строка журнала оператора и `log verify`.

---

## 5. Критический путь
- **0 → 1 → 2** (≈ 1 неделя): нотариус с сильной кампанией и воспроизводимым хэшем. Минимум до показа жюри и ФТИМ.
- **3 → 4** (≈ 1 неделя): офлайн, журнал оператора. Минимум до shadow-пилота.
- **5 → 6** (2–3 недели): сбои и реальные данные.
- **7 → 8** (3–5 недель, после ADR): точный решатель на реальных календарях и MUS.
- **9**: упаковка.

## 6. Решения владельца
- **О1.** Принято по рекомендации плана, без сужения правила: `docs/literature-2026.md`, `docs/evidence-protocol.md`, ссылки обновлены. Видимый заголовок README — «Обзор работ, FTIM и OSINT»; год не стоит в тексте README, только в имени файла. Альтернатива (сузить правило до «заявление о результате») не использовалась: гейт её не проверяет.
- **О2.** ADR: нативная CP-SAT модель против «тонкого слоя над SynAPS». Меняет тезис проекта.
- **О3.** Делать ли `test-slow` обязательным для каждого PR (сейчас по метке `slow`). С кампанией на 100 000 nightly PR-набор должен остаться в пределах ~2 минут.
- **О4.** Кто держит соль псевдонимизации (заказчик) и формат выгрузки 1С:ТОИР.
- **О5.** Юрлицо или ИП, УКЭП, свидетельство Роспатента, чистота прав на ядро SynAPS.
- **О6.** Бренд: «RepairFlow» занят чужими продуктами.
- **О7.** Контакты: владелец процесса, держатель данных, ИБ; обезличенная выгрузка за 1–3 месяца.
- Зрелость честно: TRL 4, цель пилота TRL 6.

## 7. Ловушки из опыта (ИИ должен знать заранее)
1. **Squash и пин.** SynAPS-PR, на коммит которого ссылается пин, вливать `--merge`, не squash. Иначе после удаления ветки пин ведёт в никуда. Проверка: `git merge-base --is-ancestor <pin> origin/main`.
2. **Editable SynAPS ломает тесты RepairFlow.** `pip install -e C:\SynAPS` кладёт в `sys.path` его папку `tests` и затеняет `tests` RepairFlow. Ставить ядро только `pip install "synaps @ git+...@<sha>"`.
3. **Ratchet длины функций в SynAPS** (`tests/test_architecture.py`, допуск +10 строк): `solve` и `check` уже у предела. Новую логику выносить в отдельные функции короче 80 строк; ratchet не поднимать.
4. **Дрейф схем в SynAPS:** после изменения модели запустить `python -m synaps write-contract-schemas --output-dir schema/contracts` и закоммитить. Руками JSON не править.
5. **CRLF.** Хэши файлов evidence считаются по LF-блобу (`.gitattributes` уже это фиксирует). Не считать SHA-256 по рабочей копии на Windows.
6. **`result_hash` зависит от машины** (до фазы 2). Не сравнивать его между Windows и CI.
7. **`gh pr merge` может ничего не напечатать.** Результат читать через `gh api repos/.../pulls/N --jq .merged,.merge_commit_sha`. `gh run watch` может оборваться: итог смотреть через `gh api .../actions/runs/<id>/jobs`.
8. **PowerShell:** без bash-HEREDOC; тексты коммитов через here-string `@" ... "@`, тело PR через `--body-file`. Сложный `--jq` с вложенными кавычками ломается — брать простой фильтр в одинарных кавычках.
9. **Предел CP-SAT мерится, не назначается.** 80 операций на двухдневном горизонте «падали» из-за ёмкости одной бригады, а не из-за решателя. Замер должен давать задаче место.
10. **Не удостоверять PR-прогон и сам себя.** Только push-прогон на main нужного SHA, затем отдельный docs-PR через `tools/attest.py`.

## 8. Что не проверено на этом срезе
- Release notes actions v7 и совместимость с текущими шагами.
- Скорость кампании на 100 000 и поведение `mutmut` на Windows (может понадобиться WSL или CI).
- Сборка Docker-образа под Astra/РЕД ОС.
- `planner.py`, `adapter.py`, `normalize.py` целиком на этом срезе не перечитывались: пункты [ПРОВЕРИТЬ] подтверждать тестом до правки.
