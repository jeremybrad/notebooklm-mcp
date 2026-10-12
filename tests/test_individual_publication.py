"""Fictional Git sources and remote state; no live credentials or Google calls."""
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from notebooklm_mcp.doc_refresh.manifest import load_manifest
from notebooklm_mcp.doc_refresh.source_bundle import build_bundle
from notebooklm_mcp.doc_refresh.publication_state import MapStore, StateError
from notebooklm_mcp.doc_refresh.individual_publication import (
    document_key, bind_empty, publish, reconcile, Snapshot,
)
from notebooklm_mcp.doc_refresh import individual_publication as originals


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()


@pytest.fixture
def selected(tmp_path):
    root = tmp_path / 'C099_fixture'
    root.mkdir()
    git(root, 'init', '-q'); git(root, 'config', 'user.name', 'Fixture')
    git(root, 'config', 'user.email', 'fixture@example.invalid')
    for path in ['a/reference.md', 'b/reference.md']:
        p = root / path; p.parent.mkdir(); p.write_bytes(b'# Original\r\n\r\n| A | B |\r\n| - | - |\r\n')
    git(root, 'add', '.'); git(root, 'commit', '-qm', 'fixture')
    m = load_manifest()
    for tier in m['tiers'].values(): tier['documents'] = []
    m['repo_overrides'] = {root.name: {'extra_docs': [
        {'path': p, 'purpose': 'fixture', 'must_exist': True, 'stub_allowed': False}
        for p in ['a/reference.md', 'b/reference.md']]}}
    manifest = tmp_path / 'manifest.yaml'; manifest.write_text(yaml.safe_dump(m))
    return root, manifest


class Remote:
    def __init__(self): self.snapshot = Snapshot('file_1', '"rev1"', b''); self.writes = 0; self.lose_response = False
    def read(self, file_id): assert file_id == self.snapshot.file_id; return self.snapshot
    def write(self, file_id, content, etag):
        assert (file_id, etag) == (self.snapshot.file_id, self.snapshot.etag)
        self.snapshot = Snapshot(file_id, '"rev2"', content); self.writes += 1
        if self.lose_response: raise TimeoutError('fictional lost reply')


def test_original_bytes_collision_free_and_dirty_ignored(selected):
    root, manifest = selected
    artifact = build_bundle(root, 'HEAD', manifest_path=manifest)
    docs = artifact.documents
    assert len(docs) == 2
    assert docs[0].text.encode() == (root / 'a/reference.md').read_bytes()
    assert document_key(docs[0]) != document_key(docs[1])
    (root / 'a/reference.md').write_text('DIRTY')
    assert build_bundle(root, artifact.receipt['commit'], manifest_path=manifest).documents == docs


def test_same_file_changed_and_unchanged_repeat(selected, tmp_path):
    root, manifest = selected; artifact = build_bundle(root, 'HEAD', manifest_path=manifest)
    store = MapStore(tmp_path / 'map.yaml'); remote = Remote(); source = artifact.documents[0]
    bind_empty(store, source, 'notebook_1', remote.snapshot)
    assert publish(store, source, artifact.receipt, remote) == 'replace_bytes'
    before = store.path.read_bytes()
    assert publish(store, source, artifact.receipt, remote) == 'unchanged'
    assert store.path.read_bytes() == before and remote.writes == 1
    source = replace(source, text='# Correction\n', source_revision='b'*40)
    receipt = dict(artifact.receipt, sources=[dict(path=source.path, blob_oid=source.source_revision, sha256=hashlib.sha256(source.text.encode()).hexdigest(), byte_count=len(source.text.encode()))])
    assert publish(store, source, receipt, remote) == 'replace_bytes'
    assert remote.snapshot.file_id == 'file_1' and remote.writes == 2


