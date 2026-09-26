"""Explicit publisher commands; credential access requires a selected configuration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .publication_batch import Job, ReceiptError, execute
from .publication_state import MapStore
from .publication_credentials import ProviderError, load_config, transport_factory


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key")
        result[key] = value
    return result


def _snapshots(path: Path) -> dict[str, Any]:
    # Explicit local input only. Do not print its contents or parser exceptions.
    with path.open("rb") as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("Snapshot input exceeds limit")
    def reject_nonfinite(_value):
        raise ValueError("Nonfinite value")

    value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=reject_nonfinite)
    if not isinstance(value, dict) or any(not isinstance(v, dict) for v in value.values()):
        raise ValueError("Expected repository-to-document mapping")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="plan", choices=("plan", "publish", "reconcile", "status"))
    parser.add_argument("--repo", nargs=2, action="append", required=True, metavar=("PATH", "FULL_COMMIT"))
    parser.add_argument("--map", required=True, type=Path, dest="map_path")
    parser.add_argument("--receipts", required=True, type=Path,
                        help="Existing local receipt directory outside source repositories")
    parser.add_argument("--manifest", type=Path, help="Explicit accepted source-selection manifest")
    parser.add_argument("--snapshots", type=Path, help="Offline plan only: complete native Docs JSON by repository name")
    parser.add_argument("--credentials-config", type=Path,
                        help="Live modes only: explicit nonsecret OAuth/Keychain configuration")
    args = parser.parse_args(argv)
    if args.snapshots and args.mode != "plan":
        parser.error("--snapshots is only valid with plan")
    if args.credentials_config and args.mode not in {"publish", "reconcile"}:
        parser.error("--credentials-config is only valid with publish/reconcile")
    try:
        snapshots = _snapshots(args.snapshots) if args.snapshots else None
    except (OSError, ValueError, RecursionError):
        print("Invalid snapshot input", file=sys.stderr)
        return 2
    try:
        factory = transport_factory(load_config(args.credentials_config, live=True)) \
            if args.credentials_config else None
    except ProviderError:
        print("Invalid credential configuration", file=sys.stderr)
        return 2
    try:
        result = execute(args.mode, [Job(Path(path), revision) for path, revision in args.repo],
                         MapStore(args.map_path), args.receipts, manifest_path=args.manifest,
                         snapshots=snapshots, transport_factory=factory)
    except ReceiptError:
        print("Receipt persistence failed; no successful run is claimed", file=sys.stderr)
        return 1
    # No token/provider-module argument, environment discovery or implicit consent.
    print(json.dumps(result, sort_keys=True, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
