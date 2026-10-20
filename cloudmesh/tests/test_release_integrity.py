from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_release_workflow_publishes_checksums_sbom_and_attestation():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "SHA256SUMS" in workflow
    assert "cyclonedx" in workflow.lower()
    assert "attest-build-provenance" in workflow
    assert "attestations: write" in workflow
    assert "id-token: write" in workflow
    assert "artifacts/SHA256SUMS" in workflow
    assert "artifacts/sbom.cdx.json" in workflow