def test_external_edit_refuses_and_lost_reply_reconciles_without_replay(selected, tmp_path):
    root, manifest = selected; artifact = build_bundle(root, 'HEAD', manifest_path=manifest)
    source = artifact.documents[0]; store = MapStore(tmp_path / 'map.yaml'); remote = Remote()
    bind_empty(store, source, 'notebook_1', remote.snapshot)
    remote.snapshot = replace(remote.snapshot, content=b'manual')
    with pytest.raises(StateError): publish(store, source, artifact.receipt, remote)
    assert remote.writes == 0
    remote.snapshot = replace(remote.snapshot, content=b''); remote.lose_response = True
    with pytest.raises(TimeoutError): publish(store, source, artifact.receipt, remote)
    with pytest.raises(StateError): publish(store, source, artifact.receipt, remote)
    with pytest.raises(StateError): reconcile(store, replace(source, text='wrong'), artifact.receipt, remote)
    assert reconcile(store, source, artifact.receipt, remote) == 'verified_target'
    assert remote.writes == 1


def test_duplicate_destination_and_nonempty_adoption_refuse(selected, tmp_path):
    root, manifest = selected; artifact = build_bundle(root, 'HEAD', manifest_path=manifest)
    store = MapStore(tmp_path / 'map.yaml'); remote = Remote()
    with pytest.raises(StateError): bind_empty(store, artifact.documents[0], 'notebook_1', replace(remote.snapshot, content=b'old'))
    bind_empty(store, artifact.documents[0], 'notebook_1', remote.snapshot)
    with pytest.raises(StateError): bind_empty(store, artifact.documents[1], 'notebook_1', remote.snapshot)


def test_batch_preflights_all_bindings_before_credentials(selected, tmp_path):
    from notebooklm_mcp.doc_refresh.individual_batch import execute
    from notebooklm_mcp.doc_refresh.publication_batch import Job
    root, manifest=selected; artifact=build_bundle(root,'HEAD',manifest_path=manifest)
    store=MapStore(tmp_path/'map.yaml'); remote=Remote()
    bind_empty(store,artifact.documents[0],'notebook_1',remote.snapshot)
    receipts=tmp_path/'receipts'; receipts.mkdir()
    calls=[]
    def factory(*args): calls.append(args); raise AssertionError('must not enter')
    result=execute('publish',[Job(root,artifact.receipt['commit'])],store,receipts,manifest_path=manifest,transport_factory=factory)
    assert result['exit_code']==1 and calls==[] and remote.writes==0
    assert 'file_1' not in open(result['receipt_path']).read()


def test_batch_cli_offline_plan_requires_optin_and_no_cloud(selected, tmp_path, capsys):
    from notebooklm_mcp.doc_refresh.publication_cli import main
    root,manifest=selected; receipts=tmp_path/'receipts'; receipts.mkdir()
    args=['plan','--individual','--repo',str(root),git(root,'rev-parse','HEAD'),
          '--manifest',str(manifest),'--map',str(tmp_path/'map.yaml'),'--receipts',str(receipts)]
    assert main(args)==0
    import json
    result=json.loads(capsys.readouterr().out)
    assert len(result['items'])==2 and all(i['action']=='unbound' for i in result['items'])
    assert not (tmp_path/'map.yaml').exists()
    with pytest.raises(SystemExit): main([a if a!='plan' else 'publish' for a in args])


@pytest.mark.parametrize('alias', [False, True])
def test_distinct_checkouts_with_same_basename_refuse_before_any_write(selected, tmp_path, alias):
    from contextlib import contextmanager
    from notebooklm_mcp.doc_refresh.individual_batch import execute
    from notebooklm_mcp.doc_refresh.publication_batch import Job
    root, manifest = selected
    second = tmp_path / 'other' / root.name
    second.parent.mkdir()
    subprocess.run(['git', 'clone', '-q', str(root), str(second)], check=True)
    git(second, 'config', 'user.name', 'Fixture')
    git(second, 'config', 'user.email', 'fixture@example.invalid')
    (second / 'a/reference.md').write_text('# Other checkout original\n')
    git(second, 'add', '.'); git(second, 'commit', '-qm', 'different original')
    artifact = build_bundle(root, 'HEAD', manifest_path=manifest)
    store = MapStore(tmp_path / 'map.yaml')
    remotes = {}
    for i, source in enumerate(artifact.documents):
        remote = Remote()
        remote.snapshot = replace(remote.snapshot, file_id='file_' + str(i))
        # Remote methods below deliberately enforce each individual identity.
        remotes[remote.snapshot.file_id] = remote
        bind_empty(store, source, 'notebook_1', remote.snapshot)
    calls = []
    @contextmanager
    def factory(job, file_id):
        calls.append(file_id)
        remote = remotes[file_id]
        class Transport:
            def read(self, identity):
                assert identity == file_id
                return remote.snapshot
            def write(self, identity, raw, etag):
                assert identity == file_id and etag == remote.snapshot.etag
                remote.snapshot = Snapshot(file_id, '"updated"', raw)
                remote.writes += 1
        yield Transport()
    before = store.path.read_bytes()
    with pytest.raises(StateError):
        execute('publish', [Job(root, git(root, 'rev-parse', 'HEAD')),
                Job(second / 'a' / '..' if alias else second, git(second, 'rev-parse', 'HEAD'))], store, tmp_path,
                manifest_path=manifest, transport_factory=factory)
    assert calls == [] and all(r.writes == 0 for r in remotes.values())
    assert store.path.read_bytes() == before


