"""Opt-in, offline-testable Docs lifecycle in the existing notebook map.

No default path, credentials, HTTP implementation, CLI or runner wiring. Writers
using this module serialize on the existing parent directory (POSIX flock), not
a new lock registry. Legacy/uncooperative writers MUST be quiesced before use.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Iterator, Protocol
import uuid

import yaml

from .drive_publication import (
    Bundle, DocsBinding, DocsSnapshot, UpdatePlan, parse_document, plan_update,
    verify_readback,
)

KEY = 'drive_publication'
MAX_BYTES = 4 * 1024 * 1024


class StateError(ValueError):
    """Invalid or unreconciled state; do not publish."""


class StateConflict(StateError):
    """The caller's snapshot no longer describes the on-disk map."""


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _label(value: Any) -> None:
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise StateError('Expected nonempty single-line identifier/evidence')


def _hash(value: Any) -> None:
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise StateError('Expected full SHA-256')


def _keys(value: Any, required: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != required:
        raise StateError('Unsupported publication state shape')


def _json_tree(value: Any, depth: int = 0) -> None:
    if depth > 40:
        raise StateError('Map nesting limit exceeded')
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise StateError('Map keys must be strings')
            _json_tree(v, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _json_tree(item, depth + 1)
    elif type(value) not in (str, int, bool, float, type(None)):
        raise StateError('Map values must be JSON-compatible')
    elif isinstance(value, float) and not math.isfinite(value):
        raise StateError('Nonfinite map value')


def validate_map(data: Any) -> None:
    """Validate the whole extension; preserve opaque JSON-compatible legacy data."""
    _json_tree(data)
    if not isinstance(data, dict) or not isinstance(data.get('notebooks'), dict):
        raise StateError('Map requires a notebooks mapping')
    if 'config' in data and not isinstance(data['config'], dict):
        raise StateError('Map config must be a mapping')
    if 'sync_log' in data and not isinstance(data['sync_log'], list):
        raise StateError('Map sync_log must be a list')
    destinations = set()
    for repo, record in data['notebooks'].items():
        _label(repo)
        if not isinstance(record, dict):
            raise StateError('Repository entry must be a mapping')
        if KEY not in record:
            continue
        _label(record.get('notebook_id'))
        entry = record[KEY]
        _keys(entry, {'version', 'document_id', 'tab_id', 'verified', 'pending', 'notebook', 'artifacts'})
        if type(entry['version']) is not int or entry['version'] != 1:
            raise StateError('Unsupported publication state version')
        _label(entry['document_id'])
        _label(entry['tab_id'])
        if entry['document_id'] in destinations:
            raise StateError('A Doc cannot be bound to multiple repositories')
        destinations.add(entry['document_id'])
        _keys(entry['verified'], {'sha256', 'revision_id'})
        _hash(entry['verified']['sha256'])
        _label(entry['verified']['revision_id'])
        pending = entry['pending']
        if pending is not None:
            _keys(pending, {'operation_id', 'base_sha256', 'base_revision_id', 'target_sha256'})
            if not isinstance(pending['operation_id'], str) or not re.fullmatch('[0-9a-f]{32}', pending['operation_id']):
                raise StateError('Invalid operation ID')
            _hash(pending['target_sha256'])
            if pending['base_sha256'] != entry['verified']['sha256']:
                raise StateError('Pending base hash does not match verified state')
            _label(pending['base_revision_id'])
        notebook = entry['notebook']
        if notebook is not None:
            _keys(notebook, {'sha256', 'source_id', 'evidence'})
            _hash(notebook['sha256'])
            _label(notebook['source_id'])
            _label(notebook['evidence'])
        if not isinstance(entry['artifacts'], dict):
            raise StateError('Artifacts must be a mapping')
        for artifact, evidence in entry['artifacts'].items():
            _label(artifact)
            _keys(evidence, {'sha256', 'source_id', 'evidence'})
            _hash(evidence['sha256'])
            _label(evidence['source_id'])
            _label(evidence['evidence'])


class _Loader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise StateError('YAML aliases are not supported in publication maps')
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise StateError('Duplicate or non-string map key')
            result[key] = self.construct_object(value_node, deep=deep)
        return result


@dataclass(frozen=True)
class MapSnapshot:
    data: dict[str, Any]
    raw: bytes | None


class MapStore:
    """Explicit-path store. Parent must already exist for writes, never reads.

    Parent directory locks serialize cooperating processes across file replacement.
    Compare exact bytes as well, refusing edits observed from noncooperating code.
    No algorithm here can make an arbitrary noncooperating writer safe; activation
    must retire/quiesce that writer first. This module is deliberately unwired.
    """
    def __init__(self, path: Path):
        self.path = Path(path).absolute()

    def read(self) -> MapSnapshot:
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return MapSnapshot({'notebooks': {}}, None)
        except OSError as exc:
            raise StateError('Cannot safely open publication map') from exc
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise StateError('Publication map must be a regular file')
            with os.fdopen(fd, 'rb', closefd=False) as handle:
                raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise StateError('Publication map size limit exceeded')
        finally:
            os.close(fd)
        try:
            data = yaml.load(raw.decode('utf-8'), Loader=_Loader)
            validate_map(data)
        except (yaml.YAMLError, UnicodeError, RecursionError) as exc:
            raise StateError('Malformed publication map') from exc
        return MapSnapshot(data, raw)

    @contextmanager
    def transaction(self) -> Iterator[_Transaction]:
        # Explicitly POSIX only; no silent unlocked fallback on other platforms.
        import fcntl

        fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        transaction = _Transaction(self, fd)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield transaction
        except BlockingIOError as exc:
            raise StateConflict('Publication map directory is busy') from exc
        finally:
            transaction.active = False
            os.close(fd)


class _Transaction:
    def __init__(self, store: MapStore, directory_fd: int):
        self.store, self.directory_fd = store, directory_fd
        self.active = True

    def save(self, expected: MapSnapshot, data: dict[str, Any]) -> MapSnapshot:
        if not self.active:
            raise StateError('Transaction is closed')
        validate_map(data)
        raw = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).encode('utf-8')
        if len(raw) > MAX_BYTES:
            raise StateError('Publication map size limit exceeded')
        if self.store.read().raw != expected.raw:
            raise StateConflict('Publication map changed since planning')
        fd, name = tempfile.mkstemp(prefix=self.store.path.name + '.', suffix='.tmp', dir=self.store.path.parent)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            if self.store.read().raw != expected.raw:
                raise StateConflict('Publication map changed before commit')
            os.replace(name, self.store.path)
            os.fsync(self.directory_fd)
        finally:
            Path(name).unlink(missing_ok=True)
        return MapSnapshot(deepcopy(data), raw)


class DocsTransport(Protocol):
    """Injected implementation must return complete native Docs responses.

    Writes MUST enforce requiredRevisionId. No implementation is shipped here.
    """
    def read(self, document_id: str) -> dict[str, Any]: ...
    def write(self, document_id: str, body: dict[str, Any]) -> None: ...


def _entry(data: dict[str, Any], repo: str) -> dict[str, Any]:
    try:
        return data['notebooks'][repo][KEY]
    except KeyError as exc:
        raise StateError('Repository has no explicit Docs binding') from exc


def bind_empty(store: MapStore, repo: str, notebook_id: str, raw: dict[str, Any]) -> None:
    """Explicit adoption of a caller-read EMPTY Doc only. Never creates cloud objects."""
    _label(repo)
    _label(notebook_id)
    remote = parse_document(raw)
    if remote.text != '\n':
        raise StateError('Nonempty Doc adoption requires separate reconciliation')
    with store.transaction() as tx:
        before = store.read()
        data = deepcopy(before.data)
        record = data['notebooks'].setdefault(repo, {})
        if KEY in record or record.get('notebook_id', notebook_id) != notebook_id:
            raise StateError('Existing binding cannot be replaced')
        record['notebook_id'] = notebook_id
        record[KEY] = {
            'version': 1, 'document_id': remote.document_id, 'tab_id': remote.tab_id,
            'verified': {'sha256': digest(remote.text), 'revision_id': remote.revision_id},
            'pending': None, 'notebook': None, 'artifacts': {},
        }
        tx.save(before, data)


def prepare(store: MapStore, repo: str, bundle: Bundle, raw: dict[str, Any]) -> UpdatePlan:
    """Read-only planning from supplied source/remote bytes, with no transport calls."""
    entry = _entry(store.read().data, repo)
    if entry['pending'] is not None:
        raise StateError('Pending operation requires explicit reconciliation')
    return plan_update(bundle, parse_document(raw), DocsBinding(
        entry['document_id'], entry['tab_id'], entry['verified']['sha256']))


def publish(store: MapStore, repo: str, bundle: Bundle, transport: DocsTransport) -> str:
    """Persist intent before any cloud write; promote only exact verified readback.

    Any exception is failure. If a write or local save has uncertain outcome,
    do not retry automatically: use reconcile with the SAME bundle explicitly.
    """
    with store.transaction() as tx:
        before = store.read()
        data = deepcopy(before.data)
        entry = _entry(data, repo)
        if entry['pending'] is not None:
            raise StateError('Pending operation requires explicit reconciliation')
        remote = parse_document(transport.read(entry['document_id']))
        plan = plan_update(bundle, remote, DocsBinding(
            entry['document_id'], entry['tab_id'], entry['verified']['sha256']))
        if plan.body is not None:
            entry['pending'] = {
                'operation_id': uuid.uuid4().hex,
                'base_sha256': entry['verified']['sha256'],
                'base_revision_id': remote.revision_id, 'target_sha256': bundle.sha256,
            }
            before = tx.save(before, data)
            transport.write(plan.document_id, deepcopy(plan.body))
            remote = parse_document(transport.read(plan.document_id))
        verified = verify_readback(plan, remote)
        entry['verified'] = {'sha256': verified, 'revision_id': remote.revision_id}
        entry['pending'] = None
        # Old notebook/artifact attestations remain bound to their old hashes.
        tx.save(before, data)
        return plan.action


def reconcile(store: MapStore, repo: str, bundle: Bundle, transport: DocsTransport) -> str:
    """Read-only remote reconciliation; never retries a write or adopts manual edits.

    Target present => record verified success. Unchanged base at the exact original
    revision => clear unexecuted intent. Any other observation keeps pending intact.
    """
    with store.transaction() as tx:
        before = store.read()
        data = deepcopy(before.data)
        entry = _entry(data, repo)
        pending = entry['pending']
        expected_hash = pending['target_sha256'] if pending else entry['verified']['sha256']
        if expected_hash != bundle.sha256:
            raise StateError('Reconciliation requires the original pending bundle')
        # Validate bundle with the same planner before even a remote read.
        plan = plan_update(bundle, DocsSnapshot(
            entry['document_id'], entry['tab_id'], 'validation-only', bundle.text),
            DocsBinding(entry['document_id'], entry['tab_id'], bundle.sha256))
        remote = parse_document(transport.read(entry['document_id']))
        if (remote.document_id, remote.tab_id) != (entry['document_id'], entry['tab_id']):
            raise StateError('Reconciliation destination mismatch')
        if remote.text == bundle.text:
            verified = verify_readback(plan, remote)
            entry['verified'] = {'sha256': verified, 'revision_id': remote.revision_id}
            result = 'verified_target' if pending else 'already_verified'
        elif (pending and digest(remote.text) == pending['base_sha256']
              and remote.revision_id == pending['base_revision_id']):
            result = 'unchanged_base'
        else:
            raise StateError('Remote state is ambiguous; pending evidence retained')
        entry['pending'] = None
        tx.save(before, data)
        return result


def record_observation(store: MapStore, repo: str, sha256: str, source_id: str,
                       evidence: str, *, artifact_id: str | None = None) -> None:
    """Record an explicit caller attestation, NOT an automatic NotebookLM check.

    A source citation attestation must precede an artifact attestation. Evidence
    identifies the caller's durable verification record; it is not fetched here.
    """
    _hash(sha256)
    _label(source_id)
    _label(evidence)
    if artifact_id is not None:
        _label(artifact_id)
    with store.transaction() as tx:
        before = store.read()
        data = deepcopy(before.data)
        entry = _entry(data, repo)
        if entry['pending'] is not None or entry['verified']['sha256'] != sha256:
            raise StateError('Observation is not for the current verified Docs version')
        observation = {'sha256': sha256, 'source_id': source_id, 'evidence': evidence}
        if artifact_id is None:
            if entry['notebook'] and entry['notebook']['source_id'] != source_id:
                raise StateError('Stable source association cannot be replaced implicitly')
            entry['notebook'] = observation
        else:
            if not entry['notebook'] or any(entry['notebook'][k] != observation[k] for k in ('sha256', 'source_id')):
                raise StateError('Current source verification required before artifact verification')
            if artifact_id in entry['artifacts']:
                raise StateError('Artifact observation is immutable')
            entry['artifacts'][artifact_id] = observation
        tx.save(before, data)


def freshness(store: MapStore, expected: dict[str, str]) -> dict[str, Any]:
    """Report each layer against explicit expected hashes, never a generic success."""
    if not expected:
        raise StateError('Expected publication set cannot be empty')
    data = store.read().data
    results = {}
    for repo, sha256 in expected.items():
        _hash(sha256)
        entry = data['notebooks'].get(repo, {}).get(KEY)
        docs = bool(entry and entry['pending'] is None and entry['verified']['sha256'] == sha256)
        notebook = bool(docs and entry['notebook'] and entry['notebook']['sha256'] == sha256)
        results[repo] = {
            'docs_verified': docs, 'notebook_attested': notebook,
            'artifact_attestations': sorted(k for k, v in entry['artifacts'].items()
                if notebook and v['sha256'] == sha256 and v['source_id'] == entry['notebook']['source_id']) if entry else [],
        }
    return {'all_docs_verified': all(v['docs_verified'] for v in results.values()), 'repos': results}
