# OSINT and pilot gates, 2026-09-30

## Verified public signals

- FTIM's [pilot program](https://ftim.ru/pilotirovanie/) describes testing on Moscow Transport infrastructure with internal business customers and asks for a product ready for business-customer testing, a measurable hypothesis, and a pilot feasible in 90 days. FTIM's home page says applications are reviewed individually, with a stated response window of up to 14 calendar days.
- The official [SВАРЗ profile](https://www.mosgortrans.ru/about/branches/filial-sokolnicheskii-vagonoremontno-stroitelnyi-zavod-svarz-gup-mosgortrans/) confirms the plant repairs transport components and has a specialized coating-recovery area. Official 2025 communications report 550+ employees, but neither source proves the existence of an Excel-based planning process or a confirmed RepairFlow sponsor.
- The [MIC pilot page](https://i.moscow/pilot) states a recommended TRL of at least 6, a legal entity in Moscow, rights to the relevant intellectual property, and a recommended pilot duration of up to three months. The [grant page](https://i.moscow/pilot/grant) currently marks grant applications closed.
- Current research supports a transparent constraint-programming position rather than an AI claim: aircraft line-maintenance work has been modeled as an RCPSP extension with precedence, deadlines, resource availability, lexicographic objectives, and real-data evaluation ([Sciau et al., 2024](https://doi.org/10.1016/j.jairtraman.2024.102537)); industrial workforce scheduling research shows MUS/MCS-style explanations are practical for disrupted schedules ([Bleukx et al., CP 2025](https://doi.org/10.4230/LIPIcs.CP.2025.6)).

## Required pilot framing

Use: **offline, shadow-only decision support for one repair contour, with synthetic or anonymized data until a data agreement exists**. Measure schedule feasibility, replanning latency, manual edits, tardiness, resource utilization, and operator acceptance against the current baseline. Never claim deployment at SВАРЗ, economic savings, TRL 6, or customer pain without primary evidence.

## Submission checklist

- legal entity or IP owner and rights chain
- named process owner and data owner
- one signed data slice and anonymization rules
- baseline export and KPI definitions
- 90-day protocol with rollback to current manual/EAM process
- offline threat model and installation package
- reproducible evidence bundle with exact commit, solver version, seed, input hash, and checker output