@pytest.mark.parametrize('evidence', [' ', 'x' * 1025, 'proof\n'])
def test_invalid_conditional_evidence_refuses_before_keychain(selected, tmp_path, monkeypatch, evidence):
    from notebooklm_mcp.doc_refresh import publication_credentials as provider
    from notebooklm_mcp.doc_refresh.individual_batch import DocumentJob
    from tests.test_publication_credentials import configuration
    root, manifest = selected
    source = build_bundle(root, 'HEAD', manifest_path=manifest).documents[0]
    config = provider.load_config(configuration(tmp_path, repo_name=document_key(source)))
    calls = []
    def keychain(*args):
        calls.append('keychain')
        raise provider.ProviderError('configuration_invalid')
    monkeypatch.setattr(provider, 'KeychainStore', keychain)
    factory = provider.transport_factory(config, individual=True, conditional_write_evidence=evidence)
    with pytest.raises(provider.ProviderError):
        with factory(DocumentJob(root, git(root, 'rev-parse', 'HEAD'), source), 'synthetic-doc'):
            pytest.fail('invalid qualification must not construct transport')
    assert calls == []


@pytest.mark.parametrize('alias', [False, True])
def test_omitted_bound_original_refuses_with_normalized_identity(selected, tmp_path, alias):
    from contextlib import contextmanager
    from notebooklm_mcp.doc_refresh.individual_batch import execute
    from notebooklm_mcp.doc_refresh.publication_batch import Job
    root, manifest = selected
    artifact = build_bundle(root, 'HEAD', manifest_path=manifest)
    store = MapStore(tmp_path / 'map.yaml')
    for i, source in enumerate(artifact.documents):
        bind_empty(store, source, 'notebook_1', Snapshot('file_' + str(i), '"empty"', b''))
    narrowed = yaml.safe_load(manifest.read_text())
    narrowed['repo_overrides'][root.name]['extra_docs'] = narrowed['repo_overrides'][root.name]['extra_docs'][:1]
    manifest.write_text(yaml.safe_dump(narrowed))
    calls = []
    @contextmanager
    def factory(job, file_id):
        calls.append(file_id)
        remote = Remote()
        remote.snapshot = Snapshot(file_id, '"empty"', b'')
        class Transport:
            def read(self, identity): return remote.snapshot
            def write(self, identity, content, etag):
                remote.snapshot = Snapshot(file_id, '"new"', content)
        yield Transport()
    before = store.path.read_bytes()
    result = execute('publish', [Job(root / 'a' / '..' if alias else root, artifact.receipt['commit'])],
                     store, tmp_path, manifest_path=manifest, transport_factory=factory)
    assert result['exit_code'] == 1 and calls == []
    assert store.path.read_bytes() == before


def adoption_inputs(selected, tmp_path):
    root, manifest = selected
    artifact = build_bundle(root, 'HEAD', manifest_path=manifest)
    source = artifact.documents[0]
    remote = Remote()
    remote.snapshot = Snapshot('file_1', '"existing"', source.text.encode('utf-8'))
    store = MapStore(tmp_path / 'map.yaml')
    receipts = tmp_path / 'admission-receipts'
    receipts.mkdir()
    return root, artifact, source, remote, store, receipts


