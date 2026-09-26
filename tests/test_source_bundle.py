"""Offline acceptance at real Git boundaries, using fictional documentation."""
import hashlib
import json
import subprocess

import pytest
import yaml

from notebooklm_mcp.doc_refresh.manifest import load_manifest
from notebooklm_mcp.doc_refresh.source_bundle import build_bundle, main, write_artifacts


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "C099_fictional"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", "Synthetic Test")
    git(root, "config", "user.email", "test@example.invalid")
    for name, text in {"README.md": "---\ntitle: Fictional\n---\n# Hello\n",
                       "CHANGELOG.md": "# Fictional history\n", "META.yaml": "version: 1\n",
                       "code.py": "pass\n", "10_docs/public.md": "Public fixture\n",
                       "10_docs/private/secret.md": "NEVER EXPORT\n"}.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    commit(root)
    return root


def commit(repo):
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "synthetic change")
    return git(repo, "rev-parse", "HEAD")


def test_pinned_blobs_ignore_dirty_untracked_and_unrelated_commits(repo):
    first = build_bundle(repo, "HEAD")
    (repo / "README.md").write_text("DIRTY BYTES")
    (repo / "PROJECT_PRIMER.md").write_text("UNTRACKED BYTES")
    assert build_bundle(repo, first.receipt["commit"]) == first
    git(repo, "restore", "README.md")
    (repo / "PROJECT_PRIMER.md").unlink()
    (repo / "code.py").write_text("print('unrelated')")
    commit(repo)
    second = build_bundle(repo, "HEAD")
    assert first.bundle == second.bundle
    assert first.receipt["commit"] != second.receipt["commit"]
    assert first.receipt["sources"] == second.receipt["sources"]
    (repo / "README.md").write_text("Changed source\n")
    commit(repo)
    third = build_bundle(repo, "HEAD")
    assert third.bundle.sha256 != first.bundle.sha256
    assert build_bundle(repo, first.receipt["commit"]) == first


def test_selected_bytes_have_blob_and_full_hash_provenance(repo):
    result = build_bundle(repo, "HEAD")
    assert result.receipt["source_count"] == 4
    assert "NEVER EXPORT" not in result.bundle.text
    assert "title: Fictional" in result.bundle.text
    for source in result.receipt["sources"]:
        data = subprocess.check_output(["git", "-C", str(repo), "cat-file", "blob", source["blob_oid"]])
        assert source["sha256"] == hashlib.sha256(data).hexdigest()
        assert source["blob_oid"] in result.bundle.text
    assert any(x["path"] == "10_docs/private/secret.md" for x in result.receipt["excluded"])
    assert result.receipt["publication"] == {"drive_document_id": None, "notebook_id": None}


def test_excluded_blob_is_never_read_and_directory_is_not_content(repo, monkeypatch):
    from notebooklm_mcp.doc_refresh import source_bundle as module
    forbidden = git(repo, "rev-parse", "HEAD:10_docs/private/secret.md")
    original = module._git
    def guarded(root, *args):
        assert not (args[:2] == ("cat-file", "blob") and args[2] == forbidden)
        return original(root, *args)
    monkeypatch.setattr(module, "_git", guarded)
    result = build_bundle(repo, "HEAD")
    assert all(s["path"] != "10_docs" for s in result.receipt["sources"])


def test_root_override_and_literal_brackets_survive_snapshot(repo, tmp_path):
    path = repo / "docs[1]/restricted.md"
    path.parent.mkdir()
    path.write_text("PRIVATE FIXTURE")
    commit(repo)
    manifest = load_manifest()
    manifest["repo_overrides"][repo.name] = {
        "extra_docs": [{"path": "docs[1]/restricted.md", "purpose": "fixture"}],
        "exclusions": [{"pattern": "RESTRICTED.md", "reason": "private fixture"}],
    }
    # Literal alias exclusion is filesystem-dependent; exact exclusion is universal.
    manifest["repo_overrides"][repo.name]["exclusions"].append(
        {"pattern": "restricted.md", "reason": "private fixture"})
    config = tmp_path / "manifest.yaml"
    config.write_text(yaml.safe_dump(manifest))
    result = build_bundle(repo, "HEAD", manifest_path=config)
    assert "PRIVATE FIXTURE" not in result.bundle.text
    link = tmp_path / "alias"
    link.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError, match="root"):
        build_bundle(link, "HEAD", manifest_path=config)
    with pytest.raises(ValueError, match="root"):
        build_bundle(repo / "10_docs", "HEAD")


def test_symlink_target_never_exported(repo):
    (repo / "10_docs/linked.md").symlink_to("private/secret.md")
    commit(repo)
    result = build_bundle(repo, "HEAD")
    assert "NEVER EXPORT" not in result.bundle.text
    assert any(x["path"] == "10_docs/linked.md" and "mode" in x["reason"]
               for x in result.receipt["excluded"])


