"""Synthetic storage and HTTP only: configuration -> pinned grant -> fixed lease."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path

import httpx
import pytest

from notebooklm_mcp.doc_refresh import publication_credentials as provider
from notebooklm_mcp.doc_refresh import publication_cli
from notebooklm_mcp.doc_refresh.google_docs_transport import AccountExpectation, DRIVE_FILE_SCOPE
from notebooklm_mcp.doc_refresh.google_oauth import DesktopClient, StoredGrant, OAuthClient
from notebooklm_mcp.doc_refresh.google_keychain import KeychainError
from notebooklm_mcp.doc_refresh.publication_batch import execute
from tests.test_publication_batch import managed, repo

EMAIL = 'jeremybradford1977@gmail.com'
CLIENT = 'fictional-client.apps.googleusercontent.com'
NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)


def configuration(tmp_path, repo_name='C099_test', **changes):
    value = {'version': 1, 'keychain_path': str(tmp_path / 'login.keychain-db'),
             'client_id': CLIENT, 'email': EMAIL, 'permission_id': 'fictional-permission',
             'destinations': {repo_name: {'document_id': 'synthetic-doc', 'parent_id': 'fictional-parent'}}}
    value.update(changes)
    path = tmp_path / 'credentials.json'
    path.write_text(json.dumps(value))
    return path


def grant(**changes):
    values = dict(client=DesktopClient(CLIENT, 'fictional-client-secret'),
                  refresh_token='fictional-refresh-secret',
                  account=AccountExpectation('fictional-permission', EMAIL), issued_at=NOW)
    values.update(changes)
    return StoredGrant(**values)


def forbid(*args, **kwargs):
    pytest.fail('Unexpected credential or network access')


@pytest.mark.parametrize('change', [
    {'version': True}, {'version': 2}, {'client_id': 'other'},
    {'keychain_path': 'relative/login.keychain-db'}, {'email': 'wrong@example.invalid'},
    {'permission_id': 42}, {'destinations': []},
    {'destinations': {'repo': {'document_id': 'doc', 'parent_id': '../path'}}},
    {'extra': 'fictional-secret-never-print'},
])
def test_bad_config_is_redacted(tmp_path, change):
    with pytest.raises(provider.ProviderError) as error:
        provider.load_config(configuration(tmp_path, **change), live=True)
    assert error.value.__context__ is None
    assert 'fictional-secret-never-print' not in str(error.value)


def test_config_is_pure_and_permission_required_only_for_live(tmp_path, monkeypatch):
    monkeypatch.setattr(provider, 'KeychainStore', forbid)
    monkeypatch.setattr(provider, 'OAuthClient', forbid)
    path = configuration(tmp_path, permission_id=None)
    config = provider.load_config(path)
    provider.transport_factory(config)
    with pytest.raises(provider.ProviderError):
        provider.load_config(path, live=True)


@pytest.mark.parametrize('body', ['{"version":1,"version":1}', '{"version": NaN}', '[]', '{"secret":'])
def test_strict_file_parser(tmp_path, body):
    path = tmp_path / 'bad.json'
    path.write_text(body)
    if body == '[]' or body.startswith('{"secret":'):
        with pytest.raises(provider.ProviderError):
            provider.read_json(path)
    else:
        with pytest.raises(provider.ProviderError):
            provider.load_config(path)


def test_private_client_file_permissions_and_kind(tmp_path):
    path = tmp_path / 'client.json'
    path.write_text(json.dumps({'installed': {'client_id': CLIENT, 'client_secret': 'fictional-secret',
          'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
          'token_uri': 'https://oauth2.googleapis.com/token'}}))
    path.chmod(0o644)
    with pytest.raises(provider.ProviderError):
        provider.load_desktop_client(path)
    path.chmod(0o600)
    assert provider.load_desktop_client(path).client_id == CLIENT
    linked = tmp_path / 'linked.json'
    linked.symlink_to(path)
    with pytest.raises(provider.ProviderError):
        provider.load_desktop_client(linked)
    value = json.loads(path.read_text())
    value['installed']['token_uri'] = 'https://untrusted.invalid/token'
    path.write_text(json.dumps(value))
    with pytest.raises(provider.ProviderError):
        provider.load_desktop_client(path)


@pytest.mark.parametrize('stored', [
    grant(client=DesktopClient('other.apps.googleusercontent.com')),
    grant(account=AccountExpectation('other-permission', EMAIL)),
    grant(account=AccountExpectation('fictional-permission', 'other@example.invalid')),
])
def test_mismatched_grant_refuses_before_oauth(tmp_path, monkeypatch, stored):
    class Store:
        def __init__(self, selection): pass
        def read(self, *, interactive):
            assert interactive is False
            return stored.serialize()
    monkeypatch.setattr(provider, 'KeychainStore', Store)
    monkeypatch.setattr(provider, 'OAuthClient', forbid)
    config = provider.load_config(configuration(tmp_path))
    from types import SimpleNamespace
    with pytest.raises(provider.ProviderError, match='grant_mismatch'):
        with provider.transport_factory(config)(SimpleNamespace(repo=Path('/fictional/C099_test')), 'synthetic-doc'):
            pytest.fail('Must not enter transport')


def test_destination_mismatch_precedes_keychain(tmp_path, monkeypatch):
    monkeypatch.setattr(provider, 'KeychainStore', forbid)
    config = provider.load_config(configuration(tmp_path))
    from types import SimpleNamespace
    with pytest.raises(provider.ProviderError, match='destination_mismatch'):
        with provider.transport_factory(config)(SimpleNamespace(repo=Path('/fictional/C099_test')), 'wrong-doc'):
            pass


def test_cli_to_refresh_to_publication_and_noop(managed, tmp_path, monkeypatch, capsys):
    job, store, receipts, remote = managed
    config_path = configuration(tmp_path, repo_name=job.repo.name)
    events = []
    class Store:
        def __init__(self, selection):
            assert selection.service == provider.SERVICE
        def read(self, *, interactive):
            assert interactive is False
            events.append('keychain')
            return grant().serialize()
    def response(request):
        events.append(request.url.path)
        if request.url.path == '/token':
            assert request.method == 'POST'
            assert b'fictional-refresh-secret' in request.content
            return httpx.Response(200, json={'access_token': 'fictional-access-secret',
                'token_type': 'Bearer', 'expires_in': 3600, 'scope': DRIVE_FILE_SCOPE})
        assert request.url.path == '/drive/v3/about'
        assert request.headers['authorization'] == 'Bearer fictional-access-secret'
        return httpx.Response(200, json={'user': {'permissionId': 'fictional-permission', 'emailAddress': EMAIL}})
    @contextmanager
    def docs(lease, account, destination):
        events.append('docs')
        assert lease.bearer == 'fictional-access-secret'
        assert account == grant().account
        assert destination.document_id == 'synthetic-doc'
        yield remote
    monkeypatch.setattr(provider, 'KeychainStore', Store)
    monkeypatch.setattr(provider, 'OAuthClient', lambda: OAuthClient(http_transport=httpx.MockTransport(response), clock=lambda: NOW))
    monkeypatch.setattr(provider, 'GoogleDocsTransport', docs)
    args = ['publish', '--repo', str(job.repo), job.revision, '--map', str(store.path),
            '--receipts', str(receipts), '--credentials-config', str(config_path)]
    assert publication_cli.main(args) == 0
    assert events == ['keychain', '/token', '/drive/v3/about', 'docs']
    assert remote.writes == 1
    assert publication_cli.main(args) == 0
    assert remote.writes == 1
    output = capsys.readouterr().out
    assert 'fictional-refresh-secret' not in output and 'fictional-access-secret' not in output
    for receipt in receipts.glob('*.json'):
        assert 'fictional-refresh-secret' not in receipt.read_text()


def test_storage_refusal_is_actionable_redacted_terminal_receipt(managed, tmp_path, monkeypatch):
    job, store, receipts, remote = managed
    class Store:
        def __init__(self, selection): pass
        def read(self, **kwargs): raise KeychainError('interaction_required')
    monkeypatch.setattr(provider, 'KeychainStore', Store)
    monkeypatch.setattr(provider, 'OAuthClient', forbid)
    config = provider.load_config(configuration(tmp_path, repo_name=job.repo.name))
    result = execute('publish', [job], store, receipts, transport_factory=provider.transport_factory(config))
    assert result['items'][0]['error_code'] == 'credential_keychain_interaction_required'
    assert remote.writes == 0
    saved = json.loads(Path(result['receipt_path']).read_text())
    assert saved['status'] == 'failed'
    assert saved['items'] == result['items']


def test_bad_sources_prevent_keychain_access(managed, tmp_path, monkeypatch):
    job, store, receipts, remote = managed
    monkeypatch.setattr(provider, 'KeychainStore', forbid)
    config = provider.load_config(configuration(tmp_path, repo_name=job.repo.name))
    from notebooklm_mcp.doc_refresh.publication_batch import Job
    result = execute('publish', [Job(job.repo, '0' * 40)], store, receipts,
                     transport_factory=provider.transport_factory(config))
    assert result['items'][0]['error_code'] == 'source_preflight_failed'


@pytest.mark.parametrize('mode', ['plan', 'status'])
def test_offline_cli_remains_credential_free(managed, tmp_path, monkeypatch, mode, capsys):
    job, store, receipts, remote = managed
    monkeypatch.setattr(provider, 'KeychainStore', forbid)
    monkeypatch.setattr(provider, 'OAuthClient', forbid)
    args = [mode, '--repo', str(job.repo), job.revision, '--map', str(store.path), '--receipts', str(receipts)]
    assert publication_cli.main(args) == 0
    with pytest.raises(SystemExit) as error:
        publication_cli.main(args + ['--credentials-config', str(configuration(tmp_path))])
    assert error.value.code == 2