def admit(inputs, **overrides):
    root, artifact, source, remote, store, receipts = inputs
    operation = getattr(originals, 'bind_existing_original', None)
    assert callable(operation), 'Explicit nonempty original admission is missing'
    kwargs = dict(store=store, source=source, receipt=artifact.receipt,
                  notebook_id='notebook_1', file_id='file_1', transport=remote,
                  source_root=root, receipt_dir=receipts)
    kwargs.update(overrides)
    return operation(**kwargs)


def test_admission_preserves_bytes_provenance_and_later_publication(selected, tmp_path):
    inputs = adoption_inputs(selected, tmp_path)
    root, artifact, source, remote, store, receipts = inputs
    sibling = artifact.documents[1]
    bind_empty(store, sibling, 'notebook_1', Snapshot('file_2', '"empty"', b''))
    sibling_before = store.read().data['notebooks'][source.repo]['drive_documents'][sibling.path]
    result = admit(inputs)
    entry = store.read().data['notebooks'][source.repo]['drive_documents'][source.path]
    assert entry['verified'] == dict(sha256=hashlib.sha256(remote.snapshot.content).hexdigest(),
        etag='"existing"', source=dict(commit=artifact.receipt['commit'],
        blob_oid=source.source_revision, manifest_hash_prefix=artifact.receipt['manifest_hash_prefix']))
    assert entry['pending'] is None and entry['notebook'] is None and remote.writes == 0
    assert store.read().data['notebooks'][source.repo]['drive_documents'][sibling.path] == sibling_before
    saved = json.loads(open(result['receipt_path']).read())
    assert saved['status'] == 'success' and saved['map_effect'] == 'verified_base_saved'
    assert saved['sha256'] == entry['verified']['sha256']
    assert source.text not in json.dumps(saved) and 'file_1' not in json.dumps(saved)
    assert publish(store, source, artifact.receipt, remote) == 'unchanged'
    before = store.path.read_bytes()
    assert publish(store, source, artifact.receipt, remote) == 'unchanged'
    assert store.path.read_bytes() == before and remote.writes == 0
    (root / source.path).write_text('# Genuine correction\n')
    git(root, 'add', '.'); git(root, 'commit', '-qm', 'correction')
    changed = build_bundle(root, 'HEAD', manifest_path=selected[1])
    assert publish(store, changed.documents[0], changed.receipt, remote) == 'replace_bytes'
    before = store.path.read_bytes()
    assert publish(store, changed.documents[0], changed.receipt, remote) == 'unchanged'
    assert store.path.read_bytes() == before and remote.writes == 1


@pytest.mark.parametrize('fault', ['bytes', 'file', 'blob', 'receipt_hash', 'commit',
                                 'empty', 'weak_etag', 'wrong_root'])
def test_admission_refuses_invalid_base_without_binding(selected, tmp_path, fault):
    inputs = adoption_inputs(selected, tmp_path)
    root, artifact, source, remote, store, receipts = inputs
    overrides = {}
    if fault == 'bytes': remote.snapshot = replace(remote.snapshot, content=b'manual change')
    if fault == 'file': overrides['file_id'] = 'wrong_file'
    if fault == 'blob':
        source = replace(source, source_revision='b' * 40)
        receipt = dict(artifact.receipt, sources=[dict(artifact.receipt['sources'][0], blob_oid=source.source_revision)])
        overrides.update(source=source, receipt=receipt)
    if fault == 'receipt_hash':
        overrides['receipt'] = dict(artifact.receipt, sources=[dict(artifact.receipt['sources'][0], sha256='0' * 64)])
    if fault == 'commit': overrides['receipt'] = dict(artifact.receipt, commit='HEAD')
    if fault == 'empty': overrides['source'] = replace(source, text='')
    if fault == 'weak_etag': overrides['expected_etag'] = 'W/"old"'
    if fault == 'wrong_root': overrides['source_root'] = tmp_path / 'different_repo'
    result = admit(inputs, **overrides)
    assert result['status'] == 'failed' and not store.path.exists() and remote.writes == 0


