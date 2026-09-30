# 1C:ТОИР / EAM mapping guide

This is a field map. It is not an integration and not a claim that a customer extract exists.

| Source concept | RepairFlow field | Treatment |
|---|---|---|
| Repair order | `jobs[].id`, `jobs[].external_ref` | Replace personal identifiers with stable pseudonyms |
| Equipment or unit | `jobs[].asset_code`, `jobs[].unit_type` | Keep the minimum needed for eligibility and the exchange pool |
| Operation / routing step | `operations[]` | Keep duration, skills, posts, setup state, and `predecessor_ids` |
| Work centre / post | `work_centers[]` | Capability and calendar. An empty `eligible_work_center_ids` is invalid |
| Employee group | `crews[]` | Skill codes and anonymized ids. A calendar with no windows is unavailable |
| Tool / fixture | `aux_resources[]` | Capacity and calendar. The kernel aux pool has no shift calendar; the domain checker does |
| Material / spare | `spares[]`, `exchange_pools[]` | Blocking spares stay an availability check. Exchange stock is a dated ledger |
| Shift calendar | `calendars[]` | UTC instants. Record the source timezone in the accompanying manifest |
| Provenance | `data_provenance` | `synthetic` until a signed extract says otherwise |

Before a customer pilot, require a signed field-level contract, a sample extract, a timezone definition, an anonymization procedure, and a reconciliation against the source system.
