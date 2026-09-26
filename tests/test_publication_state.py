"""Offline lifecycle tests: explicit temporary maps and synthetic Docs only."""
from copy import deepcopy
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

import yaml

from notebooklm_mcp.doc_refresh import publication_state as state
from notebooklm_mcp.doc_refresh.publication_state import (
    KEY, MapStore, StateConflict, StateError, bind_empty, digest, freshness,
    prepare, publish, reconcile, record_observation,
)
from notebooklm_mcp.doc_refresh.drive_publication import Bundle, parse_document
from tests.test_drive_publication import document, apply_requests
from tests.test_source_bundle import repo as source_repo
from notebooklm_mcp.doc_refresh.source_bundle import build_bundle


def bundle(text='Version A: Amber and Birch\n'):
    return Bundle(text, digest(text), 1)


class FakeDocs:
    def __init__(self):
        self.raw = document()
        self.reads = self.writes = 0
        self.fail_before_write = False
        self.fail_after_write = False
        self.stale_readback = False
        self.invalid_readback = False

    def read(self, document_id):
        assert document_id == 'synthetic-doc'
        self.reads += 1
        if self.writes and self.invalid_readback:
            return {'documentId': document_id}
        if self.writes and self.stale_readback:
            return document()
        return deepcopy(self.raw)

    def write(self, document_id, body):
        assert document_id == 'synthetic-doc'
        self.writes += 1
        if self.fail_before_write:
            raise OSError('Synthetic transport failure before application')
        # Existing test interpreter implements the actual UTF-16 insert/delete
        # requests and checks requiredRevisionId, not just the expected output.
        from types import SimpleNamespace
        self.raw = apply_requests(SimpleNamespace(body=body), self.raw)
        self.raw['revisionId'] = 'r' + str(self.writes + 1)
        if self.fail_after_write:
            raise OSError('Synthetic lost response after remote success')


@pytest.fixture
def managed(tmp_path):
    store = MapStore(tmp_path / 'notebook_map.yaml')
    remote = FakeDocs()
    bind_empty(store, 'repo', 'notebook', remote.raw)
    return store, remote


def entry(store):
    return store.read().data['notebooks']['repo'][KEY]


def test_read_absent_map_never_creates_it(tmp_path):
    path = tmp_path / 'absent' / 'notebook_map.yaml'
    assert MapStore(path).read().data == {'notebooks': {}}
    assert not path.parent.exists()


@pytest.mark.parametrize('text', ['', '[]', 'notebooks: []', 'notebooks: {}\nnotebooks: {}'])
def test_malformed_existing_map_fails_without_changing_bytes(tmp_path, text):
    path = tmp_path / 'map.yaml'
    path.write_text(text)
    with pytest.raises(StateError):
        MapStore(path).read()
    assert path.read_text() == text


def test_binding_preserves_legacy_data_and_refuses_rebinding(tmp_path):
    path = tmp_path / 'map.yaml'
    legacy = {'notebooks': {'legacy': {'notebook_id': 'old', 'docs': {'a': {'hash': 'short'}}}},
              'config': {'unknown': 12}, 'sync_log': ['old'], 'custom': ['preserve']}
    path.write_text(yaml.safe_dump(legacy))
    store = MapStore(path)
    bind_empty(store, 'repo', 'notebook', document())
    loaded = store.read().data
    assert loaded['notebooks']['legacy'] == legacy['notebooks']['legacy']
    assert loaded['config'] == legacy['config'] and loaded['custom'] == legacy['custom']
    saved = path.read_bytes()
    for repo, doc in [('repo', document()), ('another', document()), ('new', document('Not empty\n'))]:
        with pytest.raises(StateError):
            bind_empty(store, repo, 'notebook', doc)
        assert path.read_bytes() == saved


def test_prepare_is_readonly_and_missing_binding_creates_nothing(tmp_path, managed):
    store, remote = managed
    before = store.path.read_bytes()
    plan = prepare(store, 'repo', bundle(), remote.raw)
    assert plan.body['writeControl'] == {'requiredRevisionId': 'r1'}
    assert store.path.read_bytes() == before
    missing = MapStore(tmp_path / 'missing')
    with pytest.raises(StateError, match='binding'):
        prepare(missing, 'repo', bundle(), remote.raw)
    assert not missing.path.exists()


