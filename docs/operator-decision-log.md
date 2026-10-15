# Журнал решения оператора

Решатель отдаёт кандидата. Человек его принимает, правит или отвергает. RepairFlow пишет это решение в JSONL, к которому можно только дописывать, рядом с пакетом доказательств. Журнал — запись для разбора. Сам он план не утверждает.

## Форма записи

Новый журнал — цепочка версии 2. Каждую строку проверяет `repairflow.decision_log.DecisionEvent`, и в ней есть `prev_hash` и `event_hash`. Первый `prev_hash` — 64 нуля. `event_hash` — SHA-256 канонического JSON всех остальных полей. Журнал, записанный до цепочки, без обоих полей, — `legacy`. Файл, где смешаны оба вида, — ошибка. `legacy`-журнал продолжать нельзя.

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

Событие и оба хеша плана проверяются до записи. У метки времени обязан быть часовой пояс, дальше она приводится к UTC. Для `accepted_with_edits` нужен `edit_summary`. Для `rejected` и `manual_fallback` нужна `reason`.

## Цепочка и сохранность

`append_decision` берёт эксклюзивный файл блокировки (`O_CREAT|O_EXCL`) рядом с журналом, с тайм-аутом. Чужую блокировку он не удаляет. После дописывания сбрасывает буфер и делает `fsync` файла, затем `fsync` каталога, если система это позволяет.

`repairflow log verify LOG [--head HASH]` пересчитывает цепочку. Без `--head` укороченный файл, который остаётся допустимым префиксом, проходит проверку. Если хеш вершины хранится отдельно, пропавший хвост — ошибка. Изменённое поле или переставленные строки — ошибка. Переписанный хвост с новой опубликованной вершиной не обнаруживается: журнал не подписан.

## Проверенное решение

`repairflow decide` читает файл задачи и файл результата, проверяет `verify_plan_hashes` и отказывает в `accepted` и `accepted_with_edits`, если `exit_code` не 0.

```text
repairflow decide --problem P --result R --accept --operator-code op-shadow-01 --log L
repairflow decide --problem P --result R --accept-with-edits "moved one operation" --operator-code op-shadow-01 --log L
repairflow decide --problem P --result R --reject --reason "hard notary" --operator-code op-shadow-01 --log L
repairflow log verify L --head <event_hash>
repairflow log stats L
```

`log stats` печатает `acceptance_rate`, `edit_rate` и частые причины отказа. `operator_code` не печатается. Причина — текст оператора; имя, спрятанное внутри, команда не ищет.

`tools/append_decision.py` открывает файлы задачи и результата, сверяет хеши и не записывает `accepted` при ненулевом коде выхода. Хеши с командной строки не принимаются.

## Форма записи до цепочки

Каждую историческую строку без полей цепочки по-прежнему проверяет `DecisionEvent`:

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
  "rollback_reference": ""
}
```

## Только дописывать

`append_decision(path, event)` дописывает одну каноническую строку JSONL:

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

Перед дописыванием RepairFlow проверяет каждую уже лежащую строку. Кривая, подправленная, пустая или не подходящая схеме строка останавливает запись: испорченную историю программа не продолжает. `read_decision_log(path)` делает ту же полную проверку.

Из оболочки:

```text
python tools/append_decision.py \
  --log out/decisions.jsonl \
  --problem out/repair-site-mvp.json \
  --result out/greed.json \
  --operator-code op-shadow-01 \
  --decision accepted
```

## Что сюда не класть

`operator_code` — псевдоним в одну строку. Библиотека отвергает фамилии, строки, похожие на почту, числовые табельные номера и подстановку перевода строки. Имена, табельные номера, почту и другие личные данные в пакет плана не кладут. Соответствие псевдонима человеку остаётся в системе, которой управляет заказчик.

Журнал не решает, допустим ли план, не меняет `verified_feasible` и сам по себе не создаёт заявления о заказчике, пилоте, производстве, безопасности, экономии или оптимальности. Ссылка на откат — это указатель, который дал оператор, на внешнюю контролируемую запись.
