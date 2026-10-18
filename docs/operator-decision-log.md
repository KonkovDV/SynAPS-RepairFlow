# Журнал решений оператора

Расчётное ядро и нотариус формируют проверенный вариант графика, но окончательное решение всегда принимает человек: принять план в работу, принять с ручными поправками, отклонить или остаться на ручном графике. RepairFlow записывает каждое такое решение в неизменяемый журнал формата JSONL рядом с файлами задачи и расписания. Сам по себе журнал не заменяет проверку нотариуса и не меняет поле `verified_feasible`.

## Структура записи и версия цепочки

Актуальный формат журнала — хеш-цепочка версии `v2`. Каждая строка проходит валидацию модели `repairflow.decision_log.DecisionEvent` и содержит поля `prev_hash` и `event_hash`:

- у первой записи в файле поле `prev_hash` состоит из `64` нулей;
- поле `event_hash` равно SHA-256 от канонического JSON всех остальных полей записи (включая `prev_hash`);
- исторические файлы без полей `prev_hash` и `event_hash` распознаются как `legacy` — их можно прочитать и проверить по схеме, но дописывать новые записи в `legacy`-файл или смешивать оба формата в одном файле запрещено.

```json
{
  "event_id": "uuid",
  "timestamp": "2026-09-30T12:00:00Z",
  "operator_code": "op-shadow-01",
  "instance_id": "instance-code",
  "input_hash": "sha256",
  "result_hash": "sha256",
  "decision": "accepted|accepted_with_edits|rejected|manual_fallback",
  "edit_summary": "",
  "reason": "required for rejection or fallback",
  "rollback_reference": "",
  "prev_hash": "64 hex or 64 zeroes",
  "event_hash": "sha256"
}
```

Метка времени `timestamp` обязана содержать часовой пояс и при сохранении приводится к UTC. Для решения `accepted_with_edits` обязательно непустое описание правок `edit_summary`, а для `rejected` и `manual_fallback` — причина `reason`.

## Защита от параллельной записи, обрезки и подмены

Перед добавлением новой записи функция `append_decision` проверяет все уже существующие строки файла и захватывает эксклюзивный файл блокировки (`O_CREAT | O_EXCL`) с тайм-аутом, не удаляя чужую активную блокировку. После записи буфер принудительно сбрасывается на диск (`fsync` файла и, если поддерживает ОС, каталога).

Команда `repairflow log verify LOG [--head HASH]` пересчитывает всю цепочку от первой записи:

- изменение любого поля внутри строки ломает `event_hash`, а перестановка или удаление строки в середине файла ломает сцепку `prev_hash`;
- если проверяющему известна сохранённая отдельно вершина `--head`, обрезка хвоста файла также обнаруживается;
- чтобы защититься от полной перезаписи хвоста с пересчётом новых хешей, команда `repairflow log witness LOG --key-file KEY` вычисляет HMAC-SHA256 текущей вершины внешним секретным ключом оператора, а `repairflow log verify LOG --witness HEX --key-file KEY` сверяет этот HMAC. Секретный ключ хранится у оператора вне репозитория (это механизм внешнего свидетеля журнала, а не подпись релизного пакета).

## Команды работы с журналом

Команда `repairflow decide` (как и скрипт `tools/append_decision.py`) открывает файлы задачи и результата, пересчитывает их криптографические отпечатки через `verify_plan_hashes` и запрещает запись решений `accepted` и `accepted_with_edits`, если код выхода плана отличен от нуля:

```text
repairflow decide --problem P --result R --accept --operator-code op-shadow-01 --log L
repairflow decide --problem P --result R --accept-with-edits "moved one operation" --operator-code op-shadow-01 --log L
repairflow decide --problem P --result R --reject --reason "hard notary" --operator-code op-shadow-01 --log L
repairflow log verify L --head <event_hash>
repairflow log witness L --key-file KEY
repairflow log verify L --witness HEX --key-file KEY
repairflow log stats L
```

Команда `repairflow log stats` выводит долю принятых (`acceptance_rate`) и скорректированных (`edit_rate`) планов, а также распределение причин отказа без вывода поля `operator_code`.

Вызов через вспомогательный скрипт:

```text
python tools/append_decision.py \
  --log out/decisions.jsonl \
  --problem out/repair-site-mvp.json \
  --result out/greed.json \
  --operator-code op-shadow-01 \
  --decision accepted
```

Программный вызов из Python:

```python
from repairflow.decision_log import DecisionEvent, append_decision

event = DecisionEvent(
    operator_code="op-shadow-01",
    instance_id="instance-code",
    input_hash="a" * 64,
    result_hash="b" * 64,
    decision="accepted",
)
append_decision("out/decisions.jsonl", event)
```

## Обезличивание и правила гигиены данных

Поле `operator_code` должно содержать обезличенный однострочный псевдоним (например, `op-shadow-01`). Валидатор отклоняет строки, похожие на ФИО, адреса электронной почты, чисто цифровые табельные номера и строки с управляющими символами. Таблица соответствия между псевдонимом и конкретным сотрудником остаётся во внутреннем контуре предприятия и в репозиторий или пакет плана не передаётся.
