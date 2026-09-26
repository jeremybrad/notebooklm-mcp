"""Explicit, synthetic Git-to-Docs batches; never use credentials or real state."""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess

import pytest

from notebooklm_mcp.doc_refresh import publication_batch as batch
from notebooklm_mcp.doc_refresh.publication_state import KEY, MapStore, bind_empty
from notebooklm_mcp.doc_refresh.source_bundle import build_bundle
from tests.test_drive_publication import apply_requests, document
from tests.test_source_bundle import commit, git, repo


class FakeDocs:
    def __init__(self, document_id='synthetic-doc'):
        self.raw = document(document_id=document_id)
        self.reads = self.writes = 0
        self.fail_before_write = self.fail_after_write = False

    def read(self, document_id):
        assert document_id == self.raw['documentId']
        self.reads += 1
        return deepcopy(self.raw)

    def write(self, document_id, body):
        from types import SimpleNamespace
        assert document_id == self.raw['documentId']
        self.writes += 1
        if self.fail_before_write:
            raise OSError('secret-token source-body /private/source/path')
        self.raw = apply_requests(SimpleNamespace(body=body), self.raw)
        self.raw['revisionId'] = 'r' + str(self.writes + 1)
        if self.fail_after_write:
            raise OSError('secret-token source-body /private/source/path')


@pytest.fixture
def managed(repo, tmp_path):
    receipts = tmp_path / 'receipts'
    receipts.mkdir()
    store = MapStore(tmp_path / 'map.yaml')
    remote = FakeDocs()
    bind_empty(store, repo.name, 'synthetic-notebook', remote.raw)
    job = batch.Job(repo, git(repo, 'rev-parse', 'HEAD'))
    return job, store, receipts, remote


def factory_for(remote):
    @contextmanager
    def factory(job, document_id):
        assert document_id == remote.raw['documentId']
        yield remote
    return factory


def run(managed, mode='publish', **kwargs):
    job, store, receipts, remote = managed
    kwargs.setdefault('transport_factory', factory_for(remote))
    return batch.execute(mode, [job], store, receipts, **kwargs)


def test_complete_changed_no_change_and_separate_status(managed):
    job, store, receipts, remote = managed
    first = run(managed)
    assert first['status'] == 'success' and first['exit_code'] == 0
    assert first['items'][0]['action'] == 'replace_text'
    assert first['items'][0]['verification'] == 'remote'
    assert remote.writes == 1
    second = run(managed)
    assert second['items'][0]['action'] == 'unchanged' and remote.writes == 1
    assert first['receipt_path'] != second['receipt_path']
    status = run(managed, 'status')
    assert status['verification'] == 'local-state'
    assert status['items'][0]['freshness'] == {
        'docs_recorded_verified': True, 'notebook_attested': False,
        'artifact_attestation_count': 0,
    }
    for result in (first, second, status):
        path = Path(result['receipt_path'])
        assert path.is_file() and path.stat().st_mode & 0o777 == 0o600
        receipt = json.loads(path.read_text())
        assert receipt['run_id'] == result['run_id']
        assert str(job.repo) not in path.read_text()


def test_default_offline_plan_does_not_create_map_or_open_factory(repo, tmp_path):
    receipts = tmp_path / 'receipts'
    receipts.mkdir()
    store = MapStore(tmp_path / 'missing-parent' / 'map.yaml')
    job = batch.Job(repo, git(repo, 'rev-parse', 'HEAD'))
    def forbidden(*args):
        pytest.fail('No provider should be opened during an offline plan')
    result = batch.execute('plan', [job], store, receipts, transport_factory=forbidden)
    assert result['status'] == 'success'
    assert result['items'][0]['action'] == 'unbound'
    assert result['verification'] == 'offline'
    assert not store.path.parent.exists()


def test_lost_response_receipt_retains_pending_and_reconcile_never_replays(managed):
    job, store, receipts, remote = managed
    remote.fail_after_write = True
    failed = run(managed)
    assert failed['status'] == 'failed' and failed['exit_code'] == 1
    assert store.read().data['notebooks'][job.repo.name][KEY]['pending'] is not None
    result = run(managed, 'reconcile')
    assert result['status'] == 'success'
    assert result['items'][0]['action'] == 'verified_target'
    assert remote.writes == 1
    assert store.read().data['notebooks'][job.repo.name][KEY]['pending'] is None
    receipt = Path(failed['receipt_path']).read_text()
    assert not any(secret in receipt for secret in ('secret-token', 'source-body', '/private/source/path'))