def test_complete_lifecycle_separates_each_layer_and_keeps_stale_evidence(managed):
    store, remote = managed
    a = bundle()
    assert publish(store, 'repo', a, remote) == 'replace_text'
    assert remote.writes == 1
    assert freshness(store, {'repo': a.sha256})['repos']['repo'] == {
        'docs_verified': True, 'notebook_attested': False, 'artifact_attestations': []}
    record_observation(store, 'repo', a.sha256, 'source', 'synthetic-citation-A')
    record_observation(store, 'repo', a.sha256, 'source', 'synthetic-image-A', artifact_id='image-A')
    assert freshness(store, {'repo': a.sha256})['repos']['repo']['artifact_attestations'] == ['image-A']
    assert publish(store, 'repo', a, remote) == 'unchanged'
    assert remote.writes == 1
    b = bundle('Version B: Amber, Birch, Cedar; Collect Normalize Verify Summarize\n')
    publish(store, 'repo', b, remote)
    assert entry(store)['notebook']['sha256'] == a.sha256
    assert freshness(store, {'repo': b.sha256})['repos']['repo'] == {
        'docs_verified': True, 'notebook_attested': False, 'artifact_attestations': []}
    mixed = freshness(store, {'repo': b.sha256, 'unpublished': a.sha256})
    assert mixed['all_docs_verified'] is False
    assert mixed['repos']['repo']['docs_verified'] is True


@pytest.mark.parametrize('failure', ['fail_before_write', 'fail_after_write', 'stale_readback', 'invalid_readback'])
def test_failed_publication_keeps_pending_and_never_promotes(managed, failure):
    store, remote = managed
    initial = deepcopy(entry(store)['verified'])
    setattr(remote, failure, True)
    with pytest.raises((OSError, ValueError)):
        publish(store, 'repo', bundle(), remote)
    assert entry(store)['verified'] == initial
    assert entry(store)['pending']['target_sha256'] == bundle().sha256
    assert not freshness(store, {'repo': bundle().sha256})['all_docs_verified']
    calls = (remote.reads, remote.writes)
    with pytest.raises(StateError, match='reconciliation'):
        publish(store, 'repo', bundle(), remote)
    assert (remote.reads, remote.writes) == calls
    assert not list(store.path.parent.glob('*.tmp'))


@pytest.mark.parametrize('remote_applied', [True, False])
def test_explicit_reconcile_does_not_repeat_uncertain_write(managed, remote_applied):
    store, remote = managed
    remote.fail_after_write = remote_applied
    remote.fail_before_write = not remote_applied
    with pytest.raises(OSError):
        publish(store, 'repo', bundle(), remote)
    writes = remote.writes
    result = reconcile(store, 'repo', bundle(), remote)
    assert result == ('verified_target' if remote_applied else 'unchanged_base')
    assert entry(store)['pending'] is None
    assert remote.writes == writes
    assert freshness(store, {'repo': bundle().sha256})['all_docs_verified'] == remote_applied


def test_reconcile_wrong_bundle_manual_edit_or_identity_preserves_pending(managed):
    store, remote = managed
    remote.fail_before_write = True
    with pytest.raises(OSError):
        publish(store, 'repo', bundle(), remote)
    before = store.path.read_bytes()
    with pytest.raises(StateError):
        reconcile(store, 'repo', bundle('Other\n'), remote)
    assert remote.reads == 1
    for raw in [document('Manual edit\n'), document(revision='r-other'),
                document(bundle().text, document_id='wrong'), document(bundle().text, tab_id='wrong')]:
        remote.raw = raw
        with pytest.raises(StateError):
            reconcile(store, 'repo', bundle(), remote)
        assert store.path.read_bytes() == before