@pytest.mark.parametrize('fault', ['existing', 'pending', 'notebook', 'duplicate_original', 'duplicate_docs'])
def test_admission_refuses_existing_and_colliding_state(selected, tmp_path, fault):
    inputs = adoption_inputs(selected, tmp_path)
    root, artifact, source, remote, store, receipts = inputs
    if fault in {'existing', 'pending'}:
        bind_empty(store, source, 'notebook_1', Snapshot('file_1', '"empty"', b''))
        if fault == 'pending':
            remote.snapshot = replace(remote.snapshot, content=b'')
            remote.lose_response = True
            with pytest.raises(TimeoutError): publish(store, source, artifact.receipt, remote)
    elif fault == 'duplicate_docs':
        store.path.write_text(yaml.safe_dump({'notebooks': {'OTHER': {'notebook_id':'other',
            'drive_publication': {'version': 1, 'document_id': 'file_1', 'tab_id': 'tab',
                'verified': {'sha256': hashlib.sha256(b'').hexdigest(), 'revision_id': 'rev'},
                'pending': None, 'notebook': None, 'artifacts': {}}}}}))
    else:
        bind_empty(store, artifact.documents[1], 'wrong_notebook' if fault == 'notebook' else 'notebook_1',
                   Snapshot('file_1' if fault == 'duplicate_original' else 'file_2', '"empty"', b''))
    before = store.path.read_bytes()
    writes = remote.writes
    result = admit(inputs)
    assert result['status'] == 'failed' and store.path.read_bytes() == before and remote.writes == writes


@pytest.mark.parametrize('reason', ['account_mismatch', 'permissions_rejected', 'destination_rejected',
                                  'planner_guard', 'request_timeout'])
def test_admission_transport_read_refusal_leaves_map_absent(selected, tmp_path, reason):
    from notebooklm_mcp.doc_refresh.google_docs_transport import TransportError
    inputs = adoption_inputs(selected, tmp_path)
    remote = inputs[3]
    def refusal(file_id): raise TransportError(reason)
    remote.read = refusal
    assert admit(inputs)['status'] == 'failed'
    assert not inputs[4].path.exists() and remote.writes == 0


def test_admission_concurrent_map_edit_is_not_overwritten(selected, tmp_path):
    inputs = adoption_inputs(selected, tmp_path)
    remote, store = inputs[3:5]
    new = {'notebooks': {'OTHER': {'notebook_id':'other'}}}
    def competing_read(file_id):
        store.path.write_text(yaml.safe_dump(new))
        return remote.snapshot
    remote.read = competing_read
    assert admit(inputs)['status'] == 'failed'
    assert store.read().data == new and remote.writes == 0


def test_admission_requires_coherent_snapshot_and_expected_etag(selected, tmp_path):
    inputs = adoption_inputs(selected, tmp_path)
    assert admit(inputs, expected_etag='"stale"')['status'] == 'failed'
    assert not inputs[4].path.exists() and inputs[3].writes == 0


def test_admission_receipt_reservation_failure_precedes_remote_read(selected, tmp_path):
    from notebooklm_mcp.doc_refresh.publication_batch import ReceiptError
    inputs = adoption_inputs(selected, tmp_path)
    def must_not_read(file_id): pytest.fail('Receipt reservation must precede remote access')
    inputs[3].read = must_not_read
    with pytest.raises(ReceiptError): admit(inputs, receipt_dir=tmp_path / 'absent')
    assert not inputs[4].path.exists()


def test_admission_receipt_failure_does_not_claim_success_or_replay(selected, tmp_path, monkeypatch):
    from notebooklm_mcp.doc_refresh.publication_batch import ReceiptError, _ReceiptSink
    inputs = adoption_inputs(selected, tmp_path)
    def failed_finish(self, result): raise ReceiptError('fictional durability failure')
    monkeypatch.setattr(_ReceiptSink, 'finish', failed_finish)
    with pytest.raises(ReceiptError): admit(inputs)
    assert inputs[4].read().data['notebooks'][inputs[2].repo]['drive_documents'][inputs[2].path]['pending'] is None
    assert inputs[3].writes == 0


