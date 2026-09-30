# Release checklist

A laboratory release and a pilot submission are different gates. A checked item needs evidence in the repository or a named external document.

## Laboratory release

- [ ] `python tools/verify_lock.py` passes.
- [ ] Ruff, mypy, schema export, fast tests, demo, and the default benchmark pass.
- [ ] The evidence bundle records the SynAPS commit, Python version, OR-Tools version, platform, seed, input hash, config hash, and result hash.
- [ ] Every row marked `verified` has full operation coverage and an empty hard notary.
- [ ] Synthetic numbers name the preset, seed, solver, and commit.
- [ ] Public text avoids the phrases in `docs/BANNED_CLAIMS.txt`.
- [ ] The artifact is built from a clean commit.

## FTIM/MIC pilot submission

- [ ] Legal entity or IP owner is identified.
- [ ] Rights chain for the software and dependencies is documented.
- [ ] Named business owner, data owner, and information-security contact are confirmed.
- [ ] One repair contour, one baseline, one anonymized slice, and one measurable hypothesis are agreed.
- [ ] The protocol is shadow-only, offline, reversible, and limited to 90 days.
- [ ] Operator acceptance and rollback criteria are defined before the first run.
- [ ] The application says TRL 4.

## What a green benchmark is

A green synthetic benchmark is evidence about that fixture. It is not economic effect, customer pain, legal compliance, or production safety. Public information about SVARZ confirms a repair profile, not sponsorship.
