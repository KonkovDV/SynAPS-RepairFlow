# Pilot KPI template

Do not fill these with synthetic results. Define the denominator and baseline with the process owner before pilot execution.

| KPI | Baseline definition | Candidate definition | Target / decision rule |
|---|---|---|---|
| Hard-constraint violations | Count in the current plan | Count after independent check | Zero for accepted candidate |
| Operation coverage | Scheduled operations / eligible operations | Same denominator | 100% or explicit manual fallback |
| Replanning latency | Time from disruption to manual plan | Wall-clock candidate generation + check | Agreed threshold |
| Manual edits | Count and minutes per plan | Operator edits after candidate | Track, do not assume reduction |
| Tardiness | Weighted or unweighted, agreed in advance | Same measure | Compare with confidence interval |
| Resource utilization | Agreed post/crew denominator | Same definition | Interpret with throughput and safety |
| Operator acceptance | Accepted / reviewed candidates | Same review protocol | Qualitative and quantitative |

A pilot result is valid only if the data slice, time window, exclusions, and operator protocol are archived with the evidence bundle.
