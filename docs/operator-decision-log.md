# Operator decision log contract

The solver emits a candidate. A person accepts, edits, or rejects it. This page is the record shape. RepairFlow does not yet append the log.

Store append-only JSONL next to the evidence bundle:

```json
{
  "event_id": "uuid",
  "timestamp": "2026-09-30T12:00:00Z",
  "operator_code": "operator-pseudonym",
  "instance_id": "instance-code",
  "input_hash": "sha256",
  "result_hash": "sha256",
  "decision": "accepted|accepted_with_edits|rejected|manual_fallback",
  "edit_summary": "",
  "reason": "required for rejection or fallback",
  "rollback_reference": ""
}
```

Do not store names, personnel numbers, or other personal data in the planning bundle. Keep the identity mapping in the customer's system.
