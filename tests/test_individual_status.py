"""Synthetic evidence only; no provider, network, credential or runtime access."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from notebooklm_mcp.doc_refresh.individual_status import reduce_status, main

NOW = '2026-10-03T00:00:00Z'
HASH = 'a' * 64


def inputs():
    selected = [{'repo': 'C099', 'path': 'a.md', 'sha256': HASH}]
    entry = {'file_id': 'fictional_file', 'verified': {'sha256': HASH, 'etag': '"v1"',
             'source': {'commit': 'b' * 40}}, 'pending': None, 'notebook': None}
    notebooks = {'C099': {'notebook_id': 'fictional_notebook', 'drive_documents': {'a.md': entry}}}
    return selected, notebooks


def test_publication_never_proves_notebook_current_and_pure():
    selected, notebooks = inputs()
    before = deepcopy(notebooks)
    result = reduce_status(selected, notebooks, [], now=NOW)
    row = result['items'][0]
    assert row['publication'] == 'recorded_verified'
    assert row['notebook_observation'] == 'unknown'
    assert row['observation_evidence_at'] is None
    assert 'receipt_missing' in row['problems']
    assert notebooks == before
    assert result == reduce_status(selected, notebooks, [], now=NOW)


def test_changed_original_and_stale_observation_pending():
    selected, notebooks = inputs()
    entry = notebooks['C099']['drive_documents']['a.md']
    entry['notebook'] = {'sha256': HASH, 'source_id': 'fictional_source', 'evidence': 'fixture_ref'}
    entry['pending'] = {'operation_id': 'fictional_operation'}
    selected[0]['sha256'] = 'c' * 64
    row = reduce_status(selected, notebooks, [], now=NOW)['items'][0]
    assert row['publication'] == 'changed' and row['notebook_observation'] == 'stale'
    assert 'pending_reconciliation' in row['problems']
    assert 'original inputs' in row['next_action']


def test_new_failure_partial_missing_source_and_explicit_stale_bound():
    selected, notebooks = inputs()
    notebooks['C099']['drive_documents']['b.md'] = deepcopy(notebooks['C099']['drive_documents']['a.md'])
    receipts = json.loads((Path(__file__).parent / 'fixtures/individual_status/receipts.json').read_text())
    result = reduce_status(selected, notebooks, receipts, now=NOW)
    a, b = result['items']
    assert a['last_successful_publication_at'] == '2026-10-01T00:00:00Z'
    assert a['receipt_freshness'] == 'unknown'
    assert 'latest_run_failed_or_partial' in a['problems']
    assert 'original_missing_from_selection' in b['problems']
    assert result['aggregate'] == 'attention'
    bounded = reduce_status(selected, notebooks, receipts, now=NOW, stale_after_seconds=60)
    assert bounded['items'][0]['receipt_freshness'] == 'stale'


def test_matching_observation_has_no_invented_time_or_mode():
    selected, notebooks = inputs()
    notebooks['C099']['drive_documents']['a.md']['notebook'] = {
        'sha256': HASH, 'source_id': 'fictional_source', 'evidence': 'fixture_ref'}
    row = reduce_status(selected, notebooks, [], now=NOW)['items'][0]
    assert row['notebook_observation'] == 'recorded_hash_match'
    assert row['observation_evidence_at'] is None
    assert row['last_successful_scheduled_run_at'] is None


def test_plan_receipts_do_not_count_and_unattributed_preflight_visible():
    selected, notebooks = inputs()
    receipt = {'format': 'c021.individual-publication-batch.v1', 'mode': 'status',
               'completed_at': NOW, 'status': 'success', 'items': []}
    assert reduce_status(selected, notebooks, [receipt], now=NOW)['items'][0]['last_successful_publication_at'] is None
    receipt.update(mode='publish', status='failed')
    assert 'unattributed_preflight_failure' in reduce_status(selected, notebooks, [receipt], now=NOW)['items'][0]['problems']


@pytest.mark.parametrize('now, threshold', [('2026-10-03', None), (NOW, 0), (NOW, -1)])
def test_invalid_time_or_bound_refused(now, threshold):
    with pytest.raises(ValueError):
        reduce_status([], {}, [], now=now, stale_after_seconds=threshold)


def test_cli_reads_without_writing(tmp_path, monkeypatch, capsys):
    from notebooklm_mcp.doc_refresh import individual_status as module
    from types import SimpleNamespace
    map_path = tmp_path / 'map.yaml'
    map_path.write_text('notebooks: {}\n')
    before = map_path.read_bytes()
    monkeypatch.setattr(module, 'build_bundle', lambda *a, **k: SimpleNamespace(
        documents=[], receipt={'commit': 'b' * 40}))
    args = ['--repo', str(tmp_path), 'b' * 40, '--manifest', str(tmp_path / 'manifest'),
            '--map', str(map_path), '--receipts', str(tmp_path), '--now', NOW]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    assert capsys.readouterr().out == first
    assert map_path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ['map.yaml']


def test_cli_real_git_selection_is_hermetic(tmp_path, capsys, monkeypatch):
    import socket
    import subprocess
    import yaml
    from notebooklm_mcp.doc_refresh.manifest import load_manifest
    def no_network(*args, **kwargs):
        raise AssertionError('Offline status attempted network')
    monkeypatch.setattr(socket, 'socket', no_network)
    root = tmp_path / 'C099'
    root.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()
    git('init', '-q')
    git('config', 'user.name', 'Fixture')
    git('config', 'user.email', 'fixture@example.invalid')
    (root / 'a.md').write_text('# Fictional original\n')
    git('add', '.')
    git('commit', '-qm', 'fixture')
    manifest = load_manifest()
    for tier in manifest['tiers'].values():
        tier['documents'] = []
    manifest['repo_overrides'] = {'C099': {'extra_docs': [
        {'path': 'a.md', 'purpose': 'fixture', 'must_exist': True, 'stub_allowed': False}]}}
    manifest_path = tmp_path / 'manifest.yaml'
    manifest_path.write_text(yaml.safe_dump(manifest))
    map_path = tmp_path / 'map.yaml'
    map_path.write_text('notebooks: {}\n')
    receipts = tmp_path / 'receipts'
    receipts.mkdir()
    before = map_path.read_bytes()
    args = ['--repo', str(root), git('rev-parse', 'HEAD'), '--manifest', str(manifest_path),
            '--map', str(map_path), '--receipts', str(receipts), '--now', NOW]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['items'][0]['path'] == 'a.md'
    assert 'binding_missing' in result['items'][0]['problems']
    assert map_path.read_bytes() == before and not list(receipts.iterdir())
    assert not (tmp_path / 'map.yaml.lock').exists()
