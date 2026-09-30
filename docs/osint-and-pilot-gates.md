# OSINT and pilot gates, 2026-09-30

## Verified public signals

- FTIM's [pilot program](https://ftim.ru/pilotirovanie/) describes testing on Moscow Transport infrastructure with internal business customers and asks for a product ready for that testing, a measurable hypothesis, and a pilot feasible in 90 days. Applications are reviewed individually.
- The official [SVARZ profile](https://www.mosgortrans.ru/about/branches/filial-sokolnicheskii-vagonoremontno-stroitelnyi-zavod-svarz-gup-mosgortrans/) confirms the plant repairs transport components. That page does not establish an Excel planning process or a RepairFlow sponsor.
- The [MIC pilot page](https://i.moscow/pilot) states a recommended TRL of at least 6, a legal entity in Moscow, rights to the relevant intellectual property, and a recommended pilot of up to three months. RepairFlow declares TRL 4. The [grant page](https://i.moscow/pilot/grant) has marked grant applications closed.
- Published scheduling work supports a constraint-programming position: Sciau et al., 2024, [DOI 10.1016/j.jairtraman.2024.102537](https://doi.org/10.1016/j.jairtraman.2024.102537); Bleukx et al., CP 2025, [DOI 10.4230/LIPIcs.CP.2025.6](https://doi.org/10.4230/LIPIcs.CP.2025.6).

## Required framing

Use offline, shadow-only decision support for one repair contour, on synthetic or anonymized data, until a data agreement exists. Measure feasibility, replanning latency, manual edits, tardiness, resource use, and operator acceptance against an agreed baseline.

## Submission checklist

- legal entity or IP owner, and the rights chain
- named process owner and data owner
- one signed data slice and anonymization rules
- baseline export and KPI definitions
- 90-day protocol with rollback to the current process
- offline threat model and the installation package
- evidence bundle with commit, solver version, seed, input hash, and checker output
