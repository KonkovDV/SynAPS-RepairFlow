# SBOM and provenance

`repairflow.sbom.build_sbom` writes a CycloneDX 1.5 document for the direct runtime components: `synaps-repairflow`, `synaps`, `pydantic`, and `ortools`. OR-Tools must be `9.15.6755`. `tools/write_sbom.py` is the CLI. This is not a hash of every transitive wheel and not a signed attestation.

Each plan result stores `input_hash`, `config_hash`, and `result_hash`. The config payload includes a runtime manifest (Python, platform, RepairFlow version, SynAPS commit, OR-Tools, Pydantic). `repairflow check --verify-hashes` recomputes those hashes and exits 1 on a mismatch.

A pilot package that claims supply-chain attestation still needs:

- source commit and repository URL;
- complete dependency names, versions, licenses, and artifact hashes;
- build timestamp in UTC;
- benchmark preset, seed, solver, time limit, and status;
- a signature or another approved integrity mechanism.

Until that gate exists, call the package a reproducible laboratory artifact.
