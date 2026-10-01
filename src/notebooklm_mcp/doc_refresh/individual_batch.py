"""Explicit per-document batches using existing Git selection, map and receipts.

No file creation/enrollment/cohort/scheduler. Source and destination preflight for
all items completes before the first credential access. Failures stop the batch.
"""
from dataclasses import dataclass
from pathlib import Path
import os
import re
import uuid

from . import individual_publication as state
from .publication_batch import Job, _ReceiptSink, _now
from .publication_state import StateError
from .source_bundle import build_bundle


@dataclass(frozen=True)
class DocumentJob:
    repo: Path
    revision: str
    source: object


def execute(mode, jobs, store, receipt_dir, *, manifest_path, transport_factory=None, config=None):
    if mode not in {'plan', 'status', 'publish', 'reconcile'} or manifest_path is None:
        raise StateError('Explicit individual mode and manifest required')
    # Match build_bundle's lexical normalization before deriving any identity.
    jobs = [Job(Path(os.path.abspath(j.repo)), j.revision) for j in jobs]
    if (not jobs or len({str(j.repo) for j in jobs}) != len(jobs)
            or len({j.repo.name for j in jobs}) != len(jobs)):
        raise StateError('Unique explicit repositories required')
    run_id = uuid.uuid4().hex
    sink = _ReceiptSink(receipt_dir, run_id, [j.repo for j in jobs])
    result = {'format':'c021.individual-publication-batch.v1', 'run_id':run_id,
              'mode':mode, 'started_at':_now(), 'items':[], 'status':'failed', 'exit_code':1}
    prepared = []
    try:
        try:
            snapshot = store.read()
            for job in jobs:
                if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', job.revision):
                    raise StateError('Full immutable commit required')
                if store.path.resolve().is_relative_to(job.repo.resolve()):
                    raise StateError('Publication map must be outside source repo')
                artifact = build_bundle(job.repo, job.revision, manifest_path=manifest_path)
                bound = snapshot.data['notebooks'].get(job.repo.name, {}).get(state.KEY, {})
                selected_paths = {source.path for source in artifact.documents}
                if mode in {'publish', 'reconcile'} and set(bound) - selected_paths:
                    raise StateError('Previously bound original missing from inspected selection')
                for source in artifact.documents:
                    key = state.document_key(source)
                    raw, provenance = state._target(source, artifact.receipt)
                    entry = snapshot.data['notebooks'].get(source.repo, {}).get(state.KEY, {}).get(source.path)
                    action = 'unbound' if entry is None else 'pending' if entry['pending'] else (
                        'locally_unchanged' if entry['verified']['sha256'] == state.digest(raw) else 'changed')
                    item = {'repo':source.repo,'path':source.path,'commit':artifact.receipt['commit'],
                            'blob_oid':source.source_revision,'sha256':state.digest(raw),
                            'manifest_hash_prefix':artifact.receipt['manifest_hash_prefix'],
                            'action':action,'status':'not_attempted','verification':'offline'}
                    result['items'].append(item)
                    if mode in {'publish', 'reconcile'}:
                        if entry is None or transport_factory is None: raise StateError('Live explicit binding/factory required')
                        if mode == 'publish' and entry['pending'] is not None: raise StateError('Pending recovery required')
                        if mode == 'reconcile' and (entry['pending'] is None
                            or entry['pending']['target_sha256'] != state.digest(raw)
                            or entry['pending']['source'] != provenance): raise StateError('Original pending input required')
                        if config is not None:
                            destination = config.destinations.get(key)
                            if destination is None or destination.document_id != entry['file_id']:
                                raise StateError('Inspected destination configuration required')
                    prepared.append((DocumentJob(job.repo, job.revision, source),artifact,entry,item))
            if not prepared: raise StateError('No selected originals')
        except Exception:
            result['error'] = 'individual_preflight_failed'
        else:
            for job, artifact, entry, item in prepared:
                if mode in {'plan','status'}: item['status'] = 'success'; continue
                try:
                    with transport_factory(job, entry['file_id']) as transport:
                        operation = state.publish if mode == 'publish' else state.reconcile
                        item['action'] = operation(store,job.source,artifact.receipt,transport)
                    item.update(status='success',verification='remote')
                except Exception:
                    item.update(status='failed', error='individual_operation_failed')
                    break
            if all(i['status']=='success' for i in result['items']):
                result.update(status='success',exit_code=0)
        result['completed_at'] = _now()
        result['receipt_path'] = sink.finish(result)
        return result
    finally: sink.close()