@pytest.mark.parametrize("case", ["missing", "binary", "control", "directory"])
def test_invalid_selected_source_fails(repo, case):
    path = repo / "README.md"
    path.unlink()
    if case == "directory":
        path.mkdir()
        (path / "child").write_text("fixture")
    elif case == "binary":
        path.write_bytes(b"\xff")
    elif case == "control":
        path.write_bytes(b"bad\x00text")
    commit(repo)
    with pytest.raises(ValueError):
        build_bundle(repo, "HEAD")


def test_invalid_revision_is_not_an_option(repo):
    for revision in ["missing-ref", "--all", "HEAD:README.md"]:
        with pytest.raises(ValueError):
            build_bundle(repo, revision)


def test_batch_cli_idempotence_and_no_fake_remote_ids(repo, tmp_path, capsys):
    out = tmp_path / "artifacts"
    other = tmp_path / "C098_second"
    subprocess.run(["git", "clone", "-q", str(repo), str(other)], check=True)
    args = ["--repo", str(repo), "HEAD", "--repo", str(other), "origin/master", "--output", str(out)]
    # Default initial branch is host-configurable; pin the actual fetched ref.
    args[5] = "origin/" + git(repo, "branch", "--show-current")
    assert main(args) == 0
    one = capsys.readouterr().out
    files = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert main(args) == 0
    assert capsys.readouterr().out == one
    assert files == {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert json.loads(one)[0]["source_count"] == 4
    assert len(json.loads(one)) == 2
    # Validate the entire batch before writing any artifact.
    missing_out = tmp_path / "failure"
    assert main(["--repo", str(repo), "HEAD", "--repo", str(other), "bad-ref",
                 "--output", str(missing_out)]) == 1
    assert not missing_out.exists()


def test_artifact_conflict_refused(repo, tmp_path):
    result = build_bundle(repo, "HEAD")
    paths = write_artifacts(result, tmp_path / "out")
    paths["bundle"].write_text("tampered")
    with pytest.raises(ValueError, match="existing artifact"):
        write_artifacts(result, tmp_path / "out")


def test_moving_ref_during_capture_does_not_mix_revisions(repo, monkeypatch):
    from notebooklm_mcp.doc_refresh import source_bundle as module
    original = build_bundle(repo, "HEAD")
    real_git = module._git
    def moving(root, *args):
        result = real_git(root, *args)
        if args[0] == "ls-tree":
            (repo / "README.md").write_text("Concurrent commit\n")
            commit(repo)
        return result
    monkeypatch.setattr(module, "_git", moving)
    assert build_bundle(repo, "HEAD") == original


def test_replacement_objects_and_inherited_git_routing_cannot_change_content(repo, tmp_path, monkeypatch):
    original = build_bundle(repo, "HEAD")
    old = git(repo, "rev-parse", "HEAD:README.md")
    (repo / "README.md").write_text("Replacement\n")
    commit(repo)
    new = git(repo, "rev-parse", "HEAD:README.md")
    git(repo, "replace", old, new)
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nonexistent"))
    assert build_bundle(repo, original.receipt["commit"]) == original


def test_corrupted_blob_transport_refused(repo, monkeypatch):
    from notebooklm_mcp.doc_refresh import source_bundle as module
    original = module._git
    def altered(root, *args):
        return b"corrupt" if args[:2] == ("cat-file", "blob") else original(root, *args)
    monkeypatch.setattr(module, "_git", altered)
    with pytest.raises(ValueError, match="integrity"):
        build_bundle(repo, "HEAD")


def test_empty_or_invalid_manifest_fails_before_output(repo, tmp_path):
    manifest = load_manifest()
    manifest["exclusions"].append({"pattern": "**", "reason": "exclude everything"})
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest))
    with pytest.raises(ValueError, match="at least one"):
        build_bundle(repo, "HEAD", manifest_path=path)
    path.write_text("invalid: true\n")
    assert main(["--repo", str(repo), "HEAD", "--manifest", str(path),
                 "--output", str(tmp_path / "output")]) == 1
    assert not (tmp_path / "output").exists()


def test_no_notebook_mapping_bootstrap(repo, monkeypatch):
    from notebooklm_mcp.doc_refresh import manifest
    def forbidden(*args, **kwargs):
        pytest.fail("Offline bundling accessed notebook map")
    monkeypatch.setattr(manifest, "save_notebook_map", forbidden)
    build_bundle(repo, "HEAD")


def test_output_inside_repo_or_symlink_refused(repo, tmp_path):
    assert main(["--repo", str(repo), "HEAD", "--output", str(repo / "output")]) == 1
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        write_artifacts(build_bundle(repo, "HEAD"), link)


def test_quarantined_repo_refused_before_blob_read(repo):
    quarantined = repo.with_name("W007_fictional")
    repo.rename(quarantined)
    with pytest.raises(ValueError, match="Quarantined"):
        build_bundle(quarantined, "HEAD")
