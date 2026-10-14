# Журнал решения оператора

Решатель отдаёт кандидата. Человек его принимает, правит или отвергает. RepairFlow пишет это решение в JSONL, к которому можно только дописывать, рядом с пакетом доказательств. Журнал — запись для разбора. Сам он план не утверждает.

## Форма записи

Каждую строку проверяет `repairflow.decision_log.DecisionEvent`:

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

Событие и оба хеша проверяются до записи. У метки времени обязан быть часовой пояс, дальше она приводится к UTC. Для `accepted_with_edits` нужен `edit_summary`. Для `rejected` и `manual_fallback` нужна `reason`.

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
  --operator-code op-shadow-01 \
  --instance-id instance-code \
  --input-hash <sha256> \
  --result-hash <sha256> \
  --decision accepted
```

## Что сюда не класть

`operator_code` — псевдоним в одну строку. Библиотека отвергает фамилии, строки, похожие на почту, числовые табельные номера и подстановку перевода строки. Имена, табельные номера, почту и другие личные данные в пакет плана не кладут. Соответствие псевдонима человеку остаётся в системе, которой управляет заказчик.

Журнал не решает, допустим ли план, не меняет `verified_feasible` и сам по себе не создаёт заявления о заказчике, пилоте, производстве, безопасности, экономии или оптимальности. Ссылка на откат — это указатель, который дал оператор, на внешнюю контролируемую запись.
