# Карта документации

Страницы разложены по тому, зачем вы пришли: запустить, сделать конкретную работу, найти точное правило или понять, почему так устроено. Если страницы расходятся, верен [`limitations.md`](limitations.md). Что проверено на какой ревизии `main`, говорит таблица в [`../README.md`](../README.md); её пишет `tools/attest.py`, значок сборки её не заменяет.

## Запустить и показать

- [`../README.md`](../README.md) — что это, как читать вердикт, команды, таблица аттестации.
- [`jury-demo.md`](jury-demo.md) — прогон `repairflow demo` по шагам и сборка папки подачи.
- [`runbook.md`](runbook.md) — образ без сети из склада колёс, корень только для чтения.
- [`MVP.md`](MVP.md) — команда готовности в две строки.

## Сделать работу

- [`data-request.md`](data-request.md) — какие обезличенные данные нужны для теневого сравнения.
- [`data-mapping-1c-toir.md`](data-mapping-1c-toir.md) — как поля учёта ремонта ложатся в `repairflow.problem.v1`.
- [`pilot-protocol.md`](pilot-protocol.md) и [`pilot-kpi-template.md`](pilot-kpi-template.md) — порядок теневого пилота на одном участке и таблица показателей.
- [`operator-decision-log.md`](operator-decision-log.md) — как вести и проверять журнал решений (`repairflow decide`, `repairflow log`).
- [`release-checklist.md`](release-checklist.md) — что отметить перед лабораторным выпуском и перед подачей на пилот.
- [`../APPLICATION.md`](../APPLICATION.md) — карточка заявки и гипотеза пилота.

## Справка

- [`limitations.md`](limitations.md) — полный перечень границ. При разночтении прав он.
- [`core-compat.md`](core-compat.md) — пин ядра SynAPS, вызовы, предел CP-SAT, передача смен.
- [`evidence-table.md`](evidence-table.md) и [`benchmark-protocol.md`](benchmark-protocol.md) — сводная таблица решателей, формулы показателей и правила замера.
- [`submission-facts.md`](submission-facts.md) — числовая сводка подачи; собирается автоматически.
- [`traceability-matrix.md`](traceability-matrix.md) — требование, код, тест.
- [`sbom-and-provenance.md`](sbom-and-provenance.md) — опись CycloneDX, замок колёс, `schedule_hash` и `result_hash`.
- [`atc-baseline-contract.md`](atc-baseline-contract.md) — модуль упорядочения ATC и правило планировщика: где они расходятся.
- [`../CHANGELOG.md`](../CHANGELOG.md) — что менялось.

## Почему так устроено

- [`domain-assumptions.md`](domain-assumptions.md) — граф работ, полосы, переналадка, смены, запчасти, обменный фонд.
- [`evidence-protocol.md`](evidence-protocol.md) — четыре ярлыка результата и лестница проверок от оракула до сбоев.
- [`adr/0002-dag-over-chain-kernel.md`](adr/0002-dag-over-chain-kernel.md) — ветвящаяся карта поверх ядра, которое умеет только цепочку.
- [`adr/0003-release-boundary.md`](adr/0003-release-boundary.md) — теневой план не становится командой.
- [`adr/0004-exchange-pool-ledger.md`](adr/0004-exchange-pool-ledger.md) — обменный фонд как книга остатков.
- [`adr/0005-inspection-rewrites-the-card.md`](adr/0005-inspection-rewrites-the-card.md) — дефектовка переписывает одну карту.
- [`adr/0006-native-model-stays-unwired.md`](adr/0006-native-model-stays-unwired.md) — своя модель CP-SAT: какой замер нужен до подключения.
- [`threat-model.md`](threat-model.md) — граница автономной установки и личные данные.
- [`literature-2026.md`](literature-2026.md) — публикации и открытые планировщики.
- [`osint-and-pilot-gates.md`](osint-and-pilot-gates.md) — требования площадок пилотирования и соседние системы.
- [`SYNAPS_REPAIRFLOW_MVP_SKELETON.md`](SYNAPS_REPAIRFLOW_MVP_SKELETON.md) — исходная спецификация MVP.

## Как проверяли сам нотариус

- [`red-team-remediation.md`](red-team-remediation.md) — оракул минут, кампания порчи, импорт CSV, сбои, журнал, цепочка поставки.
- [`mutation-survivors.md`](mutation-survivors.md) — мутационные прогоны четырёх модулей и разбор выживших.
- [`murder-board.md`](murder-board.md) — неудобные вопросы и прямые ответы.
- [`../AUDIT.md`](../AUDIT.md) — формальная модель ограничений и два раунда аудита.

## Сопровождение

- [`documentation-audit.md`](documentation-audit.md) — как страницы сверяются с кодом, командами и тестами.
- [`BANNED_CLAIMS.txt`](BANNED_CLAIMS.txt) — фразы, которых на публичных страницах быть не должно (`tests/test_banned_claims.py`).
- [`AI_USE.md`](AI_USE.md) — где в разработке помогали автоматические инструменты и почему вердикт от них не зависит.
- [`GH_AGENT_BUS.md`](GH_AGENT_BUS.md) — координация задач разработки через задачи и запросы GitHub (`tools/agent_bus.py`).
- [`brand/`](brand/) — знак RepairFlow и полный лист бренда.
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md), [`../CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md), [`../SECURITY.md`](../SECURITY.md), [`../LICENSES.md`](../LICENSES.md) — правки, правила общения, уязвимости, лицензии зависимостей.

Число попадает на страницу вместе с источником, ревизией кода, входом, настройкой решателя, выводом нотариуса и знаменателем. Иначе это допущение, гипотеза или пункт плана.
