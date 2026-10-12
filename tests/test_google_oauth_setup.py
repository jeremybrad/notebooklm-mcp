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


@pytest.fixture
def picker_setup(tmp_path,monkeypatch):
    """Fictional credential bytes in memory; never native store, browser or HTTP."""
    from dataclasses import replace
    import httpx,socket,webbrowser
    from notebooklm_mcp.doc_refresh import google_keychain
    previous=grant();updated=replace(previous,refresh_token='new-fictional-refresh')
    events=[];state={'bytes':previous.serialize(),'mode':'success'}
    def unexpected(*args,**kwargs):pytest.fail('Unexpected real network/browser/Security.framework call')
    monkeypatch.setattr(httpx.Client,'send',unexpected);monkeypatch.setattr(socket,'socket',unexpected);monkeypatch.setattr(webbrowser,'open',unexpected)
    for name in ('read','create','update'):monkeypatch.setattr(google_keychain.KeychainStore,name,unexpected)
    monkeypatch.setattr(setup,'load_desktop_client',unexpected)
    monkeypatch.setattr(setup,'get_authorization_code',unexpected)
    class Store:
        def __init__(self,selection):pass
        def read(self,*,interactive):
            assert interactive is False;events.append('read')
            if state['mode']=='readback_fail' and 'update' in events:raise KeychainError('access_denied')
            return state['bytes']
        def create(self,*args,**kwargs):unexpected()
        def update(self,expected,payload,*,interactive):
            assert interactive is False;events.append('update')
            if state['bytes']!=expected:raise KeychainError('conflict')
            assert expected==previous.serialize()
            state['bytes']=payload
            if state['mode']=='update_uncertain':raise KeychainError('native_failure')
    class OAuth:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def exchange_code(self,client,code,uri,verifier,email):
            events.append('exchange');assert client==previous.client
            return state.get('returned',updated)
    def selected(client,*,file_id):
        events.append('selection');assert client==previous.client and file_id=='fictional_file'
        if state['mode']=='concurrent':state['bytes']=replace(previous,refresh_token='concurrent-fictional-refresh').serialize()
        if state['mode']=='selection_fail':raise setup.LoopbackError('loopback_selection_refused')
        return ('fictional-code','http://127.0.0.1:123/oauth2/callback','v'*43)
    monkeypatch.setattr(setup,'KeychainStore',Store);monkeypatch.setattr(setup,'OAuthClient',OAuth)
    monkeypatch.setattr(setup,'get_file_authorization_code',selected,raising=False)
    monkeypatch.setattr('builtins.input',lambda _:previous.account.email_address+' fictional_file')
    args=['select-file','--config',str(configuration(tmp_path)),'--file-id','fictional_file']
    return args,state,events,previous,updated


def test_picker_setup_updates_only_existing_item_with_readback(picker_setup,capsys):
    args,state,events,previous,updated=picker_setup
    assert setup.main(args)==0
    assert events==['read','selection','exchange','update','read']
    assert state['bytes']==updated.serialize()
    output=capsys.readouterr()
    for secret in ('fictional-code','fictional-refresh-secret','new-fictional-refresh','fictional-client-secret'):
        assert secret not in output.out+output.err
    assert 'file_selection_grant_stored' in output.out

@pytest.mark.parametrize('mode',['selection_fail','concurrent','update_uncertain','readback_fail'])
def test_picker_setup_failure_has_no_retry_and_reports_storage_uncertainty(picker_setup,capsys,mode):
    args,state,events,previous,updated=picker_setup;state['mode']=mode
    assert setup.main(args)==1
    assert events.count('selection')==1 and events.count('exchange')<=1 and events.count('update')<=1
    if mode=='selection_fail':assert events==['read','selection'] and state['bytes']==previous.serialize()
    output=capsys.readouterr()
    if mode in {'update_uncertain','readback_fail'}:assert 'credential_persistence_unknown' in output.err
    if mode=='concurrent':
        assert 'keychain_conflict' in output.err
        assert b'concurrent-fictional-refresh' in state['bytes']
        assert state['bytes']!=updated.serialize()
    if mode in {'update_uncertain','readback_fail'}:assert state['bytes']==updated.serialize()

