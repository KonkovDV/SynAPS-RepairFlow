# SBOM and provenance

`repairflow.sbom.build_sbom` writes a CycloneDX 1.5 document for the direct runtime components: `synaps-repairflow`, `synaps`, `pydantic`, and `ortools`. OR-Tools must be `9.15.6755`. `tools/write_sbom.py` is the CLI.

The document now includes `runtime_binding` (`repairflow.runtime_binding.v1`). For every direct component, the binding records the installed version, every existing file advertised by the distribution metadata, the SHA-256 of each file, and a sorted aggregate `manifest_sha256`. The aggregate is computed from relative path plus file digest, so an unchanged installed tree can be checked offline without contacting a package index. The CycloneDX component properties repeat the aggregate hash and file count for table-oriented consumers.

This is an installed-distribution file manifest, not a wheel archive hash. It is not signed, it does not establish provenance of a downloaded artifact, and it does not replace license review or a complete transitive dependency inventory. Missing distributions are explicit as `absent`; distributions with no readable files are explicit as `empty` rather than silently treated as bound.

Each plan result stores `input_hash`, `config_hash`, and `result_hash`. The config payload includes a runtime manifest (Python, platform, RepairFlow version, SynAPS commit, OR-Tools, Pydantic). `repairflow check --verify-hashes` recomputes those hashes and exits 1 on a mismatch.

A pilot package that claims supply-chain attestation still needs:

- source commit and repository URL;
- complete dependency names, versions, licenses, and artifact hashes;
- wheel or source-artifact hash obtained before installation;
- build timestamp in UTC;
- benchmark preset, seed, solver, time limit, and status;
- a signature or another approved integrity mechanism.

Until that gate exists, call the package a reproducible laboratory artifact. No customer, production, safety, savings, sponsor, or optimality claim follows from this manifest.
