# Release checklist

This checklist separates a reproducible laboratory release from a pilot submission. A checked item requires evidence in the repository or a named external document.

## Laboratory release

- [ ] `python tools/verify_lock.py` passes.
- [ ] Ruff, mypy, schema validation, fast tests, slow tests, demo, and benchmark pass.
- [ ] Exact SynAPS commit, Python version, solver version, platform, seed, input hash, config hash, and result hash are recorded.
- [ ] Independent checker has zero hard violations and full operation coverage for every claim marked verified.
- [ ] Synthetic numbers identify preset, seed, solver, commit, and are not presented as customer effect.
- [ ] No public claim says AI, optimal, production, deployed, or savings unless the evidence bundle proves that exact claim.
- [ ] Release artifact is built from a clean commit and its hashes are archived.

## FTIM/MIC pilot submission

- [ ] Legal entity or IP owner is identified.
- [ ] Rights chain for the software and dependencies is documented.
- [ ] Named business owner, data owner, and information-security contact are confirmed.
- [ ] One repair contour, one baseline, one anonymized data slice, and one measurable hypothesis are agreed.
- [ ] Pilot protocol is shadow-only, offline, reversible, and limited to 90 days.
- [ ] Operator acceptance and rollback criteria are defined before the first run.
- [ ] The application says TRL 4 if no evidence supports TRL 6.

## Explicitly not release gates

A green synthetic benchmark is not proof of economic effect, customer pain, legal compliance, or production safety. Public information about SVARZ confirms its repair profile, not sponsorship or access to operational data.
