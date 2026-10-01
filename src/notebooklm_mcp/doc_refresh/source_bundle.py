"""Offline, manifest-selected documentation from immutable local Git objects.

No worktree content, notebook map, credentials, network or model is consulted.
GitHub revisions must already be fetched into the caller's local repository.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

from .discover import _validate_repo_root_spelling, discover_repo
from .drive_publication import Bundle, SourceText, render_bundle
from .manifest import _load_manifest_snapshot
from .selection import get_exclusions, is_excluded, normalize_relpath, path_is_contained


@dataclass(frozen=True)
class BundleArtifact:
    bundle: Bundle
    receipt: dict[str, Any]
    documents: tuple[SourceText, ...] = ()


def _git(repo: Path, *args: str) -> bytes:
    # Explicit local repository, no inherited Git routing/config injection,
    # replacement objects or implicit promisor-remote lazy fetches.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    try:
        result = subprocess.run(
            ["git", "--no-lazy-fetch", "--no-optional-locks", "--literal-pathspecs", "-C", str(repo), *args],
            env=env, capture_output=True, check=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"Local Git operation failed: {args[0]}") from exc
    return result.stdout


def _oid(raw: bytes) -> str:
    value = raw.decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
        raise ValueError("Expected a full Git object ID")
    return value


def _inventory(repo: Path, commit: str, root: Path) -> dict[str, tuple[str, str]]:
    """Build only empty path markers, never materialize unselected blob bytes.

    Preserve exact basename/entry identity for the existing selector. Refuse
    filesystem collisions (including case/Unicode aliases), never overwrite.
    Unsupported Git modes remain inert symlinks rejected by shared containment.
    """
    entries = {}
    for record in _git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, raw_oid = metadata.split()
        rel = raw_path.decode("utf-8")
        if (normalize_relpath(rel) != rel or Path(rel).as_posix() != rel
                or any(p.lower() == ".git" for p in Path(rel).parts)
                or not path_is_contained(root, rel)):
            raise ValueError("Git tree contains an ambiguous or unsafe path")
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not path_is_contained(root, rel):
            raise ValueError("Git tree path spelling collides on this filesystem")
        try:
            if mode in (b"100644", b"100755") and kind == b"blob":
                with target.open("xb"):
                    pass
            else:
                target.symlink_to("/__c021_unsupported_git_mode__")
        except FileExistsError as exc:
            raise ValueError("Git tree path collision") from exc
        entries[rel] = (mode.decode("ascii"), _oid(raw_oid))
    return entries


def build_bundle(repo: Path, revision: str, *, manifest_path: Path | None = None) -> BundleArtifact:
    """Select at one pinned commit; source revisions are exact blob object IDs.

    Dirty/untracked worktree bytes are deliberately irrelevant. Root aliases
    cannot change repo overrides. Receipts bind selection to the pinned commit;
    bundle text uses blob IDs so unrelated commits do not churn publication.
    """
    repo = Path(os.path.abspath(repo))  # Do not resolve away a root symlink.
    _validate_repo_root_spelling(repo)
    if not repo.is_dir():
        raise ValueError("Repository root does not exist")
    top = Path(os.fsdecode(_git(repo, "rev-parse", "--show-toplevel")).rstrip("\n"))
    if top.resolve() != repo.resolve():
        raise ValueError("Supply the repository root, not a subdirectory")
    if re.match(r"W0[0-9]{2}(?:_|$)", repo.name):
        raise ValueError("Quarantined W-series repositories are outside this CLI's scope")
    if not revision or revision.startswith("-"):
        raise ValueError("A Git commit revision is required")
    commit = _oid(_git(repo, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}"))
    manifest, manifest_hash = _load_manifest_snapshot(manifest_path)
    sources, source_records, excluded = [], [], []
    with tempfile.TemporaryDirectory(prefix="c021-bundle-") as temporary:
        root = Path(temporary) / repo.name
        root.mkdir()
        entries = _inventory(repo, commit, root)
        discovery = discover_repo(root, manifest, notebook_map={})
        if discovery.missing_required:
            raise ValueError("Missing required documentation: " + ", ".join(
                str(doc.path) for doc in discovery.missing_required))
        selected = set()
        for doc in discovery.docs:
            if not doc.exists:
                continue
            rel = doc.path.as_posix()
            if (root / rel).is_dir():
                # Only directory definitions (which can include scans) are containers.
                if rel in entries or doc.required:
                    raise ValueError(f"Required document is a directory: {rel}")
                continue
            if rel not in entries or entries[rel][0] not in {"100644", "100755"}:
                raise ValueError(f"Selected source is not a regular Git blob: {rel}")
            selected.add(rel)
        rules = get_exclusions(manifest, repo.name)
        for rel, (mode, blob) in sorted(entries.items()):
            if rel not in selected:
                reason = ("unsupported Git mode " + mode if mode not in {"100644", "100755"}
                          else "manifest exclusion" if is_excluded(rel, rules, root)
                          else "not selected by manifest")
                excluded.append({"path": rel, "reason": reason})
                continue
            raw = _git(repo, "cat-file", "blob", blob)
            algorithm = "sha1" if len(blob) == 40 else "sha256"
            actual = hashlib.new(algorithm, b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            if actual != blob:
                raise ValueError(f"Git blob integrity mismatch: {rel}")
            text = raw.decode("utf-8")
            sources.append(SourceText(repo.name, rel, blob, text))
            source_records.append({"path": rel, "blob_oid": blob, "sha256": hashlib.sha256(raw).hexdigest(),
                                   "byte_count": len(raw)})
        missing_optional = sorted(str(doc.path) for doc in discovery.docs if not doc.exists)
    bundle = render_bundle(f"{repo.name} documentation", sources)
    receipt = {
        "format": "c021.offline-source-bundle.v1", "repo": repo.name, "commit": commit,
        "manifest_hash_prefix": manifest_hash, "manifest_version": manifest["version"],
        "source_revision_kind": "git_blob", "source_count": bundle.source_count,
        "sources": source_records, "excluded": excluded, "missing_optional": missing_optional,
        "bundle_sha256": bundle.sha256, "artifact_id": f"sha256:{bundle.sha256}",
        "publication": {"drive_document_id": None, "notebook_id": None},
    }
    return BundleArtifact(bundle, receipt, tuple(sources))


def _write_identical_or_new(path: Path, content: bytes) -> None:
    if path.is_symlink():
        raise ValueError("Artifact path must not be a symlink")
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError(f"Conflicting existing artifact: {path}")


def write_artifacts(result: BundleArtifact, output: Path) -> dict[str, Path]:
    """Write content-addressed local artifacts; identical reruns are no-ops."""
    directory = output / result.receipt["repo"] / result.bundle.sha256
    for parent in [directory, *directory.parents]:
        if parent.is_symlink():
            raise ValueError("Artifact directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    raw_receipt = (json.dumps(result.receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    paths = {"bundle": directory / "bundle.md",
             "receipt": directory / (hashlib.sha256(raw_receipt).hexdigest() + ".json")}
    _write_identical_or_new(paths["bundle"], result.bundle.text.encode("utf-8"))
    _write_identical_or_new(paths["receipt"], raw_receipt)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", nargs=2, action="append", required=True, metavar=("PATH", "REVISION"),
                        help="Local repository root and commit/ref; repeat for batch mode")
    parser.add_argument("--manifest", type=Path, help="Accepted canonical_docs YAML (packaged default otherwise)")
    parser.add_argument("--output", type=Path, required=True, help="Local artifact directory outside source repos")
    args = parser.parse_args(argv)
    try:
        names = [Path(os.path.abspath(path)).name for path, _ in args.repo]
        if len(set(names)) != len(names):
            raise ValueError("Batch repository names must be unique")
        for path, _ in args.repo:
            if args.output.resolve().is_relative_to(Path(path).resolve()):
                raise ValueError("Output must be outside source repositories")
        results = [build_bundle(Path(path), revision, manifest_path=args.manifest) for path, revision in args.repo]
        # The user-supplied output can be outside a repo while its derived
        # OUTPUT/REPO/HASH destination is inside it (e.g. output=repo.parent).
        # Validate every destination against every input before any batch write.
        roots = [Path(path).resolve() for path, _ in args.repo]
        for result in results:
            destination = (args.output / result.receipt["repo"] / result.bundle.sha256).resolve()
            if any(destination.is_relative_to(root) for root in roots):
                raise ValueError("Derived artifact output must be outside source repositories")
        summaries = []
        for result in results:
            paths = write_artifacts(result, args.output)
            summaries.append({"repo": result.receipt["repo"], "commit": result.receipt["commit"],
                              "sha256": result.bundle.sha256, "source_count": result.bundle.source_count,
                              **{key: str(path.absolute()) for key, path in paths.items()}})
        print(json.dumps(summaries, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"Bundle generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
