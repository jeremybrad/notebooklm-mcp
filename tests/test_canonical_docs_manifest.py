"""
WOR-186: canonical_docs schema, exclusions, containment, synthetic fixtures.
"""

from __future__ import annotations

import copy
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
    manifest["repo_overrides"][repo.name] = {"extra_docs": [{"path": "EXTRA.md"}]}
    assert discover_repo(repo, manifest, EMPTY_MAP).manifest_content_hash is None


@pytest.mark.parametrize("alias", ["docs/./restricted.md", "docs/sub/../restricted.md", "docs//restricted.md", "docs/restricted.md/", "docs/restricted.md//", "./docs/restricted.md/", "docs\\restricted.md\\"])
def test_dot_segment_alias_cannot_bypass_exclusions(tmp_path, alias):
    repo = build_simple_repo(tmp_path)
    _write(repo / "docs/restricted.md", "synthetic excluded")
    (repo / "docs/sub").mkdir()
    manifest = copy.deepcopy(load_manifest())
    manifest["repo_overrides"][repo.name] = {"exclusions": [{"pattern": "docs/restricted.md"}], "extra_docs": [{"path": alias}]}
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