def test_remote_success_local_save_failure_recovers_without_second_write(managed, monkeypatch):
    store, remote = managed
    original = os.replace
    count = 0

    def fail_second(*args):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('Synthetic interrupted local commit')
        return original(*args)

    monkeypatch.setattr(state.os, 'replace', fail_second)
    with pytest.raises(OSError):
        publish(store, 'repo', bundle(), remote)
    assert parse_document(remote.raw).text == bundle().text
    assert entry(store)['pending'] is not None
    assert entry(store)['verified']['sha256'] == digest('\n')
    assert reconcile(store, 'repo', bundle(), remote) == 'verified_target'
    assert remote.writes == 1


def test_failure_before_pending_commit_never_writes_remote(managed, monkeypatch):
    store, remote = managed
    before = store.path.read_bytes()
    def fail(*args):
        raise OSError('Synthetic disk failure')
    monkeypatch.setattr(state.os, 'replace', fail)
    with pytest.raises(OSError):
        publish(store, 'repo', bundle(), remote)
    assert store.path.read_bytes() == before and remote.writes == 0
    assert not list(store.path.parent.glob('*.tmp'))


def test_observed_concurrent_edit_refuses_overwrite(managed):
    store, remote = managed
    before = store.read()
    changed = deepcopy(before.data)
    changed['other_writer'] = 'keep me'
    with store.transaction() as tx:
        store.path.write_text(yaml.safe_dump(changed))
        with pytest.raises(StateConflict):
            tx.save(before, before.data)
    assert store.read().data == changed


def test_cooperating_writer_cannot_enter_during_transport(managed):
    store, remote = managed
    entered, release = Event(), Event()
    original = remote.write
    def paused(*args):
        entered.set()
        assert release.wait(5)
        original(*args)
    remote.write = paused
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(publish, store, 'repo', bundle(), remote)
        assert entered.wait(5)
        try:
            with pytest.raises(StateConflict, match='busy'):
                publish(MapStore(store.path), 'repo', bundle(), FakeDocs())
        finally:
            release.set()
        assert task.result() == 'replace_text'


@pytest.mark.parametrize('mutation', [
    lambda d: d['notebooks']['repo'][KEY].update(version=2),
    lambda d: d['notebooks']['repo'][KEY].update(version=True),
    lambda d: d['notebooks']['repo'][KEY].update(unrecognized=True),
    lambda d: d['notebooks']['repo'][KEY]['verified'].update(sha256='short'),
    lambda d: d['notebooks']['repo'].pop('notebook_id'),
])
def test_invalid_state_refuses_before_transport(managed, mutation):
    store, remote = managed
    data = store.read().data
    mutation(data)
    store.path.write_text(yaml.safe_dump(data))
    before = store.path.read_bytes()
    with pytest.raises(StateError):
        publish(store, 'repo', bundle(), remote)
    assert (remote.reads, remote.writes) == (0, 0)
    assert store.path.read_bytes() == before


def test_symlink_map_refused_and_target_unchanged(tmp_path):
    target = tmp_path / 'target'
    target.write_text('notebooks: {}\n')
    link = tmp_path / 'link'
    link.symlink_to(target)
    with pytest.raises(StateError):
        MapStore(link).read()
    assert target.read_text() == 'notebooks: {}\n'


def test_source_and_artifact_attestations_cannot_silently_change_identity(managed):
    store, remote = managed
    a = bundle()
    publish(store, 'repo', a, remote)
    with pytest.raises(StateError, match='source verification'):
        record_observation(store, 'repo', a.sha256, 'source', 'image', artifact_id='image')
    record_observation(store, 'repo', a.sha256, 'source', 'citation')
    with pytest.raises(StateError, match='association'):
        record_observation(store, 'repo', a.sha256, 'other-source', 'citation')
    with pytest.raises(StateError, match='current verified'):
        record_observation(store, 'repo', 'a' * 64, 'source', 'old-citation')
    record_observation(store, 'repo', a.sha256, 'source', 'image', artifact_id='image')
    with pytest.raises(StateError, match='immutable'):
        record_observation(store, 'repo', a.sha256, 'source', 'edited', artifact_id='image')


