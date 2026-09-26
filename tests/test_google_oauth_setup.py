"""Explicit setup with fictional client files, fake consent and fake secure store."""
import json

import pytest

from notebooklm_mcp.doc_refresh import google_oauth_setup as setup
from notebooklm_mcp.doc_refresh.google_keychain import KeychainError
from tests.test_publication_credentials import CLIENT, configuration, grant, forbid


def client_file(tmp_path):
    path = tmp_path / 'client.json'
    path.write_text(json.dumps({'installed': {'client_id': CLIENT, 'client_secret': 'fictional-client-secret',
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token'}}))
    path.chmod(0o600)
    return path


def test_diagnose_never_opens_client_store_or_consent(tmp_path, monkeypatch, capsys):
    for name in ('KeychainStore', 'OAuthClient', 'get_authorization_code', 'load_desktop_client'):
        monkeypatch.setattr(setup, name, forbid)
    assert setup.main(['diagnose', '--config', str(configuration(tmp_path, permission_id=None))]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {'status': 'configuration_valid', 'credential_access': False,
                      'account_pinned': False, 'destination_count': 1}


@pytest.mark.parametrize('mode', ['enroll', 'renew'])
def test_setup_confirms_identity_and_uses_only_requested_write(tmp_path, monkeypatch, capsys, mode):
    previous = grant()
    writes = []
    class Store:
        def __init__(self, selection): pass
        def read(self, *, interactive):
            assert interactive is True
            return previous.serialize()
        def create(self, payload, *, interactive):
            assert interactive is True
            writes.append(('create', payload))
        def update(self, expected, payload, *, interactive):
            assert interactive is True and expected == previous.serialize()
            writes.append(('update', payload))
    class OAuth:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def exchange_code(self, client, code, uri, verifier, email):
            assert client.client_id == CLIENT and code == 'fictional-code'
            return previous
    monkeypatch.setattr(setup, 'KeychainStore', Store)
    monkeypatch.setattr(setup, 'OAuthClient', OAuth)
    monkeypatch.setattr(setup, 'get_authorization_code', lambda _: ('fictional-code', 'http://127.0.0.1:123/callback', 'v' * 43))
    monkeypatch.setattr('builtins.input', lambda _: previous.account.email_address)
    args = [mode, '--config', str(configuration(tmp_path)), '--client-config', str(client_file(tmp_path))]
    assert setup.main(args) == 0
    assert writes == [('create' if mode == 'enroll' else 'update', previous.serialize())]
    output = capsys.readouterr().out
    for secret in ('fictional-code', 'fictional-client-secret', 'fictional-refresh-secret'):
        assert secret not in output


def test_rejected_account_confirmation_never_persists(tmp_path, monkeypatch, capsys):
    class Store:
        def __init__(self, selection): pass
        create = update = forbid
    class OAuth:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def exchange_code(self, *args): return grant()
    monkeypatch.setattr(setup, 'KeychainStore', Store)
    monkeypatch.setattr(setup, 'OAuthClient', OAuth)
    monkeypatch.setattr(setup, 'get_authorization_code', lambda _: ('code', 'uri', 'verifier'))
    monkeypatch.setattr('builtins.input', lambda _: 'no')
    assert setup.main(['enroll', '--config', str(configuration(tmp_path)), '--client-config', str(client_file(tmp_path))]) == 1
    assert 'not stored' in capsys.readouterr().err


def test_renew_store_failure_precedes_browser_and_is_redacted(tmp_path, monkeypatch, capsys):
    class Store:
        def __init__(self, selection): pass
        def read(self, **kwargs): raise KeychainError('access_denied')
    monkeypatch.setattr(setup, 'KeychainStore', Store)
    monkeypatch.setattr(setup, 'get_authorization_code', forbid)
    assert setup.main(['renew', '--config', str(configuration(tmp_path)), '--client-config', str(client_file(tmp_path))]) == 1
    assert capsys.readouterr().err.strip() == 'keychain_access_denied'


@pytest.mark.parametrize('secret', ['missing', None, ''])
@pytest.mark.parametrize('mode', ['enroll', 'renew'])
def test_desktop_file_without_secret_refuses_before_consent(tmp_path, monkeypatch, capsys, secret, mode):
    path = client_file(tmp_path)
    value = json.loads(path.read_text())
    if secret == 'missing':
        del value['installed']['client_secret']
    else:
        value['installed']['client_secret'] = secret
    path.write_text(json.dumps(value))
    touched = []
    def unexpected(*args, **kwargs):
        touched.append('credential-or-consent-access')
        raise RuntimeError('fictional-secret-must-not-print')
    for name in ('KeychainStore', 'OAuthClient', 'get_authorization_code'):
        monkeypatch.setattr(setup, name, unexpected)
    assert setup.main([mode, '--config', str(configuration(tmp_path)), '--client-config', str(path)]) == 1
    assert touched == []
    assert 'fictional-secret' not in capsys.readouterr().err
