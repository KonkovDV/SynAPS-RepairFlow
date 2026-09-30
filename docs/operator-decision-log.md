# Operator decision log contract

The system generates a candidate plan; a qualified operator decides whether to accept, edit, or reject it. The decision log is append-only JSONL stored with the evidence bundle.

Minimum record:

```json
{
  "event_id": "uuid",
  "timestamp": "2026-09-30T12:00:00Z",
  "operator_code": "operator-pseudonym",
  "instance_id": "instance-code",
  "input_hash": "sha256",
  "result_hash": "sha256",
  "decision": "accepted|accepted_with_edits|rejected|manual_fallback",
  "edit_summary": "short description or empty string",
  "reason": "required for rejection or fallback",
  "rollback_reference": "ticket or record reference"
}
```

Do not store names, personnel numbers, or other personal data in the planning bundle. Keep the identity mapping in the customer's controlled system.