def test_admission_transaction_exit_failure_reports_saved_failed_operation(selected, tmp_path, monkeypatch):
    from contextlib import contextmanager
    inputs = adoption_inputs(selected, tmp_path)
    original = MapStore.transaction
    @contextmanager
    def failed_exit(self):
        with original(self) as transaction:
            yield transaction
        raise OSError('fictional transaction teardown failure after save')
    monkeypatch.setattr(MapStore, 'transaction', failed_exit)
    result = admit(inputs)
    assert result['status'] == 'failed'
    assert result['error'] == 'original_admission_failed'
    assert result['map_effect'] == 'verified_base_saved'
    persisted = json.loads(Path(result['receipt_path']).read_text())
    assert persisted['status'] == 'failed' and persisted['map_effect'] == 'verified_base_saved'
    entry = inputs[4].read().data['notebooks'][inputs[2].repo]['drive_documents'][inputs[2].path]
    assert entry['verified']['sha256'] == hashlib.sha256(inputs[3].snapshot.content).hexdigest()
    assert entry['pending'] is None and entry['notebook'] is None
    assert inputs[3].writes == 0


def test_admission_map_save_failure_reports_unknown_outcome(selected, tmp_path, monkeypatch):
    from notebooklm_mcp.doc_refresh.publication_state import _Transaction
    inputs = adoption_inputs(selected, tmp_path)
    original = _Transaction.save
    def uncertain_save(self, old, data):
        original(self, old, data)
        raise OSError('fictional fsync failure after replace')
    monkeypatch.setattr(_Transaction, 'save', uncertain_save)
    result = admit(inputs)
    assert result['status'] == 'failed' and result['map_effect'] == 'save_outcome_unknown'
    assert inputs[4].read().data['notebooks'][inputs[2].repo]['drive_documents'][inputs[2].path]['verified']['sha256'] == hashlib.sha256(inputs[3].snapshot.content).hexdigest()
    assert inputs[3].writes == 0


@pytest.mark.parametrize('mode', ['valid', 'wrong_account', 'shared', 'race', 'weak'])
def test_admission_with_existing_http_transport_guards(selected, tmp_path, mode):
    import httpx
    from tests.test_google_markdown_transport import API, transport
    inputs = adoption_inputs(selected, tmp_path)
    api = API()
    api.content = inputs[2].text.encode('utf-8')
    if mode == 'race': api.changed = True
    if mode == 'weak': api.etag = 'W/"one"'
    original = api.handle
    def guarded(request):
        if mode == 'wrong_account' and request.url.path.endswith('/about'):
            return httpx.Response(200, json={'user': {'permissionId': 'other', 'emailAddress': 'other@example.invalid'}})
        if mode == 'shared' and request.url.path.endswith('/permissions'):
            return httpx.Response(200, json={'permissions': []})
        return original(request)
    api.handle = guarded
    with transport(api) as active:
        result = admit(inputs, transport=active)
    assert result['status'] == ('success' if mode == 'valid' else 'failed')
    assert inputs[4].path.exists() == (mode == 'valid')
    assert api.writes == []


def test_admission_refuses_committed_symlink_even_with_matching_bytes(selected, tmp_path):
    inputs = adoption_inputs(selected, tmp_path)
    root, artifact, source, remote, store, receipts = inputs
    path = root / source.path
    path.unlink(); path.symlink_to('../b/reference.md')
    git(root, 'add', '.'); git(root, 'commit', '-qm', 'symlink')
    raw = b'../b/reference.md'
    source = replace(source, text=raw.decode(), source_revision=git(root, 'rev-parse', 'HEAD:' + source.path))
    receipt = dict(artifact.receipt, commit=git(root, 'rev-parse', 'HEAD'), sources=[
        dict(path=source.path, blob_oid=source.source_revision, sha256=hashlib.sha256(raw).hexdigest(), byte_count=len(raw))])
    remote.snapshot = replace(remote.snapshot, content=raw)
    result = admit(inputs, source=source, receipt=receipt)
    assert result['status'] == 'failed' and not store.path.exists() and remote.writes == 0


def test_admission_requires_actual_repository_root(selected, tmp_path):
    inputs = adoption_inputs(selected, tmp_path)
    nested = inputs[0] / 'nested' / inputs[2].repo
    nested.mkdir(parents=True)
    result = admit(inputs, source_root=nested)
    assert result['status'] == 'failed' and not inputs[4].path.exists() and inputs[3].writes == 0