@pytest.mark.parametrize('revision', ['HEAD', 'main', 'abc123', '', '--all', 'A' * 40])
def test_moving_or_invalid_revisions_refused_in_terminal_receipt(managed, revision):
    job, store, receipts, remote = managed
    result = batch.execute('publish', [batch.Job(job.repo, revision)], store, receipts,
                           transport_factory=factory_for(remote))
    assert result['status'] == 'failed'
    assert result['items'][0]['error_code'] == 'immutable_commit_required'
    assert remote.reads == remote.writes == 0


def test_tag_object_hash_is_not_a_commit(managed):
    job, store, receipts, remote = managed
    git(job.repo, 'tag', '-a', 'synthetic', '-m', 'fixture')
    tag = git(job.repo, 'rev-parse', 'refs/tags/synthetic')
    assert tag != job.revision
    result = batch.execute('publish', [batch.Job(job.repo, tag)], store, receipts,
                           transport_factory=factory_for(remote))
    assert result['items'][0]['error_code'] == 'source_preflight_failed'
    assert remote.reads == remote.writes == 0


def test_all_sources_preflight_before_any_cloud_operation(managed, tmp_path):
    job, store, receipts, remote = managed
    other = tmp_path / 'C098_second'
    subprocess.run(['git', 'clone', '-q', str(job.repo), str(other)], check=True)
    git(other, 'config', 'user.name', 'Synthetic')
    git(other, 'config', 'user.email', 'synthetic@example.invalid')
    (other / 'README.md').unlink()
    bad = batch.Job(other, commit(other))
    result = batch.execute('publish', [job, bad], store, receipts,
                           transport_factory=factory_for(remote))
    assert result['status'] == 'failed'
    assert result['items'][0]['status'] == 'not_attempted'
    assert result['items'][1]['error_code'] == 'source_preflight_failed'
    assert remote.reads == remote.writes == 0


def test_duplicate_repository_names_refused(managed):
    job, store, receipts, remote = managed
    result = batch.execute('publish', [job, job], store, receipts,
                           transport_factory=factory_for(remote))
    assert result['items'][1]['error_code'] == 'duplicate_repository'
    assert remote.reads == remote.writes == 0


def test_no_transport_provider_is_a_receipted_failure(managed):
    job, store, receipts, remote = managed
    before = store.path.read_bytes()
    result = batch.execute('publish', [job], store, receipts)
    assert result['status'] == 'failed'
    assert result['error_code'] == 'transport_unconfigured'
    assert result['verification'] == 'offline' and result['remote_verified_count'] == 0
    assert store.path.read_bytes() == before


@pytest.mark.parametrize('where', ['factory', 'enter', 'exit', 'suppressed'])
def test_factory_failure_and_suppressed_exception_cannot_report_success(managed, where):
    job, store, receipts, remote = managed
    message = 'secret-token /private/source/path source-body'
    class FactoryContext:
        def __enter__(self):
            if where == 'enter':
                raise RuntimeError(message)
            if where == 'suppressed':
                remote.fail_before_write = True
            return remote
        def __exit__(self, *args):
            if where == 'exit':
                raise RuntimeError(message)
            return where == 'suppressed'
    def factory(*args):
        if where == 'factory':
            raise RuntimeError(message)
        return FactoryContext()
    result = run(managed, transport_factory=factory)
    assert result['status'] == 'failed'
    assert result['items'][0]['status'] == 'failed'
    assert message not in Path(result['receipt_path']).read_text()
    if where in {'factory', 'enter'}:
        assert remote.reads == remote.writes == 0


def test_invalid_map_is_receipted_before_factory_initialization(managed):
    job, store, receipts, remote = managed
    store.path.write_text('notebooks: [secret-token]\n')
    result = run(managed)
    assert result['error_code'] == 'map_unavailable'
    assert remote.reads == remote.writes == 0
    assert 'secret-token' not in Path(result['receipt_path']).read_text()


def test_map_inside_source_repository_refused_without_read(managed):
    job, store, receipts, remote = managed
    local = MapStore(job.repo / 'map.yaml')
    local.path.write_text('secret-token')
    result = batch.execute('publish', [job], local, receipts,
                           transport_factory=factory_for(remote))
    assert result['error_code'] == 'invalid_map_location'
    assert local.path.read_text() == 'secret-token'
    assert remote.reads == remote.writes == 0


