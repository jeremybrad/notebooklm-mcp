"""Fictional Git sources and remote state; no live credentials or Google calls."""
import hashlib
import subprocess
from dataclasses import replace

import pytest
import yaml

from notebooklm_mcp.doc_refresh.manifest import load_manifest
from notebooklm_mcp.doc_refresh.source_bundle import build_bundle
from notebooklm_mcp.doc_refresh.publication_state import MapStore, StateError
from notebooklm_mcp.doc_refresh.individual_publication import (
    document_key, bind_empty, publish, reconcile, Snapshot,
)


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
