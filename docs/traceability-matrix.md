# Прослеживаемость требований

`implemented` — на `main` есть код и тесты. `documented` — есть граница или договор, самой возможности нет. `blocked` — в подаче на пилот этого обещать нельзя. `measured, not closed` — замер есть, фазу по нему не закрывали.

| Требование | Статус | Где подтверждение |
| --- | --- | --- |
| Строгая доменная схема и мгновения в UTC | implemented | `src/repairflow/model.py`, `tools/export_schemas.py` |
| Сходящаяся ремонтная карта | implemented | `src/repairflow/dag_compiler.py`, `tests/test_dag_compiler.py`, ADR-0002 |
| Конечные посты и матрица переналадки | implemented | адаптер, нотариус, тесты переналадки |
| Допуски бригады и названная бригада в опубликованном плане | implemented | планировщик называет бригаду при публикации; нотариус отвергает `CREW_UNBOUND` |
| Календари бригад и оснастки, включая пустой | implemented | доменный нотариус, `tests/test_verdict_safety.py` |
| Календари бригад внутри модели ядра | implemented | непустые смены компилируются в `AuxiliaryResource.calendar`; пустой календарь, смешанный пул и прерываемая операция по-прежнему дают `KERNEL_CALENDAR_UNSUPPORTED` |
| CP-SAT выше 100 операций | implemented | записанный отказ `CPSAT_OPS_CAP`; точный решатель не вызывается. 100 — последний проверенный размер CPSAT-10 на синтетической карте с одним навыком |
| Полное покрытие как условие проверки | implemented | `allow_partial_plan` не даёт код выхода 0 |
| Нотариус не зависит от поиска решателя | implemented | `checker.py` не импортирует поиск планировщика и `synaps.solvers`; опубликованный вердикт ещё читает проверку допустимости закреплённого SynAPS |
| Одна бригада и известный вид оснастки в назначении ядра | implemented | `AMBIGUOUS_CREW`, `UNKNOWN_RESOURCE`, `tests/test_red_team_notary.py` |
| `verified` только при допустимом статусе ядра | implemented | `feasible` или `optimal`. `domain_only` остаётся `domain_verified` на `verify-plan` и не получает код выхода 0 через `recheck` |
| Лаг предшественника, приходы расходных, допуск до конца визита | implemented | `tests/test_domain_semantics.py`; в v1 у `predecessor_ids` лаг 0 |
| Висячий идентификатор календаря — не открытый горизонт | implemented | нотариус даёт `CALENDAR_BROKEN`. Несинтетические данные задают `calendar_id` или `availability=always_open`. Синтетика может календарь не задавать |
| Кампания порчи не меньше 10 000 размеченных планов | implemented | префикс `docs/fault-campaign.json` v2: проверено 10080, false_accept 0, false_reject 0; локальный полный `docs/fault-campaign-nightly.json`: проверено 109665, false_accept 0, false_reject 0; синтетика; книгу обменного фонда не судили; это не артефакт CI |
| Независимый поминутный оракул | implemented | `tests/oracle_minutes.py`, `tests/test_oracle_minutes.py`; кампания v2 им пользуется; книгу обменного фонда не судили |
| Мутационное тестирование нотариуса | measured, not closed | ночные прогоны `37908445280`, `38037961461`, `38126032914` и `38228010896` на `b7c8c29`: убито 1587, живо 334, коды выхода совпали, пересчёт сошёлся; прогон `38618458299` на `a4e4e90`: убито 1814, живо 108, всего 1922; четыре выживших без объяснения умерли, новых не родилось; ночь `38698472141` на `7f6e9ae` прочитана: живо 175, у 126 есть причина, у 49 нет, тесты `tests/test_nightly_survivors.py` в тот счёт не входят; это не аттестация `main`; `docs/mutation-survivors.md` |
| Цеховой план без вызова ядра | implemented | `repairflow verify-plan`; заявление `domain_verified`; находка с операцией из листа хранит имя файла и номер строки; SHA-256 байтов листа в метаданных; повтор операции — ошибка разбора; пустая бригада не ошибка разбора; `tests/test_shop_plan.py` |
| Манифест загрузки CSV, ночная смена, псевдоним бригады | implemented | `src/repairflow/ingest.py`, `tests/test_ingest_manifest.py`; образ из склада колёс на Debian, Astra не проверялась |
| Ключ личных данных в `domain_attributes` | implemented | ключ и несколько форм значения отвергаются; другая строка и срок хранения открыты; `tests/test_personal_fields.py` |
| Склад колёс в финальном слое образа | implemented | стадия сборки, в финальный образ копируется `/usr/local`; запуск с корнем только для чтения; `tests/test_offline_image.py`, `Dockerfile`, `docs/runbook.md` |
| Шаги Actions по коммиту | implemented | тег остаётся комментарием; `tests/test_action_pins.py`, `tests/test_supply_chain_workflow.py` |
| Блокирующие запчасти | implemented | тесты запчастей нотариуса |
| Обменный фонд как книга остатков | implemented | `src/repairflow/ledger.py`, ADR-0004 |
| Дефектовка, которая замораживает уже выданную работу | implemented | `repairflow inspect`, ADR-0005 |
| Мягкий срок против жёсткого | implemented | `DUE_MISSED` против `DEADLINE_MISSED` |
| Пересчёт после сбоя с замороженными слотами | implemented | тесты пересчёта |
| Канонические метрики и проверка хешей | implemented | `src/repairflow/metrics.py`, `repairflow check --verify-hashes`; в `schedule_hash` нет манифеста запуска, `result_hash` его сохраняет |
| Пин коммита SynAPS | implemented | `tools/verify_lock.py` |
| Пин OR-Tools и прямая опись состава | implemented | `ortools==9.15.6755`, `repairflow.sbom` |
| Узнавание установленного колеса или sdist, отдельно от описи файлов | implemented | `repairflow.artifact_record`; подпись остаётся `absent` |
| Замок зависимостей по SHA-256 архивов | implemented | `repairflow.dependency_lock`; `locked` только когда каждый хеш на месте |
| Хеш-замок requirements | implemented | `requirements-lock.txt`; pydantic `2.13.5`; `tests/test_lock_hashes.py` |
| Подписанный артефакт | blocked | статус подписи остаётся `absent`; ключа выпуска в этой сборке нет |
| Нативная модель CP-SAT | documented | ADR-0006: разрешение есть, модель к `plan` не подключена |
| Граница «без сети, теневой режим» | documented | модель угроз, ADR-0003, протокол пилота |
| Журнал приёмки оператором | implemented | `repairflow decide`, `repairflow log verify`, хеш-цепочка; `log witness` — HMAC вершины внешним ключом, не подпись выпуска |
| `POST_DOWN`, `PART_DELAY`, `CREW_ABSENT`, `DURATION_OVERRUN`, `URGENT_JOB` | implemented | `tests/test_disruption_events.py`, `docs/disruption-campaign.json` |
| Каталог вариантов маршрута | blocked | `docs/limitations.md` |
| Лаг возврата оборотной внутри модели ядра | documented | власть у доменной книги; молчание ядра не даёт `verified` |
| Минимальный по удалению свидетель одного жёсткого кода | implemented | `explanations.py`; это не CP-MUS и не MCS |
| Объяснения MUS и MCS | blocked | в `docs/literature-2026.md` названы как следующая работа |
| Публичные страницы без списка запрещённых фраз | implemented | `tests/test_banned_claims.py`; исключения — точные строки в `docs/banned-claims-allowlist.txt` |
| Сводка чисел подачи | implemented | `docs/submission-facts.md` собирается из манифеста и двух кампаний; живую фразу аттестации переписывает `tools/attest.py`; `tests/test_submission_facts.py` |
| Готовность заявки для ФТИМ или кластера | blocked | юридическое лицо, цепочка прав, названный владелец, договор о данных |
| TRL 6 | blocked | заявленный уровень — TRL 4 |
| Эффект у заказчика или заявление об экономии | blocked | нужны база, подписанный срез и повторяемый разбор |
| Идентификаторы ядра совпадают с картой операций и постов | implemented | `_id_map_issues`; `tests/test_id_map_injectivity.py` |
| Распределение длительности ремонта | documented | фиксированные минуты; `DURATION_OVERRUN` — одна новая длительность |
| Соответствие ISO 55001 | blocked | стандарт системы организации, не сертификат этой программы |
