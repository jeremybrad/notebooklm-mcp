"""
Include/exclude selection and fail-closed path containment.

Exclusion globs always win over tier includes and extra_docs.
Paths that are absolute, escape the repo root, or symlink outside
the repo are omitted — never included.
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Union

Exclusion = Union[str, dict[str, Any]]


def normalize_relpath(path: Union[str, Path]) -> str:
    """Normalize a repo-relative path to POSIX form without a leading './'."""
    text = str(path).replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    if text in {"", "."}:
        return ""
    return text


def glob_match(relpath: str, pattern: str) -> bool:
    """
    Match a repo-relative path against a glob.

    ``**`` is treated as a recursive directory wildcard. Patterns without a
    slash also match the basename at any depth (so ``.env*`` hits
    ``config/.env.local``).
    """
    # Match the same lexical identity that DocItem stores and downstream reads.
    # Path removes trailing separators; matching the raw spelling leaks exclusions.
    rel = normalize_relpath(relpath)
    if rel:
        rel = Path(rel).as_posix()
    pat = pattern.replace("\\", "/").strip()
    if not rel or not pat:
        return False

    if fnmatch(rel, pat):
        return True

    name = rel.rsplit("/", 1)[-1]

    if "/" not in pat:
        return fnmatch(name, pat)

    if pat.startswith("**/"):
        rest = pat[3:]
        if fnmatch(rel, rest) or fnmatch(name, rest):
            return True
        if rest.endswith("/**"):
            inner = rest[:-3]
            if inner and (rel == inner or rel.startswith(inner + "/") or f"/{inner}/" in f"/{rel}/"):
                return True
        if "/" not in rest.rstrip("/"):
            return fnmatch(name, rest)

    if pat.endswith("/**"):
        prefix = pat[:-3]
        if prefix.startswith("**/"):
            prefix = prefix[3:]
        if prefix and (rel == prefix or rel.startswith(prefix + "/")):
            return True

    return False


def is_excluded(relpath: str, exclusions: Sequence[Exclusion]) -> bool:
    """True when relpath matches any exclusion glob."""
    for item in exclusions:
        pattern = item if isinstance(item, str) else str(item.get("pattern") or "")
        if pattern and glob_match(relpath, pattern):
            return True
    return False


def get_exclusions(
    manifest: dict[str, Any],
    repo_name: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Global exclusions plus optional per-repo extra exclusions."""
    items: list[dict[str, Any]] = []
    for item in manifest.get("exclusions") or []:
        if isinstance(item, dict) and item.get("pattern"):
            items.append(item)
    if repo_name:
        override = (manifest.get("repo_overrides") or {}).get(repo_name) or {}
        for item in override.get("exclusions") or []:
            if isinstance(item, dict) and item.get("pattern"):
                items.append(item)
    return items


def get_extra_docs(
    manifest: dict[str, Any],
    repo_name: str,
) -> list[dict[str, Any]]:
    """Per-repo extra_docs include list (still subject to exclusions)."""
    override = (manifest.get("repo_overrides") or {}).get(repo_name) or {}
    docs = override.get("extra_docs") or []
    return [d for d in docs if isinstance(d, dict) and d.get("path")]


def path_is_contained(repo_path: Path, relpath: str) -> bool:
    """
    Fail-closed containment check.

    Returns False for empty, absolute, UNC, tilde, drive-letter, parent-escape,
    unreadable, or symlink-escaping paths. Non-existent paths are allowed when
    their normalized location would still sit inside the repo.
    """
    repo = repo_path.resolve()
    text = normalize_relpath(relpath)
    if not text:
        return False
    if text.startswith("/") or text.startswith("~") or text.startswith("//"):
        return False
    if len(text) >= 2 and text[1] == ":":
        return False

    if any(part in {"", ".", ".."} for part in text.rstrip("/").split("/")):
        return False
    parts = [part for part in text.split("/") if part]
    candidate = repo.joinpath(*parts) if parts else repo

    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(repo)
    except (OSError, ValueError, RuntimeError):
        return False

    probe = candidate
    try:
        # Reject every symlink component: aliases can hide excluded target paths.
        while probe != repo:
            if probe.is_symlink():
                return False
            probe = probe.parent
    except (OSError, ValueError, RuntimeError):
        return False

    return True


def filter_contained_relpaths(
    repo_path: Path,
    relpaths: Iterable[str],
    exclusions: Sequence[Exclusion],
) -> list[str]:
    """Keep only contained, non-excluded relative paths (stable order, unique)."""
    seen: set[str] = set()
    kept: list[str] = []
    for raw in relpaths:
        rel = normalize_relpath(raw)
        if not rel or rel in seen:
            continue
        if not path_is_contained(repo_path, rel):
            continue
        if is_excluded(rel, exclusions):
            continue
        seen.add(rel)
        kept.append(rel)
    return kept
