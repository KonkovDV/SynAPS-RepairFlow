# Как вносить изменения

## Перед запросом на слияние

Те же проверки, что в CI:

```bash
python tools/verify_schema.py
python tools/export_schemas.py
python -m ruff format --check src tests tools
python -m ruff check src tests tools
python -m mypy --strict src/repairflow
python -m pytest -q -m "not slow"
```

Медленный набор (`python -m pytest -q -m slow`) на запросе включает метка `slow`. Её ставят, когда трогают нотариус, планировщик, компилятор графа, привязку к ядру или кампании порчи.

## Что держит репозиторий

- **Пин ядра.** SynAPS подключается только полным SHA из 40 символов — в `pyproject.toml`, `requirements-lock.txt` и `src/repairflow/versions.py`. Ветку `main` ядра не указывают, каталог `synaps/` в дерево не копируют.
- **Нотариус отдельно.** `src/repairflow/checker.py` не импортирует `repairflow.adapter`, `repairflow.planner` и `synaps.solvers`. Проверку не ослабляют, чтобы план прошёл. Оракул `tests/oracle_minutes.py` под нотариус не подгоняют.
- **Слово `optimal`.** Только чистый `OPTIMAL` CP-SAT при пустом нотариусе и не больше чем одном проходе компилятора. Эвристика его не получает. Метка `compiled_windows` значит, что между отрезками были рёбра, и этот один проход не отменяет. Ядро этого пина доказывает цепочку без лага; лаг судит нотариус.
- **Подсказка и отчёт.** У каждого кода отказа есть русская `suggested_relaxation`. `repairflow report` не завершается нулём для файла, который только носит `domain_verified`. HTML экранирует текст плана.

## Тексты

- Фраз из `docs/BANNED_CLAIMS.txt` на публичных страницах нет. Следит `tests/test_banned_claims.py`.
- В `README.md` цифры живут только в таблице доказательств между метками `evidence`. Эту таблицу, `docs/submission-facts.md` и фразы между метками `attest` пишет `tools/attest.py` — отдельным запросом после зелёного push в `main`. Руками их не правят.
- Число на странице идёт вместе с ревизией, пресетом, зерном, решателем, выводом нотариуса и знаменателем.
- Относительные ссылки, якоря и таблицы команд и кодов в `README.md` сверяет `tests/test_doc_links.py`.

## Обновление пина ядра

1. Обновить SHA в трёх файлах.
2. Прогнать `python tools/verify_lock.py` и `python tools/verify_schema.py`.
3. Прогнать `pytest tests/test_pin_regression.py`, затем быстрый и медленный наборы.
4. Пересобрать `repairflow demo` и проверочные артефакты.

## Запрос на слияние

Изменения идут через запрос в `main`. Шаблон запроса спросит:

- синтетический пресет или сценарий;
- путь решателя: `GREED`, `FIFO`, `EDD`, `ATC`, `CPSAT-*` или `verify-plan`;
- что нотариус и регрессии зелёные.

Правила общения — [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Уязвимость присылают по [`SECURITY.md`](SECURITY.md), не открытой задачей.
