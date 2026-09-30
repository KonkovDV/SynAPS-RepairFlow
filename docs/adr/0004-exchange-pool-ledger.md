# ADR-0004. Exchange pool is a ledger, not a kernel pool

## Context

`AuxiliaryResource.pool_size` is how many units of a tool can be busy at the same
instant. An exchange pool is a stock: repaired units return when the card's
sinks finish, and fleet demand withdraws them at dated events. Encoding that
stock as `pool_size` answers a different question.

## Decision

`ExchangePool` lives on the domain problem. The ledger is

`stock(t) = initial + completions with end <= t − demand with at <= t`.

A completion is the latest sink of the job's DAG, and only if every sink is
assigned. `hard=true` makes `EXCHANGE_POOL_STOCKOUT` reject the plan (exit 2).
Otherwise the same code is a KPI and a feasible schedule stays `verified`.

## Consequences

Part ETA stays on `Spare.available_from` / `earliest_start`. The exchange pool
does not consume those rows.
