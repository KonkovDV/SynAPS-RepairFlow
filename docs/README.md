# Карта документов

Сначала договор о том, что программа обещает. Потом, чем это подтверждено. Потом, где проходит граница пилота.

Значок CI на главной странице — последний прогон workflow. Аттестованная ревизия — таблица в [`../README.md`](../README.md). Её собирает `tools/attest.py`. Значок эту таблицу не заменяет.

## С чего начать

1. [`../README.md`](../README.md) — для кого эта программа, команды, какие слова в ответе честные.
2. [`evidence-protocol.md`](evidence-protocol.md) — что считается доказательством.
3. [`limitations.md`](limitations.md) — чего программа не обещает.
4. [`runbook.md`](runbook.md) — лабораторный образ из склада колёс.
5. [`red-team-remediation.md`](red-team-remediation.md) — что нотариус закрывает и что остаётся снаружи.
6. [`traceability-matrix.md`](traceability-matrix.md) — требование, статус и где лежит подтверждение.

## Для инженерного разбора

- [`domain-assumptions.md`](domain-assumptions.md) — допущения модели.
- [`core-compat.md`](core-compat.md) — закреплённый коммит SynAPS и вызовы, которыми пользуется пакет.
- [`SYNAPS_REPAIRFLOW_MVP_SKELETON.md`](SYNAPS_REPAIRFLOW_MVP_SKELETON.md) — устройство и план MVP.
- [`adr/0002-dag-over-chain-kernel.md`](adr/0002-dag-over-chain-kernel.md) — сходящаяся карта собирается в цепочки для ядра.
- [`adr/0004-exchange-pool-ledger.md`](adr/0004-exchange-pool-ledger.md) — обменный фонд считается книгой остатков.
- [`adr/0005-inspection-rewrites-the-card.md`](adr/0005-inspection-rewrites-the-card.md) — дефектовка замораживает уже выданные слоты.
- [`literature-2026.md`](literature-2026.md) — обзор работ и что ещё нужно для статьи.
- [`benchmark-protocol.md`](benchmark-protocol.md) — как повторять синтетическое сравнение.
- [`atc-baseline-contract.md`](atc-baseline-contract.md) — локальное правило ATC и где оно кончается.
- [`sbom-and-provenance.md`](sbom-and-provenance.md) — что покрывает опись состава и чего в ней нет.
- [`threat-model.md`](threat-model.md) — граница автономной установки.
- [`data-mapping-1c-toir.md`](data-mapping-1c-toir.md) — карта полей, не интеграция.

## Для пилота и жюри

- [`../APPLICATION.md`](../APPLICATION.md) — текст заявки.
- [`jury-demo.md`](jury-demo.md) — что говорить на показе. Сводка чисел — [`submission-facts.md`](submission-facts.md). Папку этих страниц собирает `python tools/pack_submission.py`.
- [`pilot-protocol.md`](pilot-protocol.md) — теневой протокол на 90 дней.
- [`pilot-kpi-template.md`](pilot-kpi-template.md) — определения показателей, без придуманных результатов.
- [`operator-decision-log.md`](operator-decision-log.md) — запись решения человека. Писатель — `repairflow decide`.
- [`osint-and-pilot-gates.md`](osint-and-pilot-gates.md) — открытые источники и что нужно для входа.
- [`release-checklist.md`](release-checklist.md) — лабораторный выпуск и подача на пилот — разные ворота.
- [`adr/0003-release-boundary.md`](adr/0003-release-boundary.md) — теневой план не является командой системе управления.

## Как устроена работа с текстом

- [`documentation-audit.md`](documentation-audit.md) — сверка публичных страниц с командами. Соседние репозитории дали устройство страницы, не текст.
- [`AI_USE.md`](AI_USE.md) — где в разработке мог помочь автомат и почему его вывод не доказательство.
- [`../SECURITY.md`](../SECURITY.md) — куда сообщать об уязвимости.
- [`BANNED_CLAIMS.txt`](BANNED_CLAIMS.txt) — фразы, которых не должно быть в публичном заявлении.
- [`../LICENSES.md`](../LICENSES.md) — лицензии прямых зависимостей.

Утверждение можно публиковать, когда на месте источник, ревизия, вход, настройка решателя, вывод нотариуса и знаменатель. Иначе это допущение, гипотеза или пункт плана.
