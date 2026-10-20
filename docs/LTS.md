# CloudMesh 4.1.x LTS Policy

CloudMesh `4.1.2` is the first published 4.x release and the supported
Long-Term Support (LTS) artifact. This policy defines what the LTS promise
covers, how patches are released, and what is deliberately out of scope.

## Support window

| Item | Value |
| --- | --- |
| LTS line | `4.1.x` |
| First supported release | `4.1.2` |
| Support starts | 2026-10-20 |
| Support ends | 2027-10-20 |
| Patch cadence | As needed for critical and high-severity fixes |
| Feature backports | None |

The window is 12 months from the first published release. When the window
ends, upgrade to the current feature line. A new LTS line is announced
separately; it does not extend this one silently.

## Supported platforms

- **Python:** 3.11, 3.12, and 3.13.
- **Controller:** Windows, Linux, FreeBSD, OpenBSD, and NetBSD.
- **Node agent:** Linux and the BSD family.
- **REST API:** Loopback only (`127.0.0.1`). Remote access is through an SSH
  tunnel; cleartext external binding is not supported.

Python 3.10 reached end of life in October 2026. Supporting it for the full
LTS window would promise security patches for an interpreter that no longer
receives them, so `4.1.2` requires Python 3.11 or newer.

## Release channel

CloudMesh is distributed through **GitHub Releases** only. The `cloudmesh`
name on PyPI belongs to a different project; do not install it from PyPI.

- Release wheels and sdists are attached to the GitHub release.
- `SHA256SUMS` is published beside the artifacts.
- A CycloneDX SBOM is attached.
- GitHub build-provenance attestations are attached.
- `cm update --pip` installs a verified GitHub release wheel and refuses a
  missing checksum or a digest mismatch.

Install and upgrade instructions live in `README.md` and
`docs/UPGRADING.md`.

## Patch policy

Only security fixes and release-blocking regressions enter `4.1.x` after
`4.1.2`. New features, UI changes, and protocol changes wait for the next
feature line.

A patch release must include:

- a failing regression test for the defect;
- a green full suite on Windows, Linux, and the BSD VM;
- a changelog entry;
- the same checksum, SBOM, and attestation pipeline as `4.1.2`.

## Severity definitions

The release gate is **zero open P0 or P1 defects**.

### P0

A defect that, in a supported configuration, causes any of:

- remote code execution;
- authentication or authorization bypass;
- exposure of a secret or private key;
- irreversible data loss or corruption;
- compromise of the release supply chain.

### P1

A defect that causes any of:

- bypass of a documented security control, with a workaround available;
- a major documented feature that does not work;
- a failed upgrade or migration from a supported baseline;
- a crash on a supported platform;
- a release artifact that cannot be installed or verified.

### P2 and below

P2 covers limited-impact bugs with a workaround. P3 covers cosmetic issues.
Neither blocks the release; both are recorded in the release checklist.

## Known limitations

These are accepted risks, not hidden defects:

- **Node protocol.** The node agent uses a shared auth key, optional TLS, and
  optional SPA. The protocol is not changed in `4.1.x`. Without TLS, a network
  observer can read traffic. The controller cannot distinguish a wrong key
  from an unreachable node; authentication failures are recorded on the node.
- **REST API.** The API is loopback-only and speaks HTTP. A local process with
  the API key can call it. Remote access requires an SSH tunnel.
- **`docker exec`.** The operator supplies the command; that is the feature.
  The container is the trust boundary. It is not a CloudMesh shell injection.
- **Windows secret permissions.** POSIX `0600` is not meaningful on Windows.
  Secret files rely on the per-user profile ACL. Do not install CloudMesh in a
  shared, world-readable directory.

## Reporting a vulnerability

Use the process in `SECURITY.md`. Do not open a public issue for a suspected
P0 or P1. Include the version, platform, reproduction steps, and whether the
issue is already public.
