# Licenses of the runtime pins

RepairFlow itself is MIT. The solver stack is pulled in by the pinned SynAPS commit.

| Component | Version pin | License |
| --- | --- | --- |
| synaps-repairflow | 0.1.0 | MIT |
| synaps | git `f939727cd9369fd9b36438bfac7198f0c39c6d3b` | MIT |
| pydantic | `>=2.9` | MIT |
| ortools | `==9.15.6755` | Apache-2.0 |

OR-Tools is pinned because 9.12 had false `INFEASIBLE` reports. The kernel constraint `ortools>=9.10` is not left floating in this repository.