def test_local_unchanged_is_distinct_from_supplied_snapshot_verification(managed):
    job, store, receipts, remote = managed
    run(managed)
    reads, writes = remote.reads, remote.writes
    plan = run(managed, 'plan')
    assert plan['items'][0]['action'] == 'locally_unchanged'
    assert plan['items'][0]['verification'] == 'offline'
    assert 'snapshot_checked' not in plan['items'][0]
    valid = run(managed, 'plan', snapshots={job.repo.name: deepcopy(remote.raw)})
    assert valid['items'][0]['snapshot_checked'] is True
    assert valid['items'][0]['action'] == 'unchanged'
    assert valid['verification'] == 'offline'
    stale = run(managed, 'plan', snapshots={job.repo.name: document('Manual edit\n')})
    assert stale['status'] == 'failed'
    assert stale['items'][0]['error_code'] == 'snapshot_invalid_or_conflicting'
    assert (remote.reads, remote.writes) == (reads, writes)


def test_pending_local_plan_and_publish_stop_before_client(managed):
    job, store, receipts, remote = managed
    remote.fail_before_write = True
    run(managed)
    reads, writes = remote.reads, remote.writes
    plan = run(managed, 'plan')
    assert plan['items'][0]['action'] == 'pending'
    refused = run(managed)
    assert refused['items'][0]['error_code'] == 'pending_operation'
    assert (remote.reads, remote.writes) == (reads, writes)


def test_explicit_reconcile_unchanged_base_is_not_current_source(managed):
    job, store, receipts, remote = managed
    remote.fail_before_write = True
    run(managed)
    writes = remote.writes
    result = run(managed, 'reconcile')
    assert result['status'] == 'success' and result['items'][0]['action'] == 'unchanged_base'
    assert result['all_docs_recorded_verified'] is False
    assert remote.writes == writes


def test_reconcile_refuses_a_different_bundle_before_client(managed):
    job, store, receipts, remote = managed
    remote.fail_before_write = True
    run(managed)
    (job.repo / 'README.md').write_text('Changed fixture\n')
    changed = batch.Job(job.repo, commit(job.repo))
    calls = (remote.reads, remote.writes)
    result = batch.execute('reconcile', [changed], store, receipts,
                           transport_factory=factory_for(remote))
    assert result['items'][0]['error_code'] == 'original_bundle_required'
    assert (remote.reads, remote.writes) == calls


def test_mixed_batch_preserves_first_success_and_stops_after_second_failure(managed, tmp_path):
    job, store, receipts, first = managed
    jobs, remotes = [job], {job.repo.name: first}
    for index in (2, 3):
        other = tmp_path / f'C09{index}_fictional'
        subprocess.run(['git', 'clone', '-q', str(job.repo), str(other)], check=True)
        jobs.append(batch.Job(other, job.revision))
        remote = remotes[other.name] = FakeDocs('synthetic-doc-' + str(index))
        bind_empty(store, other.name, 'notebook-' + str(index), remote.raw)
    remotes[jobs[1].repo.name].fail_after_write = True
    opened = []
    @contextmanager
    def factory(selected, document_id):
        opened.append(selected.repo.name)
        yield remotes[selected.repo.name]
    result = batch.execute('publish', jobs, store, receipts, transport_factory=factory)
    assert [item['status'] for item in result['items']] == ['success', 'failed', 'not_attempted']
    assert result['status'] == 'failed' and result['remote_verified_count'] == 1
    assert result['all_docs_recorded_verified'] is False
    assert opened == [j.repo.name for j in jobs[:2]]
    assert first.writes == 1 and remotes[jobs[2].repo.name].writes == 0
    assert result['items'][0]['freshness']['docs_recorded_verified'] is True
    assert store.read().data['notebooks'][jobs[1].repo.name][KEY]['pending'] is not None


def test_changed_binding_after_factory_entry_cannot_redirect_operation(managed):
    job, store, receipts, remote = managed
    @contextmanager
    def factory(*args):
        import yaml
        data = store.read().data
        data['notebooks'][job.repo.name][KEY]['document_id'] = 'different-doc'
        store.path.write_text(yaml.safe_dump(data))
        yield remote
    result = run(managed, transport_factory=factory)
    assert result['status'] == 'failed'
    assert remote.reads == remote.writes == 0


def test_keyboard_interrupt_is_recorded_and_pending_is_retained(managed):
    job, store, receipts, remote = managed
    def interrupted(*args):
        raise KeyboardInterrupt()
    remote.write = interrupted
    result = run(managed)
    assert result['status'] == 'failed' and result['exit_code'] == 130
    assert result['items'][0]['error_code'] == 'interrupted'
    assert store.read().data['notebooks'][job.repo.name][KEY]['pending'] is not None