@pytest.mark.parametrize('identity',['client','account','permission'])
def test_picker_setup_rejects_returned_identity_before_update(picker_setup,identity):
    from dataclasses import replace
    from notebooklm_mcp.doc_refresh.google_oauth import DesktopClient
    from notebooklm_mcp.doc_refresh.google_docs_transport import AccountExpectation
    args,state,events,previous,updated=picker_setup
    if identity=='client':state['returned']=replace(updated,client=DesktopClient('different.apps.googleusercontent.com','fictional-secret'))
    elif identity=='account':state['returned']=replace(updated,account=AccountExpectation(updated.account.permission_id,'other@example.invalid'))
    else:state['returned']=replace(updated,account=AccountExpectation('other',updated.account.email_address))
    assert setup.main(args)==1 and 'update' not in events

def test_picker_setup_declined_confirmation_leaves_old_bytes(picker_setup,monkeypatch):
    args,state,events,previous,_=picker_setup;monkeypatch.setattr('builtins.input',lambda _:'no')
    assert setup.main(args)==1 and 'update' not in events and state['bytes']==previous.serialize()

@pytest.mark.parametrize('change',['client','account','permission','secret','malformed'])
def test_picker_old_grant_mismatch_precedes_consent(picker_setup,change):
    from dataclasses import replace
    from notebooklm_mcp.doc_refresh.google_oauth import DesktopClient
    from notebooklm_mcp.doc_refresh.google_docs_transport import AccountExpectation
    args,state,events,previous,_=picker_setup
    if change=='malformed':state['bytes']=b'{fictional-sensitive-corrupt-grant'
    else:
        if change=='client':old=replace(previous,client=DesktopClient('other.apps.googleusercontent.com','fictional-secret'))
        elif change=='secret':old=replace(previous,client=DesktopClient(previous.client.client_id))
        elif change=='account':old=replace(previous,account=AccountExpectation(previous.account.permission_id,'other@example.invalid'))
        else:old=replace(previous,account=AccountExpectation('other',previous.account.email_address))
        state['bytes']=old.serialize()
    assert setup.main(args)==1 and events==['read']

def test_picker_requires_permission_pin_before_store(picker_setup):
    args,state,events,_,_=picker_setup
    path=__import__('pathlib').Path(args[2]);value=json.loads(path.read_text());value['permission_id']=None;path.write_text(json.dumps(value))
    assert setup.main(args)==1 and events==[]

@pytest.mark.parametrize('file_id',['','one,two','*','wrong/path','wrong%2Fpath'])
def test_picker_bad_file_id_precedes_store(picker_setup,file_id):
    args,state,events,_,_=picker_setup;args[-1]=file_id
    assert setup.main(args)==1 and events==[]

@pytest.mark.parametrize('mode',['diagnose','enroll','renew'])
def test_picker_file_flag_is_rejected_in_legacy_modes(picker_setup,mode):
    args,state,events,_,_=picker_setup;args[0]=mode
    with pytest.raises(SystemExit) as caught:setup.main(args)
    assert caught.value.code==2 and events==[]

def test_picker_missing_file_id_and_alternate_client_are_rejected(picker_setup):
    args,state,events,_,_=picker_setup
    for malformed in [args[:-2],args+['--client-config','/fictional/other-client.json']]:
        with pytest.raises(SystemExit) as caught:setup.main(malformed)
        assert caught.value.code==2
    assert events==[]

def test_picker_broad_returned_scope_is_rejected_before_storage(picker_setup):
    args,state,events,_,updated=picker_setup
    object.__setattr__(updated,'scopes',frozenset({'https://www.googleapis.com/auth/drive'}))
    state['returned']=updated
    assert setup.main(args)==1 and 'update' not in events

def test_picker_readback_difference_is_unknown_not_success(picker_setup,monkeypatch,capsys):
    args,state,events,previous,_=picker_setup
    actual=setup.KeychainStore
    class ChangedReadback(actual):
        def read(self,**kwargs):
            value=super().read(**kwargs)
            return previous.serialize() if 'update' in events else value
    monkeypatch.setattr(setup,'KeychainStore',ChangedReadback)
    assert setup.main(args)==1
    assert events.count('update')==1
    output=capsys.readouterr();assert 'credential_persistence_unknown' in output.err
    assert 'file_selection_grant_stored' not in output.out

def test_picker_missing_existing_grant_does_not_enroll(picker_setup,monkeypatch):
    args,state,events,_,_=picker_setup
    class Missing(setup.KeychainStore):
        def read(self,**kwargs):events.append('read');raise KeychainError('not_found')
    monkeypatch.setattr(setup,'KeychainStore',Missing)
    assert setup.main(args)==1 and events==['read']
