"""
Filesystem discovery for canonical documentation.

Scans a repository to:
1. Detect tier classification (simple/complex/kitted)
2. Discover all canonical documents per tier
3. Apply fail-closed exclusions and path/symlink containment
4. Build a DiscoveryResult for validation
"""

from __future__ import annotations

import copy
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from .manifest import (
    DEFAULT_MANIFEST_PATH,
    _load_manifest_snapshot,
    get_alternate_names,
    get_stored_hashes,
    get_tier_docs,
    load_notebook_map,
    resolve_tier3_root,
)
from .models import DiscoveryResult, DocItem, Tier
from .schema import ManifestError, validate_canonical_docs
from .selection import (
    get_exclusions,
    get_extra_docs,
    is_excluded,
    normalize_relpath,
    path_is_contained,
)

def _validate_repo_root_spelling(repo_path: Path) -> None:
    """Refuse root aliases before their spelling can choose a different override."""
    try:
        if repo_path.is_symlink():
            raise ManifestError("repository root must not be a symlink")
        if repo_path.is_dir():
            # Compare literal directory entries, without changing case or Unicode.
            # The parent may be an ancestor alias; its entries still identify the
            # same repository basename. Missing roots retain empty discovery.
            names = {entry.name for entry in repo_path.parent.iterdir()}
            if repo_path.name not in names:
                raise ManifestError("repository root must use its directory-entry spelling")
    except (OSError, RuntimeError) as exc:
        raise ManifestError("cannot verify repository root spelling") from exc


def discover_repo(
    repo_path: Path,
    manifest: Optional[dict[str, Any]] = None,
    notebook_map: Optional[dict[str, Any]] = None,
    *,
    manifest_path: Optional[Path] = None,
) -> DiscoveryResult:
    """
    Discover canonical documentation in a repository.

    Args:
        repo_path: Absolute path to the repository root
        manifest: Pre-loaded manifest, validated before selection (default if None)
        notebook_map: Pre-loaded notebook map (loads default if None)
        manifest_path: Manifest to load, or compare with a supplied mapping for provenance

    Returns:
        DiscoveryResult with tier classification and discovered docs
    """
    loaded_from = manifest_path or DEFAULT_MANIFEST_PATH
    manifest_hash = None
    if manifest is None:
        manifest, manifest_hash = _load_manifest_snapshot(loaded_from)
    else:
        # A caller can alter a previously loaded mapping. Validate an owned copy
        # before exclusions or any repository selection can consume it.
        manifest = copy.deepcopy(manifest)
        validate_canonical_docs(manifest)
        if manifest_path is not None:
            captured, captured_hash = _load_manifest_snapshot(manifest_path)
            if captured == manifest:
                manifest_hash = captured_hash
    _validate_repo_root_spelling(repo_path)
    if notebook_map is None:
        notebook_map = load_notebook_map()

    repo_name = repo_path.name
    stored_hashes = get_stored_hashes(notebook_map, repo_name)
    exclusions = get_exclusions(manifest, repo_name)
    commit_cache: dict[str, Optional[str]] = {}

    # Discover Tier 1 docs (always checked)
    tier1_docs = _discover_tier_docs(
        repo_path, manifest, 1, stored_hashes, exclusions, repo_name, commit_cache
    )

    # Discover Tier 2 docs (always checked, but not required)
    tier2_docs = _discover_tier_docs(
        repo_path, manifest, 2, stored_hashes, exclusions, repo_name, commit_cache
    )

    # Determine if repo has Tier 3 docs
    tier3_root = resolve_tier3_root(repo_path, repo_name, manifest)
    tier3_docs: list[DocItem] = []

    if tier3_root:
        tier3_docs = _discover_tier3_docs(
            repo_path,
            tier3_root,
            manifest,
            stored_hashes,
            exclusions,
            repo_name,
            commit_cache,
        )

    extra_docs = _discover_extra_docs(
        repo_path, manifest, stored_hashes, exclusions, repo_name, commit_cache
    )

    all_docs = _dedupe_docs(tier1_docs + tier2_docs + tier3_docs + extra_docs)
    # Classification describes the same consolidated items returned to callers.
    tier = _classify_tier(
        [doc for doc in all_docs if doc.tier == 1],
        [doc for doc in all_docs if doc.tier == 2],
        [doc for doc in all_docs if doc.tier == 3],
        tier3_root,
    )

    return DiscoveryResult(
        repo_path=repo_path,
        repo_name=repo_name,
        tier=tier,
        tier3_root=tier3_root,
        docs=all_docs,
        manifest_content_hash=manifest_hash,
        manifest_version=str(manifest.get("version") or "") or None,
        manifest_last_updated=str(manifest.get("last_updated") or "") or None,
    )


