# Прослеживаемость требований

Статусы в таблице:

- `implemented` — функциональность реализована в `main` и покрыта автоматическими тестами;
- `documented` — зафиксированы архитектурное решение или граница применимости, сама функция в расчётный путь не включена;
- `measured, not closed` — проверочные замеры выполнены и задокументированы, этап остаётся открытым до контрольного пересчёта;
- `blocked` — организационное или внешнее условие, которое не может быть закрыто кодом внутри репозитория.

| Требование | Статус | Где подтверждение |
| --- | --- | --- |
| Строгая доменная схема и метки времени в UTC | implemented | `src/repairflow/model.py`, `tools/export_schemas.py`, `tests/test_contract.py` |
| Сходящаяся и ветвящаяся технологическая карта (DAG) | implemented | `src/repairflow/dag_compiler.py`, `tests/test_dag_compiler.py`, [`adr/0002-dag-over-chain-kernel.md`](adr/0002-dag-over-chain-kernel.md) |
| Параллельные полосы постов и матрица переналадки | implemented | `src/repairflow/capacity.py`, `src/repairflow/lane_setup.py`, `tests/test_dag_and_setup.py` |
| Квалификационные допуски и назначение конкретной бригады в плане | implemented | Привязка бригады при публикации плана; отказ `CREW_UNBOUND`, `SKILL_MISMATCH`, `SKILL_EXPIRED` в `checker.py` |
| Сменные календари постов, бригад и оснастки (включая закрытые) | implemented | Доменный нотариус `src/repairflow/checker.py`, `tests/test_verdict_safety.py` |
| Передача сменных календарей бригад и оснастки в модель ядра | implemented | Непустые смены компилируются в `AuxiliaryResource.calendar`; закрытый календарь с персоналом, смешанный пул и прерываемая операция дают `KERNEL_CALENDAR_UNSUPPORTED` |
| Ограничение размера задачи для CP-SAT (`CPSAT_OPS_CAP = 100`) | implemented | Явный отказ `CPSAT_OPS_CAP` с кодом выхода `2` без подмены эвристикой (`src/repairflow/limits.py`) |
| Полное покрытие операций как обязательное условие допустимости | implemented | `allow_partial_plan` оставляет статус `PARTIAL` и код выхода `2` (`PARTIAL_COVERAGE`) |
| Независимость нотариуса от кода поиска и компилятора | implemented | `checker.py` не импортирует `adapter`, `planner` и `synaps.solvers`; AST-проверка в `tests/test_verdict_safety.py` |
| Однозначность назначенной бригады и вида ресурса | implemented | Отказы `AMBIGUOUS_CREW` и `UNKNOWN_RESOURCE`, `tests/test_red_team_notary.py` |
| Выдача `verified` только при подтверждённом статусе ядра | implemented | Требуется статус ядра `feasible` или `optimal`; `verify-plan` выдаёт максимум `domain_verified` |
| Задержки между операциями, график прихода деталей и срок действия допуска | implemented | `tests/test_domain_semantics.py` |
| Отклонение несуществующих и закрытых календарей | implemented | Отказ `CALENDAR_BROKEN`; для несинтетических данных обязателен `calendar_id` или `availability=always_open` |
| Сверка образа собранной задачи ядра с исходной задачей (`INVALID_ID_MAP`) | implemented | Таблица в [`../README.md`](../README.md), `_id_map_issues`, `_kernel_references_closed`, `_kernel_image_matches`, `tests/test_id_map_injectivity.py` |
| Независимый поминутный оракул допустимости | implemented | `tests/oracle_minutes.py`, `tests/test_oracle_minutes.py` |
| Кампания намеренной порчи планов (не менее 10 000 сценариев) | implemented | Быстрый срез `docs/fault-campaign.json` (`10 080` планов, `false_accept = 0`, `false_reject = 0`) и полный прогон `docs/fault-campaign-nightly.json` (`109 665` планов, `false_accept = 0`, `false_reject = 0`) |
| Мутационное тестирование четырёх модулей нотариуса | measured, not closed | Серия прогонов `mutmut` (до `1962` убитых из `2137` на `7f6e9ae`, разбор `126` эквивалентных и тесты `tests/test_nightly_survivors.py` для `49` остальных); [`mutation-survivors.md`](mutation-survivors.md) |
| Проверка внешнего цехового плана CSV без вызова ядра | implemented | `repairflow verify-plan`, статус `domain_verified`, привязка к файлу и номеру строки CSV, SHA-256 файла; `tests/test_shop_plan.py` |
| Манифест импорта CSV, перевод ночных смен и HMAC-псевдонимы бригад | implemented | `src/repairflow/ingest.py`, `tests/test_ingest_manifest.py` |
| Фильтрация ключей и шаблонов персональных данных в `domain_attributes` | implemented | `src/repairflow/personal_fields.py`, `tests/test_personal_fields.py`. Ключ, почта, телефон, СНИЛС, ФИО, инициалы, слово с заглавной вне цехового словаря и короткая запись из двух-трёх чужих слов отвергаются. Имя строчными внутри длинной фразы остаётся открытым |
| Русская подсказка у каждого кода отказа | implemented | `SUGGESTIONS` в `src/repairflow/reasons.py` покрывает каждый `ReasonCode`; `tests/test_reason_hints.py`. У `CALENDAR_BROKEN` та же фраза, что у `WINDOW_BROKEN` |
| Конструкции установленного CP-SAT | implemented | `tests/test_kernel_formulation.py` читает решатель пина: одно назначение, интервал длины, `add_no_overlap` / `add_cumulative`, `add_circuit`, предшественник без лага, пустой календарь как круглосуточный, заморозка. Слов `spare`, `preemptive`, `lag` в файле нет. Построчного доказательства нет |
| Отчёт не выпускает поддельный `domain_verified` | implemented | `repairflow report`: код `0` только у `verified` и у чистого `domain_verified` с `exit_code` `0`. Ячейка Markdown не рвётся на `\|`. `tests/test_report_surface.py` |
| Двухстадийный офлайн-образ Docker с корнем только для чтения | implemented | `Dockerfile`, [`runbook.md`](runbook.md), `tests/test_offline_image.py` |
| Закрепление шагов GitHub Actions по полным SHA коммитов | implemented | `.github/workflows/`, `tests/test_action_pins.py`, `tests/test_supply_chain_workflow.py` |
| Блокирующие расходные и оборотные запчасти с временем возврата | implemented | `src/repairflow/checker.py`, `src/repairflow/ledger.py`, `tests/test_exchange_and_inspection.py` |
| Обменный фонд агрегатов как книга остатков по времени | implemented | `src/repairflow/ledger.py`, [`adr/0004-exchange-pool-ledger.md`](adr/0004-exchange-pool-ledger.md) |
| Включение ветки дефектовки при заморозке ранее выданных слотов | implemented | `repairflow inspect`, [`adr/0005-inspection-rewrites-the-card.md`](adr/0005-inspection-rewrites-the-card.md) |
| Разделение мягкого планового срока и жёсткого директивного срока | implemented | `DUE_MISSED` (показатель `kpi`) против `DEADLINE_MISSED` (жёсткий отказ) |
| Перепланирование пяти типов цеховых сбоев | implemented | `replan_disruption` в `planner.py`: `POST_DOWN`, `PART_DELAY`, `CREW_ABSENT`, `DURATION_OVERRUN`, `URGENT_JOB`. Восьмичасовое окно только при переданном `now`. Команда `disrupt` освобождает названные операции и событие не принимает. `tests/test_disruption_events.py`, `docs/disruption-campaign.json` |
| Единые метрики и проверка отпечатков `schedule_hash` и `result_hash` | implemented | `src/repairflow/metrics.py`, `repairflow check --verify-hashes`, `tests/test_metrics_and_hashes.py` |
| Закрепление коммита SynAPS, версии OR-Tools и хеш-замка колёс | implemented | `tools/verify_lock.py`, `requirements-lock.txt`, `ortools==9.15.6755`, `tests/test_lock_hashes.py` |
| Прямая опись состава CycloneDX и проверка установленных файлов | implemented | `src/repairflow/sbom.py`, `src/repairflow/artifact_record.py`, `src/repairflow/dependency_lock.py` |
| Журнал решений оператора с хеш-цепочкой и внешним HMAC-свидетелем | implemented | `repairflow decide`, `repairflow log verify`, `repairflow log witness`, `tests/test_decision_log.py` |
| Минимальный по удалению свидетель конфликтующих операций | implemented | `src/repairflow/explanations.py` (для одного доменного кода отказа; не является CP-MUS/MCS) |
| Автоматический контроль запрещённых фраз и генерируемых сводок | implemented | `tests/test_banned_claims.py`, `tools/attest.py`, `tools/render_submission_facts.py`, `tools/pack_submission.py` |
| Живые ссылки и таблицы README в согласии с кодом | implemented | `tests/test_doc_links.py`: относительные ссылки и якоря, команды против парсера, каждый код отказа в таблице |
| Собственная нативная модель CP-SAT | documented | В коде её нет. [`adr/0006-native-model-stays-unwired.md`](adr/0006-native-model-stays-unwired.md) называет замер, без которого её к `plan` не подключают |
| Работа в теневом режиме без сети и без записи в EAM/ERP | documented | [`threat-model.md`](threat-model.md), [`adr/0003-release-boundary.md`](adr/0003-release-boundary.md), [`pilot-protocol.md`](pilot-protocol.md) |
| Вероятностное распределение длительности ремонта | documented | Длительность задаётся числом минут; `DURATION_OVERRUN` проверяет чувствительность к конкретному удлинению |
| Вывод минимальных несовместных подмножеств ограничений (MUS/MCS) | blocked | Назван как следующий исследовательский шаг в [`literature-2026.md`](literature-2026.md) |
| Каталог альтернативных вариантов маршрута технологической карты | blocked | [`limitations.md`](limitations.md) |
| Криптографическая подпись релизных архивов | blocked | Поле подписи остаётся `absent`; релизный ключ в репозитории не хранится |
| Официальная заявка на пилот, TRL 6, подтверждённый эффект у заказчика, сертификация ISO 55001 | blocked | Требуются юридическое лицо, договор о данных, согласованная историческая база и испытания на предприятии |
