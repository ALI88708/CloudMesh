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


def test_the_release_workflow_checks_out_before_it_downloads_the_artifacts():
    """The step order decides whether the release has any assets at all.

    `actions/checkout` runs `git clean -ffdx`, which deletes the untracked
    `artifacts/` directory that `actions/download-artifact` writes. With the
    download first, the checkout deleted the artifacts and the release was
    published with no wheel in it -- which is exactly what happened to
    v3.4.0, whose release carries only the installer scripts.
    """
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    publish = workflow.split("  publish:", 1)[1]
    checkout = publish.index("actions/checkout@v4")
    download = publish.index("actions/download-artifact@v4")
    assert checkout < download, (
        "checkout must run before download-artifact, or the checkout's "
        "git clean deletes the downloaded artifacts"
    )


def test_the_release_workflow_builds_the_tagged_commit():
    """A manual dispatch must build the tag, not the default branch.

    The workflow is also run by hand to re-publish a release. Without an
    explicit `ref`, that path checks out the default branch, and the
    artifacts would be built from code the tag does not contain.
    """
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert workflow.count("ref: ${{ inputs.tag || github.ref }}") == 2

