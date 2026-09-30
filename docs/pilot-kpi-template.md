# Pilot KPI template

Leave these cells empty until a process owner defines the denominator and the baseline. Do not paste synthetic benchmark numbers here.

| KPI | Baseline definition | Candidate definition | Decision rule |
|---|---|---|---|
| Hard-constraint violations | Count in the current plan | Count after the independent checker | Zero before a candidate is accepted |
| Operation coverage | Scheduled operations / eligible operations | Same denominator | Full coverage, or an explicit manual fallback |
| Replanning latency | Time from disruption to a manual plan | Wall clock of candidate generation plus check | An agreed threshold |
| Manual edits | Count and minutes per plan | Edits after the candidate | Record them. Do not assume they fall |
| Tardiness | Measure agreed in advance | Same measure | Compare on the same window |
| Resource utilization | Agreed post and crew denominator | Same definition | Read it together with throughput |
| Operator acceptance | Accepted / reviewed candidates | Same review protocol | Both the rate and the written reasons |

A pilot result is valid only when the data slice, time window, exclusions, and operator protocol sit in the same archive as the evidence bundle.
