"""Command safety and offline execution, with fictional repositories only."""
import json
import pytest


from notebooklm_mcp.doc_refresh.publication_cli import main
from tests.test_source_bundle import repo as source_repo, git
from tests.test_publication_cohort import configured, repo


def arguments(tmp_path, repository, mode="plan"):
    revision = git(repository, "rev-parse", "HEAD")
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    return [mode, "--repo", str(repository), revision, "--map", str(tmp_path / "map.yaml"),
            "--receipts", str(receipts)]


def test_default_offline_plan_never_creates_map(tmp_path, capsys, source_repo):
    args = arguments(tmp_path, source_repo)
    assert main(args[1:]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "plan"
    assert result["status"] == "success"
    assert not (tmp_path / "map.yaml").exists()
    assert len(list((tmp_path / "receipts").glob("*.json"))) == 1


def test_cli_has_no_ambient_provider(tmp_path, capsys, monkeypatch, source_repo):
    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN", "fictional-do-not-use-or-print")
    monkeypatch.setenv("GEMINI_API_KEY", "fictional-do-not-use-or-print")
    assert main(arguments(tmp_path, source_repo, "publish")) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "failed"
    assert "fictional-do-not" not in json.dumps(result)
    assert not (tmp_path / "map.yaml").exists()


def test_malformed_snapshot_is_redacted_and_never_executes(tmp_path, capsys, source_repo):
    path = tmp_path / "snapshots.json"
    path.write_text('{"secret":"never-report-this"')
    assert main(arguments(tmp_path, source_repo) + ["--snapshots", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "never-report-this" not in captured.err
    assert not list((tmp_path / "receipts").iterdir())


def test_duplicate_snapshot_keys_refused(tmp_path, capsys, source_repo):
    path = tmp_path / "snapshots.json"
    path.write_text('{"repo":{},"repo":{}}')
    assert main(arguments(tmp_path, source_repo) + ["--snapshots", str(path)]) == 2
    assert "Invalid snapshot input" in capsys.readouterr().err


def test_receipt_failure_is_nonzero_without_success_output(tmp_path, capsys, source_repo):
    args = arguments(tmp_path, source_repo)
    args[-1] = str(tmp_path / "missing" / "receipts")
    assert main(args) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "Receipt persistence failed" in captured.err


def cohort_arguments(tmp_path, path, mode='plan'):
    receipts = tmp_path / 'receipts'
    receipts.mkdir(exist_ok=True)
    return [mode, '--cohort', str(path), '--map', str(tmp_path / 'map.yaml'),
            '--receipts', str(receipts)]


def test_cohort_plan_is_offline(configured, tmp_path, capsys, monkeypatch):
    from notebooklm_mcp.doc_refresh import publication_cli as cli
    path, _, _ = configured
    monkeypatch.setattr(cli, 'load_config', lambda *a, **k: pytest.fail('config access'))
    assert main(cohort_arguments(tmp_path, path)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['cohort_preflight']['ref_freshness'] == 'unverified-local-ref'
    assert not (tmp_path / 'map.yaml').exists()


def test_cohort_publish_requires_explicit_fetch(configured, tmp_path):
    path, _, _ = configured
    with pytest.raises(SystemExit) as error:
        main(cohort_arguments(tmp_path, path, 'publish'))
    assert error.value.code == 2


def test_cohort_reconcile_requires_original_explicit_commits(configured, tmp_path):
    path, _, _ = configured
    with pytest.raises(SystemExit) as error:
        main(cohort_arguments(tmp_path, path, 'reconcile'))
    assert error.value.code == 2


def test_fetch_not_available_for_legacy_explicit_commits(source_repo, tmp_path):
    with pytest.raises(SystemExit) as error:
        main(arguments(tmp_path, source_repo) + ['--fetch'])
    assert error.value.code == 2


@pytest.mark.parametrize('fault', ['second_source', 'second_destination', 'fetch'])
def test_cohort_preflight_failure_never_opens_provider(configured, tmp_path, monkeypatch, capsys, fault):
    import shutil
    from types import SimpleNamespace
    from notebooklm_mcp.doc_refresh import publication_cli as cli, publication_cohort as cohort
    from notebooklm_mcp.doc_refresh.publication_state import MapStore, bind_empty
    from tests.test_drive_publication import document
    from tests.test_source_bundle import commit

    path, data, first = configured
    second = first.parent / 'C098_fictional'
    shutil.copytree(first, second)
    data['repositories'].append({**data['repositories'][0], 'root': str(second), 'name': second.name})
    path.write_text(json.dumps(data))
    if fault == 'second_source':
        (second / 'README.md').unlink()
        revision = commit(second)
        git(second, 'update-ref', 'refs/remotes/origin/main', revision)
    store = MapStore(tmp_path / 'map.yaml')
    destinations = {}
    for index, root in enumerate((first, second)):
        doc_id = 'fictional-doc-' + str(index)
        bind_empty(store, root.name, 'fictional-notebook-' + str(index), document(document_id=doc_id))
        destinations[root.name] = SimpleNamespace(document_id=doc_id)
    if fault == 'second_destination':
        destinations.pop(second.name)
    monkeypatch.setattr(cli, 'load_config', lambda *a, **k: SimpleNamespace(destinations=destinations))
    calls = []
    def factory(config):
        def opened(*args):
            calls.append(args)
            pytest.fail('provider opened despite cohort preflight failure')
        return opened
    monkeypatch.setattr(cli, 'transport_factory', factory)
    real = cohort._git
    def synthetic_fetch(root, *args):
        if 'fetch' in args:
            if fault == 'fetch' and root == second:
                raise cohort.CohortError('fetch_failed')
            return ''
        return real(root, *args)
    monkeypatch.setattr(cohort, '_git', synthetic_fetch)
    args = cohort_arguments(tmp_path, path, 'publish') + ['--fetch', '--credentials-config', 'fictional.json']
    assert main(args) in (1, 2)
    assert not calls
    output = capsys.readouterr()
    if fault == 'second_source':
        result = json.loads(output.out)
        assert result['items'][1]['error_code'] == 'source_preflight_failed'
        assert result['remote_verified_count'] == 0
    else:
        assert 'Cohort preflight failed:' in output.err


def test_cohort_live_handoff_keeps_captured_manifest_and_commit(configured, tmp_path, monkeypatch, capsys):
    from pathlib import Path
    from types import SimpleNamespace
    from contextlib import contextmanager
    from notebooklm_mcp.doc_refresh import publication_cli as cli, publication_cohort as cohort
    from notebooklm_mcp.doc_refresh.publication_state import MapStore, bind_empty
    from tests.test_publication_batch import FakeDocs
    from tests.test_source_bundle import commit

    path, data, root = configured
    original_commit = git(root, 'rev-parse', 'HEAD')
    remote = FakeDocs()
    bind_empty(MapStore(tmp_path / 'map.yaml'), root.name, 'fictional-notebook', remote.raw)
    config = SimpleNamespace(destinations={root.name: SimpleNamespace(document_id=remote.raw['documentId'])})
    monkeypatch.setattr(cli, 'load_config', lambda *a, **k: config)
    real = cohort._git
    def synthetic_fetch(root, *args):
        return '' if 'fetch' in args else real(root, *args)
    monkeypatch.setattr(cohort, '_git', synthetic_fetch)
    @contextmanager
    def provider(job, document_id):
        Path(data['manifest']['path']).write_text('unapproved replacement')
        (root / 'README.md').write_text('new unapproved revision')
        revision = commit(root)
        git(root, 'update-ref', 'refs/remotes/origin/main', revision)
        yield remote
    monkeypatch.setattr(cli, 'transport_factory', lambda config: provider)
    args = cohort_arguments(tmp_path, path, 'publish') + ['--fetch', '--credentials-config', 'fictional.json']
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['items'][0]['commit'] == original_commit
    assert 'new unapproved revision' not in str(remote.raw)
    assert remote.writes == 1
    assert result['cohort_preflight']['ref_freshness'] == 'fetched-origin'
