# 1C:ТОИР / EAM mapping guide

This is a mapping template, not a claim of an existing integration.

| Source concept | RepairFlow field | Required treatment |
|---|---|---|
| Repair order | `jobs[].id`, `external_ref` | Replace personal identifiers with stable pseudonyms |
| Equipment or unit | `jobs[].asset_code`, `unit_type` | Preserve only the minimum needed for eligibility |
| Operation / routing step | `operations[]` | Keep deterministic sequence and predecessor |
| Work centre / post | `work_centers[]` | Include capability and calendar |
| Employee group | `crews[]` | Use skill codes and anonymized IDs |
| Tool / fixture | `aux_resources[]` | Include capacity and calendar |
| Material / spare | `spares[]` | Declare availability and quantity |
| Shift calendar | `calendars[]` | Convert to UTC with source timezone in manifest |

Before a customer pilot, require a signed field-level data contract, sample extract, timezone definition, anonymization procedure, and reconciliation report against the source system.
