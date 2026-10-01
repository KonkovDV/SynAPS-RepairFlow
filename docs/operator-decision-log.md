# Operator decision log contract

The solver emits a candidate. A person accepts, edits, or rejects it. RepairFlow records that decision as append-only JSONL next to the evidence bundle. The log is an audit record, not an automatic approval mechanism.

## Record shape

Each line is validated by `repairflow.decision_log.DecisionEvent`:

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

The event and both hashes are validated before writing. Timestamps must include a timezone and are normalized to UTC. `accepted_with_edits` requires `edit_summary`; `rejected` and `manual_fallback` require `reason`.

## Append-only behavior

Use `append_decision(path, event)` to append one canonical JSONL record:

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

Before appending, RepairFlow validates every existing line. A malformed, tampered, blank, or schema-invalid line stops the append instead of extending a compromised history. `read_decision_log(path)` performs the same full validation.

For a shell-facing entry point:

```text
python tools/append_decision.py \
  --log out/decisions.jsonl \
  --operator-code op-shadow-01 \
  --instance-id instance-code \
  --input-hash <sha256> \
  --result-hash <sha256> \
  --decision accepted
```

## Privacy and scope

`operator_code` is a pseudonymous single-line code. The library rejects names, email-shaped values, numeric personnel identifiers, and newline injection. Do not store names, personnel numbers, email addresses, or other personal data in the planning bundle. Keep any identity mapping in the customer's controlled system.

The log does not decide whether a plan is feasible, does not modify `verified_feasible`, and does not create a customer, pilot, production, safety, savings, or optimality claim. Rollback references are operator-provided pointers to an external controlled record.
