# SBOM and provenance gate

A pilot package should include a machine-readable SBOM and a provenance manifest. The current repository records the SynAPS commit and input/config/result hashes; it does not yet claim a complete transitive hash lock or signed attestation.

Required release fields:

- source commit and repository URL;
- Python and operating-system versions;
- complete dependency names, versions, licenses, and hashes;
- SynAPS commit and OR-Tools version;
- build timestamp in UTC;
- input, configuration, and result SHA-256 values;
- benchmark preset, seed, solver configuration, time limit, and status;
- checker version and violation count;
- signature or approved artifact-integrity mechanism.

Until this gate is implemented, describe the package as a reproducible lab artifact, not a certified or supply-chain-attested deployment.