def _must_exist(doc_def: dict[str, Any]) -> bool:
    if "must_exist" in doc_def:
        return bool(doc_def["must_exist"])
    return bool(doc_def.get("required", False))


def _lookup_last_commit(
    repo_path: Path,
    relpath: str,
    cache: dict[str, Optional[str]],
) -> Optional[str]:
    """Best-effort per-file last commit. Missing git is None, never a failure."""
    if relpath in cache:
        return cache[relpath]
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        cache[relpath] = None
        return None
    try:
        completed = subprocess.run(
            ["git", "--literal-pathspecs", "-C", str(repo_path), "log", "-1", "--format=%H", "--", relpath],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        cache[relpath] = None
        return None
    sha = (completed.stdout or "").strip() or None
    cache[relpath] = sha
    return sha


def _make_item(
    *,
    repo_path: Path,
    repo_name: str,
    relpath: str,
    tier: int,
    purpose: str,
    exists: bool,
    required: bool,
    stored_hashes: dict[str, str],
    commit_cache: dict[str, Optional[str]],
) -> Optional[DocItem]:
    rel = normalize_relpath(relpath)
    if not rel:
        return None
    if not path_is_contained(repo_path, rel):
        return None
    last_commit = _lookup_last_commit(repo_path, rel, commit_cache) if exists else None
    return DocItem(
        path=Path(rel),
        tier=tier,
        purpose=purpose,
        exists=exists,
        required=required,
        stored_hash=stored_hashes.get(rel),
        source_title=f"DOC: {repo_name} :: {rel}",
        last_commit=last_commit,
        generated_bundle_id=None,
    )


def _expand_scan(
    repo_path: Path,
    repo_name: str,
    doc_def: dict[str, Any],
    tier: int,
    stored_hashes: dict[str, str],
    exclusions: list[dict[str, Any]],
    commit_cache: dict[str, Optional[str]],
) -> list[DocItem]:
    pattern = doc_def.get("scan_pattern")
    if not pattern or not path_is_contained(repo_path, pattern):
        return []
    docs: list[DocItem] = []
    try:
        matches = sorted(repo_path.glob(pattern))
    except (OSError, ValueError, NotImplementedError):
        return []
    for match in matches:
        try:
            if not match.is_file() or match.is_symlink():
                continue
        except OSError:
            continue
        try:
            # glob() yields the supplied root spelling, including ancestor aliases.
            # Containment below checks the physical target separately.
            rel = match.relative_to(repo_path).as_posix()
        except ValueError:
            continue
        if not path_is_contained(repo_path, rel):
            continue
        if is_excluded(rel, exclusions, repo_path):
            continue
        item = _make_item(
            repo_path=repo_path,
            repo_name=repo_name,
            relpath=rel,
            tier=tier,
            purpose=doc_def.get("purpose", ""),
            exists=True,
            required=False,
            stored_hashes=stored_hashes,
            commit_cache=commit_cache,
        )
        if item is not None:
            docs.append(item)
    return docs


def _discover_one_def(
    repo_path: Path,
    repo_name: str,
    doc_def: dict[str, Any],
    tier: int,
    stored_hashes: dict[str, str],
    exclusions: list[dict[str, Any]],
    commit_cache: dict[str, Optional[str]],
    *,
    base: Optional[Path] = None,
) -> list[DocItem]:
    """Discover a single document definition, applying containment then exclusions."""
    raw_path = doc_def.get("path") or ""
    if not raw_path:
        return []

    root = base or repo_path
    names = [raw_path, *get_alternate_names(doc_def)]
    found_rel: Optional[str] = None
    found_exists = False

    for name in names:
        if not path_is_contained(root, name):
            continue
        if base is not None:
            rel = (base / name).relative_to(repo_path).as_posix()
            full = root / name
        else:
            rel = normalize_relpath(name)
            full = repo_path / rel
        if not path_is_contained(repo_path, rel):
            continue
        if is_excluded(rel, exclusions, repo_path):
            # Exclusion wins: skip this name even if it exists.
            continue
        try:
            exists = full.exists()
        except OSError:
            exists = False
        if exists and full.is_symlink() and not path_is_contained(repo_path, rel):
            continue
        if exists:
            found_rel = rel
            found_exists = True
            break
        if found_rel is None:
            found_rel = rel

    if found_rel is None:
        # Every candidate name failed containment or exclusion.
        return []

    items: list[DocItem] = []
    directory = bool(doc_def.get("is_directory")) or str(found_rel).endswith("/")
    item = _make_item(
        repo_path=repo_path,
        repo_name=repo_name,
        relpath=found_rel if not directory or found_rel.endswith("/") else found_rel + "/",
        tier=tier,
        purpose=doc_def.get("purpose", ""),
        exists=found_exists,
        required=_must_exist(doc_def),
        stored_hashes=stored_hashes,
        commit_cache=commit_cache,
    )
    if item is not None:
        items.append(item)

    if directory and found_exists:
        items.extend(
            _expand_scan(
                repo_path,
                repo_name,
                doc_def,
                tier,
                stored_hashes,
                exclusions,
                commit_cache,
            )
        )
    return items


def _discover_tier_docs(
    repo_path: Path,
    manifest: dict[str, Any],
    tier: int,
    stored_hashes: dict[str, str],
    exclusions: list[dict[str, Any]],
    repo_name: str,
    commit_cache: dict[str, Optional[str]],
) -> list[DocItem]:
    """Discover documents for a specific tier (1 or 2)."""
    docs: list[DocItem] = []
    for doc_def in get_tier_docs(manifest, tier):
        docs.extend(
            _discover_one_def(
                repo_path,
                repo_name,
                doc_def,
                tier,
                stored_hashes,
                exclusions,
                commit_cache,
            )
        )
    return docs


def _discover_tier3_docs(
    repo_path: Path,
    tier3_root: Path,
    manifest: dict[str, Any],
    stored_hashes: dict[str, str],
    exclusions: list[dict[str, Any]],
    repo_name: str,
    commit_cache: dict[str, Optional[str]],
) -> list[DocItem]:
    """
    Discover Tier 3 documents within the resolved tier3_root.

    Tier 3 docs are defined in the manifest with paths like "OVERVIEW.md"
    which get resolved relative to the tier3_root.
    """
    docs: list[DocItem] = []
    for doc_def in get_tier_docs(manifest, 3):
        docs.extend(
            _discover_one_def(
                repo_path,
                repo_name,
                doc_def,
                3,
                stored_hashes,
                exclusions,
                commit_cache,
                base=tier3_root,
            )
        )
    return docs


def _discover_extra_docs(
    repo_path: Path,
    manifest: dict[str, Any],
    stored_hashes: dict[str, str],
    exclusions: list[dict[str, Any]],
    repo_name: str,
    commit_cache: dict[str, Optional[str]],
) -> list[DocItem]:
    docs: list[DocItem] = []
    for doc_def in get_extra_docs(manifest, repo_name):
        docs.extend(
            _discover_one_def(
                repo_path,
                repo_name,
                doc_def,
                2,
                stored_hashes,
                exclusions,
                commit_cache,
            )
        )
    return docs


def _dedupe_docs(docs: list[DocItem]) -> list[DocItem]:
    unique: dict[str, DocItem] = {}
    for doc in docs:
        key = normalize_relpath(doc.path)
        if key not in unique:
            unique[key] = doc
        elif doc.required and not unique[key].required:
            # Keep the first item's tier and metadata, but never weaken a
            # requirement declared by any definition of the same path.
            unique[key] = replace(unique[key], required=True)
    return list(unique.values())


def _classify_tier(
    tier1_docs: list[DocItem],
    tier2_docs: list[DocItem],
    tier3_docs: list[DocItem],
    tier3_root: Optional[Path],
) -> Tier:
    """
    Classify repository tier based on what documentation exists.

    Classification logic:
    - KITTED: Has Tier 3 root AND at least one Tier 3 doc exists
    - COMPLEX: Has any Tier 2 doc existing (CLAUDE.md, glossary, folders)
    - SIMPLE: Only Tier 1 docs present
    """
    # Check for Tier 3 (kitted)
    if tier3_root and any(d.exists for d in tier3_docs):
        return Tier.KITTED

    # Check for Tier 2 (complex)
    if any(d.exists for d in tier2_docs):
        return Tier.COMPLEX

    # Default to simple
    return Tier.SIMPLE


def get_existing_docs(result: DiscoveryResult) -> list[DocItem]:
    """Get only docs that exist on disk."""
    return [d for d in result.docs if d.exists]


def get_docs_needing_hash(result: DiscoveryResult) -> list[DocItem]:
    """
    Get docs that exist and need hash computation.

    Returns docs that:
    - Exist on disk
    - Are files (not directories)
    """
    return [
        d for d in result.docs
        if d.exists and not str(d.path).endswith("/")
    ]
