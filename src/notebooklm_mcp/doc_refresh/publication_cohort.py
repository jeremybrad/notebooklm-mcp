"""Explicit cohort preflight; no credential access, installation or state registry."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from typing import Iterator

from .manifest import load_manifest
from .publication_batch import Job
from .publication_state import KEY, MapStore


class CohortError(ValueError):
    """Stable, credential-free preflight failure."""


@dataclass(frozen=True)
class PreparedCohort:
    jobs: tuple[Job, ...]
    manifest: Path
    manifest_sha256: str
    freshness: str


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CohortError('duplicate_configuration_key')
        result[key] = value
    return result


def _read(path: Path, limit: int) -> bytes:
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise CohortError('unsafe_configuration_path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise CohortError('unsafe_configuration_path')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
    finally:
        os.close(fd)
    if len(raw) > limit:
        raise CohortError('configuration_too_large')
    return raw


def _git(root: Path, *args: str) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1',
               GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    try:
        result = subprocess.run(
            ['git', '--no-lazy-fetch', '--no-optional-locks', '-C', str(root),
             '-c', 'core.hooksPath=/dev/null', '-c', 'protocol.allow=never',
             '-c', 'protocol.https.allow=always', '-c', 'protocol.ssh.allow=always',
             '-c', 'core.sshCommand=/usr/bin/ssh -oBatchMode=yes',
             '-c', 'credential.interactive=false', *args],
            env=env, capture_output=True, timeout=120, check=True)
        return result.stdout.decode('utf-8').strip()
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise CohortError('git_operation_failed') from None


def _entries(value):
    if not isinstance(value, dict) or set(value) != {'version', 'manifest', 'repositories'} \
            or type(value['version']) is not int or value['version'] != 1:
        raise CohortError('invalid_configuration')
    manifest = value['manifest']
    if not isinstance(manifest, dict) or set(manifest) != {'path', 'sha256'} \
            or not isinstance(manifest['path'], str) \
            or not isinstance(manifest['sha256'], str) \
            or not re.fullmatch('[0-9a-f]{64}', manifest['sha256']):
        raise CohortError('invalid_manifest_pin')
    entries = value['repositories']
    if not isinstance(entries, list) or not 1 <= len(entries) <= 128:
        raise CohortError('invalid_repository_set')
    seen_names, seen_roots = set(), set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'root', 'name', 'origin', 'branch'} \
                or any(not isinstance(v, str) for v in entry.values()):
            raise CohortError('invalid_repository')
        name, root = entry['name'], Path(entry['root'])
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}', name) \
                or re.match(r'W0[0-9]{2}(?:_|$)', name) \
                or not root.is_absolute() or root.name != name \
                or '..' in root.parts or any(p.is_symlink() for p in (root, *root.parents)):
            raise CohortError('invalid_repository_identity')
        if name in seen_names or root.resolve() in seen_roots:
            raise CohortError('duplicate_repository')
        seen_names.add(name)
        seen_roots.add(root.resolve())
        # This host rollout supports the registered GitHub transport only. In
        # particular, never permit local paths, remote helpers or URL userinfo.
        if not re.fullmatch(r'(?:https://github\.com/|git@github\.com:)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', entry['origin']):
            raise CohortError('unsupported_origin')
        branch = entry['branch']
        if not branch.startswith('refs/heads/') or _git(root, 'check-ref-format', branch):
            raise CohortError('invalid_branch')
        if Path(_git(root, 'rev-parse', '--show-toplevel')) != root:
            raise CohortError('repository_root_mismatch')
        # Both literal and effective URL must match: configured URL rewriting
        # cannot silently redirect a governed fetch to another destination.
        if _git(root, 'config', '--get-all', 'remote.origin.url') != entry['origin'] \
                or _git(root, 'remote', 'get-url', '--all', 'origin') != entry['origin']:
            raise CohortError('origin_mismatch')
    return entries


@contextmanager
def prepare(path: Path, *, fetch: bool = False) -> Iterator[PreparedCohort]:
    """Capture inspected manifest bytes and resolve every source exactly once.

    Offline by default; an explicit fetch updates only configured remote-tracking
    refs, never local branches/worktrees. All fetches must succeed before yielding.
    The private temporary manifest is discarded, not a second durable registry.
    """
    try:
        value = json.loads(_read(Path(path), 256 * 1024), object_pairs_hook=_pairs)
        entries = _entries(value)
        raw = _read(Path(value['manifest']['path']), 4 * 1024 * 1024)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != value['manifest']['sha256']:
            raise CohortError('manifest_hash_mismatch')
        jobs = []
        for entry in entries:
            root, branch = Path(entry['root']), entry['branch']
            ref = 'refs/remotes/origin/' + branch.removeprefix('refs/heads/')
            if fetch:
                # The URL was approved and checked against origin above. Passing
                # it explicitly also prevents concurrent origin edits redirecting
                # this request. Disable recursive submodule requests and tags.
                _git(root, 'fetch', '--no-tags', '--no-recurse-submodules',
                     '--no-write-fetch-head', '--', entry['origin'], branch + ':' + ref)
            revision = _git(root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}')
            if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', revision):
                raise CohortError('invalid_resolved_revision')
            jobs.append(Job(root, revision))
    except CohortError:
        raise
    except (OSError, ValueError, TypeError, RecursionError):
        raise CohortError('invalid_configuration') from None
    with tempfile.TemporaryDirectory(prefix='c021-cohort-') as directory:
        snapshot = Path(directory) / 'manifest.yaml'
        snapshot.write_bytes(raw)
        snapshot.chmod(0o600)
        try:
            load_manifest(snapshot)
        except Exception:
            raise CohortError('invalid_manifest') from None
        yield PreparedCohort(tuple(jobs), snapshot, digest,
                             'fetched-origin' if fetch else 'unverified-local-ref')


def validate_destinations(prepared: PreparedCohort, store: MapStore, config) -> None:
    """Validate every configured map/Doc binding before opening any provider."""
    try:
        data = store.read().data
        for job in prepared.jobs:
            entry = data['notebooks'].get(job.repo.name, {}).get(KEY)
            destination = config.destinations.get(job.repo.name)
            if entry is None or destination is None:
                raise CohortError('missing_destination_binding')
            if entry['document_id'] != destination.document_id:
                raise CohortError('destination_binding_mismatch')
    except CohortError:
        raise
    except Exception:
        raise CohortError('invalid_destination_map') from None