@pytest.mark.parametrize('location', ['missing', 'source', 'symlink'])
def test_unsafe_receipt_directory_fails_before_cloud_without_creating_it(managed, tmp_path, location):
    job, store, receipts, remote = managed
    if location == 'missing':
        destination = tmp_path / 'missing' / 'child'
    elif location == 'source':
        destination = job.repo
    else:
        destination = tmp_path / 'receipt-link'
        destination.symlink_to(receipts, target_is_directory=True)
    with pytest.raises(batch.ReceiptError, match='^publication_receipt_unavailable$'):
        batch.execute('publish', [job], store, destination, transport_factory=factory_for(remote))
    assert remote.reads == remote.writes == 0
    if location == 'missing':
        assert not destination.parent.exists()


def test_receipt_preflight_flush_failure_stops_cloud_work(managed, monkeypatch):
    job, store, receipts, remote = managed
    def fail(*args):
        raise OSError('secret-token /private/path')
    monkeypatch.setattr(batch.os, 'fsync', fail)
    with pytest.raises(batch.ReceiptError) as error:
        run(managed)
    assert str(error.value) == 'publication_receipt_unavailable'
    assert remote.reads == remote.writes == 0
    assert list(receipts.iterdir()) == []


def test_receipt_final_publication_failure_does_not_report_remote_success(managed, monkeypatch):
    job, store, receipts, remote = managed
    def fail(*args, **kwargs):
        raise OSError('secret-token /private/path')
    monkeypatch.setattr(batch.os, 'link', fail)
    with pytest.raises(batch.ReceiptError) as error:
        run(managed)
    assert str(error.value) == 'publication_receipt_persistence_failed'
    assert remote.writes == 1
    assert store.read().data['notebooks'][job.repo.name][KEY]['pending'] is None
    assert list(receipts.iterdir()) == []


def test_receipt_final_directory_flush_failure_is_error_even_if_json_visible(managed, monkeypatch):
    job, store, receipts, remote = managed
    original = os.fsync
    inode, count = receipts.stat().st_ino, 0
    def fail_final_directory(fd):
        nonlocal count
        if os.fstat(fd).st_ino == inode:
            count += 1
            if count == 2:
                raise OSError('Synthetic final receipt directory flush failure')
        original(fd)
    monkeypatch.setattr(batch.os, 'fsync', fail_final_directory)
    with pytest.raises(batch.ReceiptError, match='publication_receipt_persistence_failed'):
        run(managed)
    assert remote.writes == 1
    assert len(list(receipts.glob('publication-*.json'))) == 1
    assert not list(receipts.glob('*.tmp'))


def test_receipt_collision_never_deletes_another_runs_temporary(managed, monkeypatch):
    job, store, receipts, remote = managed
    from types import SimpleNamespace
    run_id = 'a' * 32
    existing = receipts / ('.publication-' + run_id + '.tmp')
    existing.write_text('another run')
    monkeypatch.setattr(batch.uuid, 'uuid4', lambda: SimpleNamespace(hex=run_id))
    with pytest.raises(batch.ReceiptError):
        run(managed)
    assert existing.read_text() == 'another run'
    assert remote.reads == remote.writes == 0


def test_invalid_requests_are_redacted_terminal_receipts(managed):
    job, store, receipts, remote = managed
    for mode, jobs in [('secret-token', [job]), ('publish', []), ('publish', [object()])]:
        result = batch.execute(mode, jobs, store, receipts)
        assert result['status'] == 'failed'
        assert 'secret-token' not in Path(result['receipt_path']).read_text()


def test_no_implicit_credentials_network_or_legacy_state_import(managed, monkeypatch):
    import socket
    import sys
    def forbidden(*args, **kwargs):
        pytest.fail('Unexpected network')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setenv('GOOGLE_API_KEY', 'secret-token')
    monkeypatch.setenv('GOOGLE_APPLICATION_CREDENTIALS', '/private/forbidden')
    before_modules = set(sys.modules)
    plan = run(managed, 'plan')
    published = run(managed)
    assert plan['status'] == published['status'] == 'success'
    added = set(sys.modules) - before_modules
    assert 'notebooklm_mcp.auth' not in added
    assert 'notebooklm_mcp.sync_cli' not in added
    for result in (plan, published):
        assert 'secret-token' not in Path(result['receipt_path']).read_text()
