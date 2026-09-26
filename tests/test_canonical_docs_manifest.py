"""
WOR-186: canonical_docs schema, exclusions, containment, synthetic fixtures.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import subprocess
from pathlib import Path

import pytest
import yaml

from notebooklm_mcp.doc_refresh import (
    ManifestError,
    discover_repo,
    is_excluded,
    load_manifest,
    manifest_content_hash,
    path_is_contained,
    validate_canonical_docs,
)
from notebooklm_mcp.doc_refresh.hashing import compute_all_hashes
from notebooklm_mcp.doc_refresh.models import Tier
from notebooklm_mcp.doc_refresh.schema import SCHEMA_ID
from notebooklm_mcp.doc_refresh.selection import glob_match

EMPTY_MAP = {"notebooks": {}, "sync_log": [], "config": {}}


@pytest.mark.parametrize("kind", ["case", "unicode", "symlink"])
@pytest.mark.parametrize("ancestor_alias", [False, True])
@pytest.mark.parametrize("entrypoint", ["discovery", "legacy"])
def test_repo_root_alias_cannot_bypass_overrides(
    tmp_path, monkeypatch, kind, ancestor_alias, entrypoint
):
    import unicodedata
    from notebooklm_mcp.sync_cli import discover_tier3_docs

    parent = tmp_path.resolve() / "parent"
    parent.mkdir()
    repo = parent / ("C099_Caf\u00e9" if kind == "unicode" else "C099_docs")
    repo.mkdir()
    repo = next(parent.iterdir())  # Use the actual directory-entry spelling.
    _write(repo / "README.md", "Fictional private notes")
    _write(repo / "CHANGELOG.md", "Fictional public history")
    if kind == "case":
        alias_name = repo.name.swapcase()
    elif kind == "unicode":
        form = "NFD" if repo.name == unicodedata.normalize("NFC", repo.name) else "NFC"
        alias_name = unicodedata.normalize(form, repo.name)
    else:
        alias_name = "linked_repo"
        (parent / alias_name).symlink_to(repo, target_is_directory=True)
    alias = parent / alias_name
    if alias.name == repo.name or not alias.exists() or not alias.samefile(repo):
        pytest.skip("requires filesystem spelling aliases")
    manifest = load_manifest()
    manifest["repo_overrides"][repo.name] = {
        "exclusions": [{"pattern": "README.md", "reason": "private fixture"}]
    }
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    module = importlib.import_module("notebooklm_mcp.doc_refresh.discover")
    monkeypatch.setattr(module, "DEFAULT_MANIFEST_PATH", path)
    if ancestor_alias:
        ancestor = tmp_path / "ancestor"
        ancestor.symlink_to(parent, target_is_directory=True)
        repo, alias = ancestor / repo.name, ancestor / alias_name

    def selected(root):
        if entrypoint == "discovery":
            return _existing(discover_repo(root, notebook_map=EMPTY_MAP))
        return {p.relative_to(root).as_posix() for p in discover_tier3_docs(root)}

    assert "README.md" not in selected(repo)
    assert "CHANGELOG.md" in selected(repo)
    with pytest.raises(ManifestError, match="repository root"):
        selected(alias)


@pytest.mark.parametrize("entrypoint", ["loader", "file", "supplied"])
def test_mixed_invalid_override_names_and_values_raise_manifest_error(tmp_path, entrypoint):
    repo = build_simple_repo(tmp_path)
    manifest = load_manifest()
    manifest["repo_overrides"] = {123: None, "valid": None}
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    with pytest.raises(ManifestError, match="repo_overrides"):
        if entrypoint == "loader":
            load_manifest(path)
        elif entrypoint == "file":
            discover_repo(repo, manifest_path=path, notebook_map=EMPTY_MAP)
        else:
            discover_repo(repo, manifest=manifest, notebook_map=EMPTY_MAP)


@pytest.mark.parametrize("case", ["global", "override_name", "nested", "merge_conflict", "repeated_merge"])
@pytest.mark.parametrize("entrypoint", ["loader", "discovery", "schema_opt_out"])
def test_manifest_duplicate_keys_fail_before_selection(tmp_path, case, entrypoint):
    repo = build_complex_repo(tmp_path)
    manifest = load_manifest()
    raw = yaml.safe_dump(manifest)
    if case == "global":
        raw += '\nexclusions:\n  - pattern: "**/*.log"\n    reason: logs\n'
    else:
        del manifest["repo_overrides"]
        raw = yaml.safe_dump(manifest)
        overrides = {
            "override_name": '  C091_complex-docs: {exclusions: [{pattern: README.md, reason: privacy}]}\n  C091_complex-docs: {}\n',
            "nested": '  C091_complex-docs:\n    exclusions: [{pattern: README.md, reason: privacy}]\n    exclusions: []\n',
            "merge_conflict": '  C091_complex-docs:\n    <<: &policy {exclusions: [{pattern: README.md, reason: privacy}]}\n    exclusions: []\n',
            "repeated_merge": '  C091_complex-docs:\n    <<: {exclusions: [{pattern: README.md, reason: privacy}]}\n    <<: {extra_docs: []}\n',
        }
        raw += '\nrepo_overrides:\n' + overrides[case]
    path = tmp_path / "duplicate.yaml"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicate"):
        if entrypoint == "discovery":
            discover_repo(repo, manifest_path=path, notebook_map=EMPTY_MAP)
        else:
            load_manifest(path, validate=entrypoint != "schema_opt_out")


def test_nonconflicting_yaml_merge_preserves_selection_and_byte_hash(tmp_path):
    repo = build_simple_repo(tmp_path)
    manifest = load_manifest()
    del manifest["repo_overrides"]
    raw = yaml.safe_dump(manifest) + '''
repo_overrides:
  C090_simple-docs:
    <<: &policy {exclusions: [{pattern: README.md, reason: privacy}]}
    extra_docs: []
'''
    path = tmp_path / "merged.yaml"
    path.write_text(raw, encoding="utf-8")
    result = discover_repo(repo, manifest_path=path, notebook_map=EMPTY_MAP)
    assert "README.md" not in _existing(result)
    assert "CHANGELOG.md" in _existing(result)
    assert result.manifest_content_hash == hashlib.sha256(raw.encode()).hexdigest()[:12]


@pytest.mark.parametrize("pattern", ["docs/**/restricted.md", "docs/**/**/restricted.md"])
@pytest.mark.parametrize("relative", ["docs/restricted.md", "docs/one/restricted.md", "docs/one/two/restricted.md"])
def test_recursive_exclusions_cover_every_depth(tmp_path, pattern, relative):
    repo = build_simple_repo(tmp_path)
    _write(repo / relative, "synthetic excluded")
    _write(repo / "docs/allowed.md", "synthetic allowed")
    manifest = load_manifest()
    manifest["exclusions"].append({"pattern": pattern, "reason": "recursive privacy"})
    manifest["repo_overrides"][repo.name] = {
        "extra_docs": [
            {"path": relative, "purpose": "excluded fixture"},
            {"path": "docs/allowed.md", "purpose": "allowed fixture"},
        ]
    }
    selected = _existing(discover_repo(repo, manifest, EMPTY_MAP))
    assert relative not in selected
    assert "docs/allowed.md" in selected


def test_legacy_automatic_selector_obeys_manifest_privacy(tmp_path):
    from notebooklm_mcp.sync_cli import discover_tier3_docs

    repo = build_complex_repo(tmp_path)
    _write(repo / "10_docs/public.md", "synthetic public")
    (repo / "README.md").unlink()
    (repo / "README.md").symlink_to(repo / "private/transcript.md")
    selected = {p.relative_to(repo).as_posix() for p in discover_tier3_docs(repo)}
    assert "10_docs/public.md" in selected
    assert not {"README.md", "10_docs/private/notes.md", "private/transcript.md", ".env"} & selected
    expected = {str(d.path) for d in discover_repo(repo, notebook_map=EMPTY_MAP).existing_docs if (repo / d.path).is_file()}
    assert selected == expected


def test_automatic_cli_keeps_selected_wildcard_filename_literal(tmp_path, monkeypatch):
    import sys
    from notebooklm_mcp import sync_cli

    repo = build_simple_repo(tmp_path)
    _write(repo / "10_docs/guide*.md", "synthetic literal filename")
    _write(repo / "10_docs/private/notes.md", "synthetic excluded")
    monkeypatch.setattr(sync_cli, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["notebooklm-sync", "--repo", repo.name, "--tier3"])
    published = []
    monkeypatch.setattr(sync_cli, "sync_files", lambda name, files, **kwargs: published.extend(files))
    assert sync_cli.main() == 0
    assert repo / "10_docs/guide*.md" in published
    assert repo / "10_docs/private/notes.md" not in published


@pytest.mark.parametrize("mode", ["excluded", "internal_symlink", "outside_symlink", "allowed"])
def test_primer_relations_uses_manifest_selection(tmp_path, monkeypatch, mode):
    module = importlib.import_module("notebooklm_mcp.doc_refresh.discover")
    from notebooklm_mcp.primer_gen.sources import gather_sources

    repo = build_simple_repo(tmp_path)
    target = repo / "RELATIONS.yaml"
    if mode.endswith("symlink"):
        private = repo / "private/notes.md" if mode == "internal_symlink" else tmp_path / "outside.md"
        _write(private, "synthetic private relation")
        target.symlink_to(private)
    else:
        _write(target, "synthetic: public_relation\n")
    manifest = load_manifest()
    if mode == "excluded":
        manifest["exclusions"].append({"pattern": "RELATIONS.yaml", "reason": "explicit privacy"})
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    monkeypatch.setattr(module, "DEFAULT_MANIFEST_PATH", path)
    monkeypatch.setattr(module, "load_notebook_map", lambda: EMPTY_MAP)
    gathered = gather_sources(repo)
    relations = [d for d in gathered.docs if d.name == "RELATIONS.yaml"]
    assert len(relations) == (1 if mode == "allowed" else 0)


@pytest.mark.parametrize("per_repo", [False, True])
@pytest.mark.parametrize("exclusions", [["README.md"], [{"patern": "README.md", "reason": "typo"}]])
def test_supplied_manifest_rejects_malformed_privacy_rules(tmp_path, per_repo, exclusions):
    repo = build_simple_repo(tmp_path)
    manifest = load_manifest()
    target = manifest
    if per_repo:
        target = manifest["repo_overrides"].setdefault(repo.name, {})
    target["exclusions"] = exclusions
    with pytest.raises(ManifestError):
        discover_repo(repo, manifest=manifest, notebook_map=EMPTY_MAP)


def test_scans_preserve_documents_and_privacy_through_ancestor_alias(tmp_path):
    parent = tmp_path.resolve() / "real"
    parent.mkdir()
    repo = build_complex_repo(parent)
    alias = tmp_path / "alias"
    alias.symlink_to(parent, target_is_directory=True)
    _write(repo / "10_docs" / "public.md", "# Synthetic public\n")
    (repo / "10_docs" / "linked.md").symlink_to(repo / "10_docs" / "private" / "notes.md")
    real = _existing(discover_repo(repo, notebook_map=EMPTY_MAP))
    aliased = _existing(discover_repo(alias / repo.name, notebook_map=EMPTY_MAP))
    assert "10_docs/public.md" in real
    assert aliased == real
    assert not {"10_docs/private/notes.md", "10_docs/linked.md", ".env"} & aliased


@pytest.mark.parametrize("supplied", [False, True])
def test_manifest_hash_describes_captured_selection_bytes(tmp_path, monkeypatch, supplied):
    module = importlib.import_module("notebooklm_mcp.doc_refresh.discover")
    repo = build_simple_repo(tmp_path)
    manifest_a = load_manifest()
    manifest_b = copy.deepcopy(manifest_a)
    manifest_b["exclusions"].append({"pattern": "README.md", "reason": "new exclusion"})
    raw_a = yaml.safe_dump(manifest_a).encode("utf-8")
    raw_b = yaml.safe_dump(manifest_b).encode("utf-8")
    path = tmp_path / "manifest.yaml"
    path.write_bytes(raw_a)
    original = module._discover_tier_docs

    def replace_manifest(*args, **kwargs):
        path.write_bytes(raw_b)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "_discover_tier_docs", replace_manifest)
    result = discover_repo(
        repo, manifest=manifest_a if supplied else None,
        manifest_path=path, notebook_map=EMPTY_MAP,
    )
    assert "README.md" in _existing(result)
    assert result.manifest_content_hash == hashlib.sha256(raw_a).hexdigest()[:12]
    assert result.manifest_content_hash != hashlib.sha256(raw_b).hexdigest()[:12]


def test_last_commit_uses_literal_document_path(tmp_path):
    repo = build_simple_repo(tmp_path)

    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

    git("init", "-q")
    git("config", "user.name", "Synthetic Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "core.hooksPath", "/dev/null")
    _write(repo / "docs" / "guide*.md", "# Synthetic literal\n")
    git("add", "--all")
    git("-c", "commit.gpgsign=false", "commit", "-qm", "literal document")
    literal_commit = git("rev-parse", "HEAD")
    _write(repo / "docs" / "guide-public.md", "# Synthetic sibling\n")
    git("add", "--all")
    git("-c", "commit.gpgsign=false", "commit", "-qm", "sibling document")
    sibling_commit = git("rev-parse", "HEAD")
    manifest = load_manifest()
    manifest["repo_overrides"][repo.name] = {
        "extra_docs": [
            {"path": "docs/guide*.md", "purpose": "literal file"},
            {"path": "docs/guide-public.md", "purpose": "matching sibling"},
        ]
    }
    result = discover_repo(repo, manifest=manifest, notebook_map=EMPTY_MAP)
    commits = {d.path.as_posix(): d.last_commit for d in result.docs}
    assert commits["docs/guide*.md"] == literal_commit
    assert commits["docs/guide-public.md"] == sibling_commit


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_simple_repo(root: Path) -> Path:
    """Tier-1-only representative repo."""
    repo = root / "C090_simple-docs"
    _write(repo / "README.md", "# Simple\n")
    _write(repo / "CHANGELOG.md", "# Changes\n")
    _write(repo / "META.yaml", "version: 1.0.0\n")
    return repo


def build_complex_repo(root: Path) -> Path:
    """Tier-1+2 representative repo with privacy files that must be omitted."""
    repo = root / "C091_complex-docs"
    _write(repo / "README.md", "# Complex\n")
    _write(repo / "CHANGELOG.md", "# Changes\n")
    _write(repo / "META.yaml", "version: 1.0.0\n")
    _write(repo / "CLAUDE.md", "# Claude\n")
    _write(repo / "AGENTS.md", "# Agents\n")
    _write(repo / "PROJECT_PRIMER.md", "# Primer\n")
    _write(repo / "10_docs" / "prds" / "PRD-X.md", "# PRD\n")
    _write(repo / "10_docs" / "private" / "notes.md", "private notes\n")
    _write(repo / ".env", "EXAMPLE=1\n")
    _write(repo / ".env.local", "EXAMPLE=1\n")
    _write(repo / "private" / "transcript.md", "not a real transcript\n")
    _write(repo / "build" / "output.txt", "generated\n")
    return repo


def build_kitted_repo(root: Path) -> Path:
    """Kitted representative repo plus extra_docs and an exclusion hit."""
    repo = root / "C092_kitted-docs"
    _write(repo / "README.md", "# Kitted\n")
    _write(repo / "CHANGELOG.md", "# Changes\n")
    _write(repo / "META.yaml", "version: 1.0.0\n")
    _write(repo / "CLAUDE.md", "# Claude\n")
    _write(repo / "docs" / "kitted_docs" / "OVERVIEW.md", "# Overview\n")
    _write(repo / "docs" / "kitted_docs" / "ARCHITECTURE.md", "# Architecture\n")
    _write(repo / "docs" / "SPECIAL.md", "# High-value extra doc\n")
    _write(repo / "secrets" / "token.txt", "placeholder-not-a-secret\n")
    return repo


def kitted_manifest() -> dict:
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"]["C092_kitted-docs"] = {
        "tier3_root": "docs/kitted_docs",
        "extra_docs": [
            {"path": "docs/SPECIAL.md", "purpose": "High-value extra"},
            {"path": "secrets/token.txt", "purpose": "Must still be excluded"},
        ],
    }
    return manifest


def _paths(result) -> set[str]:
    return {str(doc.path).replace("\\", "/") for doc in result.docs}


def _existing(result) -> set[str]:
    return {
        str(doc.path).replace("\\", "/")
        for doc in result.docs
        if doc.exists
    }


class TestSchemaValidation:
    @pytest.mark.parametrize("key", [123, True, None, 1.5])
    @pytest.mark.parametrize("mixed", [False, True])
    @pytest.mark.parametrize("entrypoint", ["loader", "file", "supplied"])
    def test_rejects_non_string_override_names(
        self, tmp_path: Path, key, mixed: bool, entrypoint: str
    ):
        repo = tmp_path / str(key).lower()
        repo.mkdir()
        (repo / "README.md").write_text("Fictional private repository notes")
        manifest = copy.deepcopy(load_manifest())
        rule = {"exclusions": [{"pattern": "README.md", "reason": "private fixture"}]}
        manifest["repo_overrides"] = {key: rule}
        if mixed:
            manifest["repo_overrides"]["C090_valid"] = copy.deepcopy(rule)
        path = tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        with pytest.raises(ManifestError, match="repo_overrides"):
            if entrypoint == "loader":
                load_manifest(path)
            elif entrypoint == "file":
                discover_repo(repo, manifest_path=path, notebook_map=EMPTY_MAP)
            else:
                discover_repo(repo, manifest=manifest, notebook_map=EMPTY_MAP)

    @pytest.mark.parametrize("name", ["123", "true", "null", "1.5"])
    @pytest.mark.parametrize("entrypoint", ["file", "supplied"])
    def test_string_override_names_preserve_exclusions(
        self, tmp_path: Path, name: str, entrypoint: str
    ):
        repo = tmp_path / name
        repo.mkdir()
        (repo / "README.md").write_text("Fictional private repository notes")
        manifest = copy.deepcopy(load_manifest())
        manifest["repo_overrides"] = {
            name: {"exclusions": [{"pattern": "README.md", "reason": "private fixture"}]}
        }
        path = tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        kwargs = {"manifest_path": path} if entrypoint == "file" else {"manifest": manifest}
        result = discover_repo(repo, notebook_map=EMPTY_MAP, **kwargs)
        assert "README.md" not in _existing(result)

    def test_packaged_manifest_validates(self):
        manifest = load_manifest()
        assert manifest["schema"] == SCHEMA_ID
        assert manifest["version"] == "1.0.0"
        assert manifest["last_updated"]
        assert manifest["exclusions"]
        digest = manifest_content_hash()
        assert len(digest) == 12

    def test_rejects_missing_version(self, tmp_path: Path):
        manifest = copy.deepcopy(load_manifest())
        del manifest["version"]
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        with pytest.raises(ManifestError, match="version"):
            load_manifest(path)

    def test_rejects_unknown_root_key(self, tmp_path: Path):
        manifest = copy.deepcopy(load_manifest())
        manifest["unexpected"] = True
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        with pytest.raises(ManifestError):
            load_manifest(path)

    def test_rejects_wrong_schema_id(self):
        manifest = copy.deepcopy(load_manifest())
        manifest["schema"] = "other.schema"
        with pytest.raises(ManifestError):
            validate_canonical_docs(manifest)

    def test_rejects_exclusion_without_reason(self):
        manifest = copy.deepcopy(load_manifest())
        manifest["exclusions"] = [{"pattern": ".env"}]
        with pytest.raises(ManifestError):
            validate_canonical_docs(manifest)

    def test_rejects_non_mapping(self):
        with pytest.raises(ManifestError, match="mapping"):
            validate_canonical_docs(["not", "a", "mapping"])


class TestGlobAndContainment:
    def test_env_patterns_match_nested_files(self):
        exclusions = load_manifest()["exclusions"]
        assert is_excluded(".env", exclusions)
        assert is_excluded(".env.local", exclusions)
        assert is_excluded("config/.env", exclusions)
        assert is_excluded("private/transcript.md", exclusions)
        assert is_excluded("secrets/token.txt", exclusions)
        assert is_excluded("build/output.txt", exclusions)
        assert not is_excluded("README.md", exclusions)
        assert not is_excluded("10_docs/prds/PRD-X.md", exclusions)

    def test_glob_directory_prefix(self):
        assert glob_match("private/transcript.md", "**/private/**")
        assert glob_match("secrets/token.txt", "**/secrets/**")
        assert not glob_match("README.md", "**/private/**")

    def test_path_containment_rejects_escape(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("nope", encoding="utf-8")
        assert path_is_contained(repo, "README.md")
        assert not path_is_contained(repo, "../outside.txt")
        assert not path_is_contained(repo, "/tmp/outside.txt")
        assert not path_is_contained(repo, "")
        link = repo / "escaped.md"
        link.symlink_to(outside)
        assert not path_is_contained(repo, "escaped.md")


class TestSyntheticRepos:
    def test_three_representative_repos(self, tmp_path: Path):
        simple = build_simple_repo(tmp_path)
        complex_repo = build_complex_repo(tmp_path)
        kitted = build_kitted_repo(tmp_path)

        simple_result = discover_repo(simple, notebook_map=EMPTY_MAP)
        complex_result = discover_repo(complex_repo, notebook_map=EMPTY_MAP)
        kitted_result = discover_repo(
            kitted, manifest=kitted_manifest(), notebook_map=EMPTY_MAP
        )

        assert simple_result.tier == Tier.SIMPLE
        assert complex_result.tier == Tier.COMPLEX
        assert kitted_result.tier == Tier.KITTED

        assert {"README.md", "CHANGELOG.md", "META.yaml"} <= _existing(simple_result)
        assert "CLAUDE.md" in _existing(complex_result)
        assert "AGENTS.md" in _existing(complex_result)
        assert "PROJECT_PRIMER.md" in _existing(complex_result)
        assert "10_docs/prds/PRD-X.md" in _existing(complex_result)
        assert "docs/kitted_docs/OVERVIEW.md" in _existing(kitted_result)
        assert "docs/kitted_docs/ARCHITECTURE.md" in _existing(kitted_result)
        assert "docs/SPECIAL.md" in _existing(kitted_result)

        assert simple_result.manifest_version == "1.0.0"
        assert simple_result.manifest_content_hash
        assert len(simple_result.manifest_content_hash) == 12
        assert kitted_result.manifest_content_hash is None

    def test_privacy_exclusions_omit_matches_keep_authorized(self, tmp_path: Path):
        repo = build_complex_repo(tmp_path)
        result = discover_repo(repo, notebook_map=EMPTY_MAP)
        existing = _existing(result)

        assert "README.md" in existing
        assert "10_docs/prds/PRD-X.md" in existing
        assert ".env" not in existing
        assert ".env.local" not in existing
        assert "private/transcript.md" not in existing
        assert "build/output.txt" not in existing
        assert "10_docs/private/notes.md" not in existing
        assert not any(path.endswith(".env") or ".env." in path for path in existing)

    def test_exclusion_wins_over_extra_docs(self, tmp_path: Path):
        repo = build_kitted_repo(tmp_path)
        result = discover_repo(
            repo, manifest=kitted_manifest(), notebook_map=EMPTY_MAP
        )
        existing = _existing(result)
        all_paths = _paths(result)

        assert "docs/SPECIAL.md" in existing
        assert "secrets/token.txt" not in existing
        assert "secrets/token.txt" not in all_paths

    def test_symlink_and_parent_escape_are_omitted(self, tmp_path: Path):
        repo = build_simple_repo(tmp_path)
        outside = tmp_path / "outside.md"
        outside.write_text("# outside\n", encoding="utf-8")
        (repo / "escaped.md").symlink_to(outside)

        manifest = copy.deepcopy(load_manifest())
        manifest["repo_overrides"][repo.name] = {
            "extra_docs": [
                {"path": "escaped.md", "purpose": "symlink escape"},
                {"path": "../outside.md", "purpose": "parent escape"},
                {"path": "README.md", "purpose": "duplicate authorized"},
            ]
        }
        result = discover_repo(repo, manifest=manifest, notebook_map=EMPTY_MAP)
        paths = _paths(result)

        assert "README.md" in paths
        assert "escaped.md" not in paths
        assert "../outside.md" not in paths
        assert "outside.md" not in paths

    def test_freshness_metadata_on_existing_files(self, tmp_path: Path):
        repo = build_simple_repo(tmp_path)
        result = discover_repo(repo, notebook_map=EMPTY_MAP)
        compute_all_hashes(result)
        readme = next(doc for doc in result.docs if str(doc.path) == "README.md")
        assert readme.source_title == f"DOC: {repo.name} :: README.md"
        assert readme.generated_bundle_id is None
        assert readme.last_commit is None  # synthetic fixture is not a git repo
        assert readme.content_hash
        assert len(readme.content_hash) == 12

    def test_required_uses_must_exist(self, tmp_path: Path):
        repo = tmp_path / "C093_missing-readme"
        _write(repo / "CHANGELOG.md", "# Changes\n")
        _write(repo / "META.yaml", "version: 1.0.0\n")
        result = discover_repo(repo, notebook_map=EMPTY_MAP)
        readme = next(doc for doc in result.docs if str(doc.path) == "README.md")
        assert readme.exists is False
        assert readme.required is True
        assert result.missing_required


def test_internal_symlink_cannot_read_excluded_content(tmp_path):
    repo = build_complex_repo(tmp_path)
    (repo / "README.md").unlink()
    (repo / "README.md").symlink_to(repo / "private" / "transcript.md")
    result = discover_repo(repo, notebook_map=EMPTY_MAP)
    assert not any(d.path == Path("README.md") for d in result.docs)


@pytest.mark.parametrize("inside", [True, False])
def test_tier3_absolute_doc_is_omitted(tmp_path, inside):
    from notebooklm_mcp.doc_refresh.discover import _discover_one_def
    repo = build_kitted_repo(tmp_path)
    target = repo / "README.md" if inside else tmp_path / "outside.md"
    assert _discover_one_def(repo, repo.name, {"path": str(target)}, 3, {}, [], {}, base=repo / "docs/kitted_docs") == []


def test_in_memory_manifest_has_no_false_byte_provenance(tmp_path):
    repo = build_simple_repo(tmp_path)
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"][repo.name] = {"extra_docs": [{"path": "EXTRA.md", "purpose": "synthetic selection fixture"}]}
    assert discover_repo(repo, manifest, EMPTY_MAP).manifest_content_hash is None


@pytest.mark.parametrize("alias", ["docs/./restricted.md", "docs/sub/../restricted.md", "docs//restricted.md", "docs/restricted.md/", "docs/restricted.md//", "./docs/restricted.md/", "docs\\restricted.md\\"])
def test_dot_segment_alias_cannot_bypass_exclusions(tmp_path, alias):
    repo = build_simple_repo(tmp_path)
    _write(repo / "docs/restricted.md", "synthetic excluded")
    (repo / "docs/sub").mkdir()
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"][repo.name] = {"exclusions": [{"pattern": "docs/restricted.md", "reason": "synthetic privacy fixture"}], "extra_docs": [{"path": alias, "purpose": "synthetic selection fixture"}]}
    assert not any(d.path.name == "restricted.md" for d in discover_repo(repo, manifest, EMPTY_MAP).docs)


def test_absolute_scan_pattern_is_omitted(tmp_path):
    from notebooklm_mcp.doc_refresh.discover import _expand_scan
    repo = build_simple_repo(tmp_path)
    assert _expand_scan(repo, repo.name, {"scan_pattern": "/tmp/*.md"}, 2, {}, [], {}) == []


def test_exclusions_use_selected_path_identity_and_preserve_directory_discovery(tmp_path):
    from notebooklm_mcp.doc_refresh.selection import glob_match

    repo = build_complex_repo(tmp_path)
    _write(repo / "10_docs/allowed.md", "synthetic allowed")
    result = discover_repo(repo, notebook_map=EMPTY_MAP)
    assert any(d.path == Path("10_docs") for d in result.docs)
    assert any(d.path == Path("10_docs/allowed.md") for d in result.docs)
    for alias in ("docs/restricted.md", "docs/restricted.md/", "docs/restricted.md//"):
        assert is_excluded(alias, ["docs/restricted.md"])
        assert Path(alias) == Path("docs/restricted.md")
    assert not glob_match("", "*")


@pytest.mark.parametrize("alias", ["docs/RESTRICTED.md", "DOCS/restricted.md", "DOCS/RESTRICTED.md"])
def test_filesystem_alias_cannot_select_excluded_file(tmp_path, alias):
    repo = build_simple_repo(tmp_path)
    _write(repo / "docs/restricted.md", "synthetic excluded")
    if not (repo / alias).exists():
        pytest.skip("requires filesystem case aliases")
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"][repo.name] = {
        "exclusions": [{"pattern": "docs/restricted.md", "reason": "synthetic privacy fixture"}],
        "extra_docs": [{"path": alias, "purpose": "synthetic selection fixture"}],
    }
    result = discover_repo(repo, manifest, EMPTY_MAP)
    assert not any((repo / d.path).is_file() and (repo / d.path).samefile(repo / "docs/restricted.md") for d in result.docs)
    assert not path_is_contained(repo, alias)


@pytest.mark.parametrize("excluded", ["docs/RESTRICTED.md", "DOCS/restricted.md", "DOCS/*.md"])
def test_filesystem_alias_exclusion_covers_canonical_file(tmp_path, excluded):
    repo = build_simple_repo(tmp_path)
    _write(repo / "docs/restricted.md", "synthetic excluded")
    if not (repo / "DOCS/RESTRICTED.md").exists():
        pytest.skip("requires filesystem case aliases")
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"][repo.name] = {
        "exclusions": [{"pattern": excluded, "reason": "synthetic privacy fixture"}],
        "extra_docs": [{"path": "docs/restricted.md", "purpose": "synthetic selection fixture"}],
    }
    assert not any(d.path == Path("docs/restricted.md") for d in discover_repo(repo, manifest, EMPTY_MAP).docs)


def test_exact_filesystem_identity_preserves_safe_and_missing_paths(tmp_path):
    repo = build_simple_repo(tmp_path)
    _write(repo / "docs/Allowed.md", "synthetic allowed")
    assert path_is_contained(repo, "docs/Allowed.md")
    assert path_is_contained(repo, "docs/missing.md")
    assert not path_is_contained(repo, "docs/../README.md")
    (repo / "alias").symlink_to(repo / "docs", target_is_directory=True)
    assert not path_is_contained(repo, "alias/Allowed.md")
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"][repo.name] = {"extra_docs": [{"path": "docs/Allowed.md", "purpose": "synthetic selection fixture"}]}
    assert any(d.path == Path("docs/Allowed.md") for d in discover_repo(repo, manifest, EMPTY_MAP).docs)


def test_case_distinct_files_remain_distinct_where_supported(tmp_path):
    repo = build_simple_repo(tmp_path)
    _write(repo / "docs/lower.md", "synthetic restricted")
    if (repo / "docs/LOWER.md").exists():
        pytest.skip("requires case-sensitive filesystem")
    _write(repo / "docs/LOWER.md", "synthetic allowed")
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"][repo.name] = {
        "exclusions": [{"pattern": "docs/lower.md", "reason": "synthetic privacy fixture"}],
        "extra_docs": [{"path": "docs/LOWER.md", "purpose": "synthetic selection fixture"}],
    }
    assert path_is_contained(repo, "docs/LOWER.md")
    assert any(d.path == Path("docs/LOWER.md") for d in discover_repo(repo, manifest, EMPTY_MAP).docs)


def test_normalization_alias_cannot_select_excluded_file(tmp_path):
    import unicodedata
    repo = build_simple_repo(tmp_path)
    name = "caf\N{LATIN SMALL LETTER E WITH ACUTE}.md"
    _write(repo / "docs" / name, "synthetic excluded")
    actual = next((repo / "docs").iterdir()).name
    alternate = unicodedata.normalize("NFD" if actual == unicodedata.normalize("NFC", actual) else "NFC", actual)
    alias = repo / "docs" / alternate
    if alternate == actual or not alias.exists():
        pytest.skip("requires filesystem Unicode normalization aliases")
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"][repo.name] = {
        "exclusions": [{"pattern": "docs/" + actual, "reason": "synthetic privacy fixture"}],
        "extra_docs": [{"path": "docs/" + alternate, "purpose": "synthetic selection fixture"}],
    }
    assert not any((repo / d.path).is_file() and (repo / d.path).samefile(alias) for d in discover_repo(repo, manifest, EMPTY_MAP).docs)


def test_filesystem_identity_applies_to_scan_alternates_and_filter(tmp_path):
    from notebooklm_mcp.doc_refresh.discover import _discover_one_def, _expand_scan
    from notebooklm_mcp.doc_refresh.selection import filter_contained_relpaths
    repo = build_simple_repo(tmp_path)
    _write(repo / "docs/restricted.md", "synthetic excluded")
    if not (repo / "DOCS/RESTRICTED.md").exists():
        pytest.skip("requires filesystem case aliases")
    excluded = [{"pattern": "DOCS/restricted.md", "reason": "synthetic privacy fixture"}]
    assert _expand_scan(repo, repo.name, {"scan_pattern": "docs/*.md"}, 2, {}, excluded, {}) == []
    assert _expand_scan(repo, repo.name, {"scan_pattern": "DOCS/*.md"}, 2, {}, [], {}) == []
    assert _discover_one_def(repo, repo.name, {"path": "docs/RESTRICTED.md", "alternate_names": ["docs/restricted.md"], "purpose": "synthetic selection fixture"}, 2, {}, excluded, {}) == []
    assert filter_contained_relpaths(repo, ["docs/restricted.md", "docs/RESTRICTED.md"], excluded) == []


def test_filesystem_identity_lookup_error_fails_closed(tmp_path, monkeypatch):
    from notebooklm_mcp.doc_refresh import selection
    repo = build_simple_repo(tmp_path)
    def denied(*args):
        raise PermissionError("synthetic lookup denial")
    monkeypatch.setattr(selection, "_entry_spelling", denied)
    assert not path_is_contained(repo, "README.md")
    assert is_excluded("README.md", ["private/**"], repo)


def test_literal_glob_character_filename_still_checks_identity(tmp_path):
    repo = build_simple_repo(tmp_path)
    _write(repo / "docs/restricted?.md", "synthetic excluded")
    if not (repo / "docs/RESTRICTED?.md").exists():
        pytest.skip("requires filesystem case aliases")
    assert not path_is_contained(repo, "docs/RESTRICTED?.md")
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"][repo.name] = {
        "exclusions": [{"pattern": "docs/restricted?.md", "reason": "synthetic privacy fixture"}],
        "extra_docs": [{"path": "docs/RESTRICTED?.md", "purpose": "synthetic selection fixture"}],
    }
    assert not any(d.path == Path("docs/RESTRICTED?.md") for d in discover_repo(repo, manifest, EMPTY_MAP).docs)


def test_exclusion_identity_does_not_walk_symlink_target(tmp_path, monkeypatch):
    repo = build_simple_repo(tmp_path)
    outside = tmp_path / "outside"
    _write(outside / "private.md", "synthetic outside")
    (repo / "alias").symlink_to(outside, target_is_directory=True)
    original = Path.iterdir
    def bounded(path):
        assert path != repo / "alias", "must not enumerate symlink target"
        return original(path)
    monkeypatch.setattr(Path, "iterdir", bounded)
    assert is_excluded("README.md", ["alias/private.md"], repo)


@pytest.mark.parametrize("parent", ["docs", "docs/deep", "docs[1]", "docs[ab]/deep[2]", "docs?", "docs*"])
def test_basename_exclusion_uses_candidate_parent_identity(tmp_path, parent):
    from notebooklm_mcp.doc_refresh.selection import filter_contained_relpaths, is_excluded

    repo = tmp_path / "repo"
    _write(repo / parent / "restricted.md", "synthetic")
    if not (repo / parent / "RESTRICTED.md").exists():
        pytest.skip("requires filesystem case aliases")
    # An unrelated same-name root file must not control the nested identity.
    _write(repo / "RESTRICTED.md", "unrelated synthetic root file")
    rel = parent + "/restricted.md"
    assert is_excluded(rel, ["RESTRICTED.md"], repo)
    assert filter_contained_relpaths(repo, [rel], [{"pattern": "RESTRICTED.md", "reason": "synthetic privacy fixture"}]) == []


def test_basename_unicode_alias_exclusion_uses_candidate_parent(tmp_path):
    import unicodedata
    from notebooklm_mcp.doc_refresh.selection import is_excluded

    repo = tmp_path / "repo"
    name = "r\u00e9stricted.md"
    _write(repo / "docs" / name, "synthetic")
    actual = next((repo / "docs").iterdir()).name
    alternate = unicodedata.normalize("NFD" if actual == unicodedata.normalize("NFC", actual) else "NFC", actual)
    if alternate == actual or not (repo / "docs" / alternate).exists():
        pytest.skip("requires filesystem normalization aliases")
    assert is_excluded("docs/" + actual, [alternate], repo)


def test_basename_identity_preserves_wildcards_and_missing_patterns(tmp_path):
    from notebooklm_mcp.doc_refresh.selection import is_excluded

    repo = tmp_path / "repo"
    _write(repo / "docs/restricted.md", "synthetic")
    assert not is_excluded("docs/restricted.md", ["*.MD", "missing.md"], repo)
    assert is_excluded("docs/restricted.md", ["*.md"], repo)
    assert is_excluded("docs/restricted.md", ["docs/restricted.md"], repo)


@pytest.mark.parametrize("parent", ["docs[1]", "docs[ab]/deep[2]"])
def test_literal_basename_exclusion_survives_glob_characters_in_parent(tmp_path, parent):
    repo = build_simple_repo(tmp_path)
    restricted = f"{parent}/restricted.md"
    allowed = f"{parent}/allowed.md"
    _write(repo / restricted, "synthetic excluded text")
    _write(repo / allowed, "synthetic allowed text")
    if not (repo / parent / "RESTRICTED.md").exists():
        pytest.skip("requires filesystem case aliases")
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"][repo.name] = {
        "exclusions": [{"pattern": "RESTRICTED.md", "reason": "synthetic privacy rule"}],
        "extra_docs": [{"path": restricted, "purpose": "synthetic selection fixture"}, {"path": allowed, "purpose": "synthetic selection fixture"}],
    }
    result = discover_repo(repo, manifest=manifest, notebook_map=EMPTY_MAP)
    assert restricted not in _paths(result)
    assert allowed in _existing(result)
