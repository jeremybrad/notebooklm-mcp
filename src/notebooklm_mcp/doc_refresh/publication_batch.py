"""Explicit Git-to-Docs batches with redacted terminal operational receipts.

The caller supplies every path, immutable commit and (for live operations) a
reviewed transport factory. This module never finds credentials, discovers a
repository set, creates a destination or changes a binding. Planning is offline.
Receipt persistence failure raises even if remote work already completed; abrupt
process death can leave only the publication map's pending-operation evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, ContextManager, Sequence
import uuid

from . import publication_state as state
from .publication_state import DocsTransport, MapStore
from .source_bundle import BundleArtifact, build_bundle

MODES = frozenset({'plan', 'publish', 'reconcile', 'status'})


@dataclass(frozen=True)
class Job:
    repo: Path
    revision: str


class ReceiptError(OSError):
    """Terminal evidence could not be persisted; never treat the run as success."""


TransportFactory = Callable[[Job, str], ContextManager[DocsTransport]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _ReceiptSink:
    """Reserve a private temp file before work, then atomically publish once.

    Existing explicit directory only. The open directory descriptor anchors file
    operations; symlink components are refused. A same-directory hard link makes
    the completed JSON visible atomically without overwriting any existing run.
    The final name can be visible when a later directory fsync fails: the caller
    still receives ReceiptError, not a durability or successful-run claim.
    """
    def __init__(self, directory: Path, run_id: str, roots: list[Path]):
        self.directory_fd = self.file_fd = None
        self.owns_temporary = False
        self.temporary = '.publication-' + run_id + '.tmp'
        self.filename = 'publication-' + run_id + '.json'
        try:
            self.directory = Path(directory).absolute()
            if any(p.is_symlink() for p in [self.directory, *self.directory.parents]):
                raise ValueError('unsafe directory')
            if any(self.directory.resolve().is_relative_to(root.resolve()) for root in roots):
                raise ValueError('source repository output')
            self.directory_fd = os.open(
                self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self.file_fd = os.open(
                self.temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600, dir_fd=self.directory_fd)
            self.owns_temporary = True
            # Catch ordinary unwritable/full-disk/flush failures before cloud work.
            os.fsync(self.file_fd)
            os.fsync(self.directory_fd)
        except (Exception, KeyboardInterrupt):
            self.close()
            raise ReceiptError('publication_receipt_unavailable') from None

    def finish(self, result: dict[str, Any]) -> str:
        try:
            raw = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8')
            with os.fdopen(self.file_fd, 'wb', closefd=False) as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(self.temporary, self.filename, src_dir_fd=self.directory_fd,
                    dst_dir_fd=self.directory_fd, follow_symlinks=False)
            os.unlink(self.temporary, dir_fd=self.directory_fd)
            os.fsync(self.directory_fd)
            return str(self.directory / self.filename)
        except (Exception, KeyboardInterrupt):
            raise ReceiptError('publication_receipt_persistence_failed') from None

    def close(self) -> None:
        if self.file_fd is not None:
            try:
                os.close(self.file_fd)
            except OSError:
                pass
            self.file_fd = None
        if self.directory_fd is not None:
            if self.owns_temporary:
                try:
                    os.unlink(self.temporary, dir_fd=self.directory_fd)
                except OSError:
                    pass
            try:
                os.close(self.directory_fd)
            except OSError:
                pass
            self.directory_fd = None


class _BoundTransport:
    """A concurrent map edit cannot redirect an already-preflighted transport."""
    def __init__(self, transport: DocsTransport, document_id: str):
        self.transport, self.document_id = transport, document_id

    def _check(self, document_id: str) -> None:
        if document_id != self.document_id:
            raise state.StateConflict('Destination changed after batch preflight')

    def read(self, document_id: str) -> dict[str, Any]:
        self._check(document_id)
        return self.transport.read(document_id)

    def write(self, document_id: str, body: dict[str, Any]) -> None:
        self._check(document_id)
        self.transport.write(document_id, body)


def _failed(item: dict[str, Any], code: str) -> None:
    item.update(status='failed', error_code=code)


def _local(entry: dict[str, Any] | None, sha256: str) -> dict[str, Any]:
    docs = bool(entry and entry['pending'] is None and entry['verified']['sha256'] == sha256)
    notebook = bool(docs and entry['notebook'] and entry['notebook']['sha256'] == sha256)
    count = sum(1 for observation in entry['artifacts'].values()
                if notebook and observation['sha256'] == sha256
                and observation['source_id'] == entry['notebook']['source_id']) if entry else 0
    return {'docs_recorded_verified': docs, 'notebook_attested': notebook,
            'artifact_attestation_count': count}


def _entry(data: dict[str, Any], repo: str) -> dict[str, Any] | None:
    return data['notebooks'].get(repo, {}).get(state.KEY)


def _local_action(entry: dict[str, Any] | None, sha256: str) -> str:
    if entry is None:
        return 'unbound'
    if entry['pending'] is not None:
        return 'pending'
    return 'locally_unchanged' if entry['verified']['sha256'] == sha256 else 'changed'


def _run(result: dict[str, Any], jobs: Sequence[Job], store: MapStore,
         manifest_path: Path | None, transport_factory: TransportFactory | None,
         snapshots: dict[str, dict[str, Any]] | None) -> None:
    """Populate metadata only. Never serialize exceptions or source/remote text."""
    mode, items = result['mode'], result['items']
    if mode not in MODES or not jobs or not isinstance(store, MapStore):
        result['error_code'] = 'invalid_request'
        return
    seen: set[str] = set()
    for job in jobs:
        item = {'repo': None, 'commit': None, 'bundle_sha256': None,
                'action': 'not_attempted', 'status': 'not_attempted',
                'verification': 'local-state' if mode == 'status' else 'offline'}
        items.append(item)
        if not isinstance(job, Job) or not isinstance(job.repo, Path):
            _failed(item, 'invalid_job')
            continue
        name = job.repo.absolute().name
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', name):
            _failed(item, 'invalid_repository_name')
            continue
        item['repo'] = name
        if not isinstance(job.revision, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', job.revision):
            _failed(item, 'immutable_commit_required')
            continue
        item['commit'] = job.revision
        if name in seen:
            _failed(item, 'duplicate_repository')
        seen.add(name)
    if snapshots is not None and (not isinstance(snapshots, dict)
                                  or any(name not in seen for name in snapshots)):
        result['error_code'] = 'invalid_snapshots'
        return
    if any(item['status'] == 'failed' for item in items):
        return
    if any(store.path.resolve().is_relative_to(job.repo.resolve()) for job in jobs):
        result['error_code'] = 'invalid_map_location'
        return
    # Validate every requested source before constructing even the first client.
    bundles: list[BundleArtifact | None] = []
    for job, item in zip(jobs, items):
        try:
            generated = build_bundle(job.repo, job.revision, manifest_path=manifest_path)
            if generated.receipt['commit'] != job.revision:
                raise ValueError('Commit object required')
            bundles.append(generated)
            item.update(bundle_sha256=generated.bundle.sha256,
                        source_count=generated.bundle.source_count,
                        manifest_hash_prefix=generated.receipt['manifest_hash_prefix'])
        except KeyboardInterrupt:
            _failed(item, 'interrupted')
            return
        except Exception:
            bundles.append(None)
            _failed(item, 'source_preflight_failed')
    if any(item['status'] == 'failed' for item in items):
        return
    try:
        data = store.read().data
    except KeyboardInterrupt:
        result['error_code'] = 'interrupted'
        return
    except Exception:
        result['error_code'] = 'map_unavailable'
        return
    for item in items:
        entry = _entry(data, item['repo'])
        item['freshness'] = _local(entry, item['bundle_sha256'])
        item['planned_action'] = _local_action(entry, item['bundle_sha256'])
    # Check all existing bindings/pending intents before any operation mutates.
    if mode in {'publish', 'reconcile'}:
        for item in items:
            entry = _entry(data, item['repo'])
            if entry is None:
                _failed(item, 'missing_binding')
            elif mode == 'publish' and entry['pending'] is not None:
                _failed(item, 'pending_operation')
            elif mode == 'reconcile':
                original = (entry['pending']['target_sha256'] if entry['pending']
                            else entry['verified']['sha256'])
                if original != item['bundle_sha256']:
                    _failed(item, 'original_bundle_required')
        if any(item['status'] == 'failed' for item in items):
            return
        if transport_factory is None:
            result['error_code'] = 'transport_unconfigured'
            return
    for job, generated, item in zip(jobs, bundles, items):
        entry = _entry(data, item['repo'])
        item['freshness'] = _local(entry, generated.bundle.sha256)
        if mode in {'plan', 'status'}:
            item['action'] = _local_action(entry, generated.bundle.sha256)
            if mode == 'plan' and snapshots is not None and item['repo'] in snapshots:
                try:
                    plan = state.prepare(store, item['repo'], generated.bundle,
                                         snapshots[item['repo']])
                    item.update(action=plan.action, snapshot_checked=True)
                except KeyboardInterrupt:
                    _failed(item, 'interrupted')
                    break
                except Exception:
                    _failed(item, 'snapshot_invalid_or_conflicting')
                    continue
            item['status'] = 'success'
            continue
        phase = 'transport_initialization_failed'
        action = None
        item['action'] = mode
        try:
            with transport_factory(job, entry['document_id']) as transport:
                phase = 'publication_failed' if mode == 'publish' else 'reconciliation_failed'
                operation = state.publish if mode == 'publish' else state.reconcile
                action = operation(store, item['repo'], generated.bundle,
                                   _BoundTransport(transport, entry['document_id']))
                phase = 'transport_finalization_failed'
            # A context manager must not silently suppress an operation failure.
            if action is None:
                raise ValueError('Operation did not complete')
            phase = 'map_unavailable'
            data = store.read().data
            item.update(action=action, status='success', verification='remote',
                        freshness=_local(_entry(data, item['repo']), generated.bundle.sha256))
        except KeyboardInterrupt:
            _failed(item, 'interrupted')
            break
        except Exception:
            _failed(item, phase)
            break


def execute(mode: str, jobs: Sequence[Job], store: MapStore, receipt_dir: Path, *,
            manifest_path: Path | None = None,
            transport_factory: TransportFactory | None = None,
            snapshots: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run an explicit batch and return its redacted terminal receipt plus path.

    Use ``mode='plan'`` for default offline planning; supplied snapshots are
    validated but are never called current remote evidence. ``status`` compares
    local recorded hashes with the requested Git bundles. Success for these
    modes means the report completed, not that Docs or artifacts are current.
    Live modes require an injected context-manager factory. Both stop after the
    first operation failure. Reconciliation reads remotely and never replays a
    write. No mode can bind/create a Doc. All sources and bindings preflight
    before live work. Jobs require full commit IDs, never moving refs or tag IDs.

    The map must be outside every source repository, as must the explicit receipt
    directory, which must already exist.
    On-disk receipts omit absolute paths, source bodies and credential material;
    only the returned copy adds ``receipt_path``. ReceiptError is redacted and
    means success cannot be reported, even when publication already took place.
    """
    run_id = uuid.uuid4().hex
    safe_mode = mode if isinstance(mode, str) and mode in MODES else 'invalid'
    valid_sequence = isinstance(jobs, (tuple, list))
    selected = jobs if valid_sequence else []
    roots = [job.repo for job in selected if isinstance(job, Job) and isinstance(job.repo, Path)]
    result: dict[str, Any] = {
        'format': 'c021.publication-batch.v1', 'run_id': run_id, 'mode': safe_mode,
        'started_at': _now(), 'status': 'failed', 'exit_code': 1,
        'verification': 'local-state' if mode == 'status' else 'offline', 'items': [],
    }
    sink = _ReceiptSink(receipt_dir, run_id, roots)
    try:
        try:
            _run(result, selected, store, manifest_path, transport_factory, snapshots)
        except KeyboardInterrupt:
            result['error_code'] = 'interrupted'
        except Exception:
            result['error_code'] = 'batch_failed'
        items = result['items']
        success = bool(items) and 'error_code' not in result and all(
            item['status'] == 'success' for item in items)
        interrupted = result.get('error_code') == 'interrupted' or any(
            item.get('error_code') == 'interrupted' for item in items)
        result.update(status='success' if success else 'failed',
                      exit_code=0 if success else 130 if interrupted else 1,
                      completed_at=_now(),
                      all_docs_recorded_verified=bool(items) and all(
                          item.get('freshness', {}).get('docs_recorded_verified', False)
                          for item in items),
                      remote_verified_count=sum(item['verification'] == 'remote' for item in items))
        if result['remote_verified_count']:
            result['verification'] = 'remote'
        result['receipt_path'] = sink.finish(result)
        return result
    finally:
        sink.close()