def test_closed_transaction_cannot_mutate(managed):
    store, remote = managed
    with store.transaction() as tx:
        before = store.read()
    with pytest.raises(StateError, match='closed'):
        tx.save(before, before.data)


def test_save_failure_after_replace_is_reported_then_explicitly_reconciled(managed, monkeypatch):
    store, remote = managed
    original = os.fsync
    calls = 0
    def fail_final_directory(fd):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError('Synthetic directory fsync failure after verified replacement')
        original(fd)
    monkeypatch.setattr(state.os, 'fsync', fail_final_directory)
    with pytest.raises(OSError):
        publish(store, 'repo', bundle(), remote)
    assert entry(store)['pending'] is None
    assert reconcile(store, 'repo', bundle(), remote) == 'already_verified'
    assert remote.writes == 1


def test_failed_file_fsync_preserves_previous_map(managed, monkeypatch):
    store, remote = managed
    before = store.path.read_bytes()
    def fail(fd):
        raise OSError('Synthetic flush failure')
    monkeypatch.setattr(state.os, 'fsync', fail)
    with pytest.raises(OSError):
        publish(store, 'repo', bundle(), remote)
    assert store.path.read_bytes() == before
    assert remote.writes == 0


@pytest.mark.parametrize('text', [
    'notebooks: &a {}\nother: *a\n', 'notebooks: {}\nconfig: []\n',
    'notebooks: {}\nsync_log: {}\n', 'notebooks: {}\nx: .nan\n',
    'notebooks: {}\nx: 2026-09-26\n', 'notebooks: {repo: null}\n',
    'notebooks: {}\nx: !!python/object:thing {}\n',
])
def test_invalid_yaml_never_calls_transport(tmp_path, text):
    path = tmp_path / 'map.yaml'
    path.write_text(text)
    remote = FakeDocs()
    with pytest.raises(StateError):
        publish(MapStore(path), 'repo', bundle(), remote)
    assert remote.reads == remote.writes == 0
    assert path.read_text() == text


def test_size_limit_and_nonregular_map_refused(tmp_path, monkeypatch):
    path = tmp_path / 'map.yaml'
    path.mkdir()
    with pytest.raises(StateError):
        MapStore(path).read()
    path.rmdir()
    path.write_text('notebooks: {}\n')
    monkeypatch.setattr(state, 'MAX_BYTES', 4)
    with pytest.raises(StateError, match='size limit'):
        MapStore(path).read()


def test_readonly_layer_and_fake_transport_never_open_network(managed, monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('Unexpected network')
    monkeypatch.setattr(socket, 'socket', forbidden)
    store, remote = managed
    prepare(store, 'repo', bundle(), remote.raw)
    publish(store, 'repo', bundle(), remote)
    assert freshness(store, {'repo': bundle().sha256})['all_docs_verified']


def test_two_repo_partial_failure_keeps_success_and_pending_separate(tmp_path):
    store = MapStore(tmp_path / 'map.yaml')
    bind_empty(store, 'repo', 'notebook', document())
    bind_empty(store, 'repo2', 'notebook2', document(document_id='second-doc'))
    publish(store, 'repo', bundle(), FakeDocs())
    class BrokenSecond:
        def read(self, document_id):
            return document(document_id='second-doc')
        def write(self, document_id, body):
            raise OSError('Synthetic second repo failure')
    with pytest.raises(OSError):
        publish(store, 'repo2', bundle(), BrokenSecond())
    result = freshness(store, {'repo': bundle().sha256, 'repo2': bundle().sha256})
    assert result['all_docs_verified'] is False
    assert result['repos']['repo']['docs_verified'] is True
    assert result['repos']['repo2']['docs_verified'] is False


def test_accepted_git_bundle_connects_to_state_machine(source_repo, managed):
    store, remote = managed
    generated = build_bundle(source_repo, 'HEAD')
    assert generated.receipt['bundle_sha256'] == generated.bundle.sha256
    publish(store, 'repo', generated.bundle, remote)
    assert parse_document(remote.raw).text == generated.bundle.text
    assert freshness(store, {'repo': generated.receipt['bundle_sha256']})['all_docs_verified']
