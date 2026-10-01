# Limitations / non-claims

1. Synthetic fixtures are not SVARZ data and not a Mosgortrans dump.
2. No EAM / ERP / CMMS / SCADA integration.
3. No vehicle pull-out, metro night windows, e-bus charging, or road routing.
4. No labour-law rostering or ТК РФ certification.
5. GREED, FIFO, ALNS, RHC are not optimal.
6. Checker proves declared hard constraints, not MUS/IIS and not economic effect.
   A deletion-minimal set of operation ids explains one domain code. It is not an MUS or an IIS.
7. ISO 16290 TRL 4 (laboratory). Not TRL 5/6, not a paid pilot.
8. Do not write “used by the Department of Transport” or “cuts repair time by X%”.
9. A soft `due_date` miss is the KPI `DUE_MISSED`. A hard finish is
   `Job.deadline` (`DEADLINE_MISSED`) or `Operation.latest_finish`
   (`WINDOW_BROKEN`).
10. Spares remain a blocking availability check. The exchange pool is a separate
    stock ledger (`EXCHANGE_POOL_STOCKOUT`, hard only when `pool.hard` is true).
    `repairflow inspect` inserts one revealed branch and keeps every already issued slot.
    It does not yet model `POST_DOWN`, `PART_DELAY`, or a catalogue of route variants.
11. `optimal` does not mean “optimal repair plan” when the compiler changed the card.
    The report scope is the compiled chain/windows. More than one fixpoint iteration
    caps the claim at `verified`.
12. CP-SAT is refused above `CPSAT_OPS_CAP` (80 operations in this lab build).
