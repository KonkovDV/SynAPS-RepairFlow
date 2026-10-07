# Operator decision log contract

The solver emits a candidate. A person accepts, edits, or rejects it. RepairFlow records that decision as append-only JSONL next to the evidence bundle. The log is an audit record, not an automatic approval mechanism.

## Record shape

A new log is chain version 2. Each line is validated by `repairflow.decision_log.DecisionEvent` and carries `prev_hash` plus `event_hash`. The first `prev_hash` is 64 zeroes. `event_hash` is the SHA-256 of the canonical JSON of every other field. A log written before the chain, with neither field, is `legacy`. A file that mixes the two is an error. A legacy log cannot be extended.

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

The event and both plan hashes are validated before writing. Timestamps must include a timezone and are normalized to UTC. `accepted_with_edits` requires `edit_summary`; `rejected` and `manual_fallback` require `reason`.

## Chain and durability

`append_decision` takes an exclusive lock file (`O_CREAT|O_EXCL`) beside the log, with a timeout. It does not remove a lock it did not create. After the append it flushes and `fsync`s the file, then `fsync`s the directory when the operating system allows it.

`repairflow log verify LOG [--head HASH]` recomputes the chain. Without `--head`, a shortened file that is still a valid prefix verifies. With the tip hash stored elsewhere, a missing tail fails. Changing a field or swapping two lines fails. Rewriting the suffix and publishing a new tip is not detected: the log is not signed.

## Checked decision

`repairflow decide` reads the problem file and the result file, checks `verify_plan_hashes`, and refuses `accepted` or `accepted_with_edits` when `exit_code` is not 0.

```text
repairflow decide --problem P --result R --accept --operator-code op-shadow-01 --log L
repairflow decide --problem P --result R --accept-with-edits "moved one operation" --operator-code op-shadow-01 --log L
repairflow decide --problem P --result R --reject --reason "hard notary" --operator-code op-shadow-01 --log L
repairflow log verify L --head <event_hash>
repairflow log stats L
```

`log stats` prints `acceptance_rate`, `edit_rate`, and the top rejection reasons. It does not print `operator_code`. A reason string is operator text; the command does not detect a name hidden inside it.

`tools/append_decision.py` remains a wrapper around `append_decision`. It seals the chain. It does not open the problem or the result, so it cannot apply the exit-code rule.

## Record shape before the chain

Each historical line without the chain fields is still validated by `DecisionEvent`:

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
