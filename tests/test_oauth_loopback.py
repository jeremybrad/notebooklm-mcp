"""Fictional OAuth clients and localhost sockets only; never open a browser."""
import base64
import hashlib
import socket
import threading
import time
import traceback
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from notebooklm_mcp.doc_refresh.google_oauth import DesktopClient
from notebooklm_mcp.doc_refresh import oauth_loopback as loopback

CLIENT = DesktopClient('fictional.apps.googleusercontent.com')
CODE = 'fictional-sensitive-authorization-code'


def details(url):
    fields = parse_qs(urlsplit(url).query)
    redirect = fields['redirect_uri'][0]
    return fields, urlsplit(redirect)


def request(url, *, query=None, target=None, host=None, method='GET', headers=''):
    fields, redirect = details(url)
    if query is None:
        query = urlencode({'code': CODE, 'state': fields['state'][0]})
    target = target if target is not None else redirect.path + '?' + query
    host = host if host is not None else redirect.netloc
    raw = f'{method} {target} HTTP/1.1\r\nHost: {host}\r\n{headers}\r\n'.encode('ascii')
    with socket.create_connection((redirect.hostname, redirect.port), timeout=1) as peer:
        peer.sendall(raw)
        return peer.recv(4096)


def assert_closed(url):
    _, redirect = details(url)
    with pytest.raises(OSError):
        socket.create_connection((redirect.hostname, redirect.port), timeout=.2)


def opener_for(action):
    seen = []
    finished = threading.Event()
    errors = []

    def opener(url):
        seen.append(url)
        try:
            action(url)
        except Exception as exc:
            errors.append(type(exc).__name__)
            return False
        finally:
            finished.set()
        return True
    return opener, seen, finished, errors


def test_success_pkce_extra_fields_and_listener_cleanup():
    responses = []

    def action(url):
        fields, _ = details(url)
        responses.append(request(url, query=urlencode({
            'state': fields['state'][0], 'code': CODE,
            'scope': 'https://www.googleapis.com/auth/drive.file', 'authuser': '0', 'prompt': 'consent',
        })))

    opener, seen, finished, errors = opener_for(action)
    code, redirect, verifier = loopback.get_authorization_code(CLIENT, opener=opener, timeout=2)
    assert finished.wait(1) and not errors
    fields, uri = details(seen[0])
    assert code == CODE
    assert redirect == fields['redirect_uri'][0]
    assert uri.hostname == '127.0.0.1' and uri.path == '/oauth2/callback' and uri.port
    assert fields['code_challenge'][0] == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    assert 43 <= len(verifier) <= 128 and len(fields['state'][0]) >= 32
    assert b'200 OK' in responses[0] and CODE.encode() not in responses[0]
    assert fields['state'][0].encode() not in responses[0]
    assert_closed(seen[0])


@pytest.mark.parametrize('variant', ['csrf', 'path', 'duplicate_code', 'duplicate_state', 'duplicate_extra',
                                    'fragment', 'host', 'duplicate_host', 'absolute', 'tab_path',
                                    'method', 'bad_percent', 'code_and_error', 'body_length'])
def test_invalid_callbacks_do_not_consume_valid_result(variant):
    responses = []

    def action(url):
        fields, redirect = details(url)
        state = fields['state'][0]
        good = urlencode({'state': state, 'code': CODE})
        options = {
            'csrf': {'query': urlencode({'state': 'wrong', 'code': CODE})},
            'path': {'target': '/wrong?' + good},
            'duplicate_code': {'query': good + '&code=other'},
            'duplicate_state': {'query': good + '&state=' + state},
            'duplicate_extra': {'query': good + '&authuser=0&authuser=1'},
            'fragment': {'target': redirect.path + '?' + good + '#'},
            'host': {'host': 'localhost:' + str(redirect.port)},
            'duplicate_host': {'headers': 'Host: attacker.invalid\r\n'},
            'absolute': {'target': 'http://' + redirect.netloc + redirect.path + '?' + good},
            'tab_path': {'target': '/oauth2/\tcallback?' + good},
            'method': {'method': 'POST'},
            'bad_percent': {'query': good + '&prompt=%xx'},
            'code_and_error': {'query': good + '&error=access_denied'},
            'body_length': {'headers': 'Content-Length: 4\r\n'},
        }
        responses.append(request(url, **options[variant]))
        responses.append(request(url))

    opener, seen, finished, errors = opener_for(action)
    assert loopback.get_authorization_code(CLIENT, opener=opener, timeout=2)[0] == CODE
    assert finished.wait(1) and not errors
    assert b'400 Bad Request' in responses[0] and b'200 OK' in responses[1]
    assert_closed(seen[0])


def test_denial_is_terminal_redacted_and_closes_listener(capsys):
    secret = 'fictional-sensitive-error-description'

    def action(url):
        fields, _ = details(url)
        request(url, query=urlencode({'state': fields['state'][0], 'error': 'access_denied',
                                    'error_description': secret}))

    opener, seen, finished, errors = opener_for(action)
    with pytest.raises(loopback.LoopbackError) as caught:
        loopback.get_authorization_code(CLIENT, opener=opener, timeout=2)
    assert caught.value.code == 'loopback_denied'
    assert finished.wait(1) and not errors
    assert secret not in ''.join(traceback.format_exception(caught.value))
    assert capsys.readouterr() == ('', '')
    assert_closed(seen[0])


@pytest.mark.parametrize('raise_error', [False, True])
def test_browser_failure_redacts_exception_and_closes_listener(raise_error):
    seen = []

    def opener(url):
        seen.append(url)
        if raise_error:
            raise RuntimeError('sensitive-browser-error ' + url)
        return False

    with pytest.raises(loopback.LoopbackError) as caught:
        loopback.get_authorization_code(CLIENT, opener=opener, timeout=1)
    assert caught.value.code == 'loopback_browser_failed'
    assert 'sensitive-browser-error' not in ''.join(traceback.format_exception(caught.value))
    assert_closed(seen[0])


def test_no_callback_timeout_closes_listener():
    seen = []
    with pytest.raises(loopback.LoopbackError, match='loopback_timeout'):
        loopback.get_authorization_code(CLIENT, opener=lambda url: seen.append(url) or True, timeout=.1)
    assert_closed(seen[0])


def test_slow_peer_obeys_total_deadline():
    finished = threading.Event()
    seen = []

    def opener(url):
        seen.append(url)
        _, redirect = details(url)
        try:
            with socket.create_connection((redirect.hostname, redirect.port), timeout=1) as peer:
                for _ in range(100):
                    peer.sendall(b'G')
                    time.sleep(.025)
        except OSError:
            pass
        finally:
            finished.set()
        return True

    start = time.monotonic()
    with pytest.raises(loopback.LoopbackError, match='loopback_timeout'):
        loopback.get_authorization_code(CLIENT, opener=opener, timeout=.15)
    assert time.monotonic() - start < .8
    assert finished.wait(1)
    assert_closed(seen[0])


def test_stuck_opener_does_not_extend_deadline():
    release = threading.Event()
    seen = []

    def opener(url):
        seen.append(url)
        release.wait(2)
        return True

    try:
        start = time.monotonic()
        with pytest.raises(loopback.LoopbackError, match='loopback_timeout'):
            loopback.get_authorization_code(CLIENT, opener=opener, timeout=.1)
        assert time.monotonic() - start < .8
        assert_closed(seen[0])
    finally:
        release.set()


def test_invalid_attempts_bounded(monkeypatch):
    monkeypatch.setattr(loopback, '_MAX_ATTEMPTS', 3)
    opener, seen, finished, errors = opener_for(lambda url: [request(url, target='/wrong') for _ in range(3)])
    with pytest.raises(loopback.LoopbackError, match='loopback_invalid_attempts'):
        loopback.get_authorization_code(CLIENT, opener=opener, timeout=2)
    assert finished.wait(1) and not errors
    assert_closed(seen[0])


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf'), True, '1', 601])
def test_invalid_timeout_never_opens_browser(timeout):
    with pytest.raises(loopback.LoopbackError, match='loopback_invalid_timeout'):
        loopback.get_authorization_code(CLIENT, opener=lambda _: pytest.fail('browser opened'), timeout=timeout)


def test_configuration_failure_is_redacted_and_closes_listener(monkeypatch):
    redirects = []

    def invalid(client, redirect, state, verifier):
        redirects.append(redirect)
        raise ValueError('fictional-sensitive-config')

    monkeypatch.setattr(loopback, 'authorization_url', invalid)
    with pytest.raises(loopback.LoopbackError, match='loopback_configuration') as caught:
        loopback.get_authorization_code(CLIENT, opener=lambda _: pytest.fail('browser opened'))
    assert 'fictional-sensitive-config' not in ''.join(traceback.format_exception(caught.value))
    uri = urlsplit(redirects[0])
    with pytest.raises(OSError):
        socket.create_connection((uri.hostname, uri.port), timeout=.2)


def test_slow_request_budget_allows_later_valid_callback(monkeypatch):
    monkeypatch.setattr(loopback, '_REQUEST_SECONDS', .05)
    responses = []

    def action(url):
        _, redirect = details(url)
        with socket.create_connection((redirect.hostname, redirect.port), timeout=1) as peer:
            peer.sendall(b'GET ')
            responses.append(peer.recv(4096))
        responses.append(request(url))

    opener, seen, finished, errors = opener_for(action)
    assert loopback.get_authorization_code(CLIENT, opener=opener, timeout=1)[0] == CODE
    assert finished.wait(1) and not errors
    assert b'400 Bad Request' in responses[0] and b'200 OK' in responses[1]
    assert_closed(seen[0])


def test_oversized_headers_are_bounded(monkeypatch):
    monkeypatch.setattr(loopback, '_MAX_HEADER_BYTES', 256)
    responses = []

    def action(url):
        responses.append(request(url, headers='X-Large: ' + 'x' * 512 + '\r\n'))
        responses.append(request(url))

    opener, seen, finished, errors = opener_for(action)
    assert loopback.get_authorization_code(CLIENT, opener=opener, timeout=1)[0] == CODE
    assert finished.wait(1) and not errors
    assert b'400 Bad Request' in responses[0] and b'200 OK' in responses[1]
    assert_closed(seen[0])


def test_import_has_no_browser_or_listener_side_effect(monkeypatch):
    import importlib.util
    monkeypatch.setattr(socket, 'socket', lambda *a, **k: pytest.fail('listener created on import'))
    monkeypatch.setattr(loopback.webbrowser, 'open', lambda *a, **k: pytest.fail('browser opened on import'))
    spec = importlib.util.spec_from_file_location(
        'notebooklm_mcp.doc_refresh._loopback_import_probe', loopback.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


@pytest.fixture
def picker_receiver(monkeypatch):
    """No OS listener, browser, HTTP or native credential calls."""
    from collections import deque
    import httpx
    from notebooklm_mcp.doc_refresh.google_keychain import KeychainStore
    def forbid(*args,**kwargs):pytest.fail('Unexpected real network/browser/credential operation')
    monkeypatch.setattr(httpx.Client,'send',forbid)
    monkeypatch.setattr(loopback.webbrowser,'open',forbid)
    for name in ('read','create','update'):monkeypatch.setattr(KeychainStore,name,forbid)
    clock=[0.0]
    monkeypatch.setattr(loopback.time,'monotonic',lambda:clock[0])
    class Peer:
        def __init__(self,raw):self.raw=raw;self.sent=[];self.closed=False
        def __enter__(self):return self
        def __exit__(self,*args):self.closed=True
        def settimeout(self,*args):pass
        def recv(self,size):raw=self.raw[:size];self.raw=self.raw[size:];return raw
        def sendall(self,data):self.sent.append(data)
    class Listener:
        def __init__(self):self.peers=deque();self.closed=False;self.accepted=0;self.accepted_peers=[]
        def __enter__(self):return self
        def __exit__(self,*args):self.closed=True
        def bind(self,address):assert address==('127.0.0.1',0)
        def listen(self,*args):pass
        def getsockname(self):return ('127.0.0.1',12345)
        def settimeout(self,*args):pass
        def accept(self):
            if self.peers:
                self.accepted+=1;peer=self.peers.popleft();self.accepted_peers.append(peer);return peer,('127.0.0.1',123)
            clock[0]+=1;raise TimeoutError
    listener=Listener();listener.peer_type=Peer;listener.urls=[]
    monkeypatch.setattr(loopback.socket,'socket',lambda *args:listener)
    class ImmediateThread:
        def __init__(self,*,target,**kwargs):self.target=target
        def start(self):self.target()
    monkeypatch.setattr(loopback.threading,'Thread',ImmediateThread)
    def opener(callbacks):
        def opened(url):
            fields,redirect=details(url);listener.urls.append(url)
            for values in callbacks:
                pairs=[('state',fields['state'][0]),('code',CODE)]
                pairs.extend(values)
                raw=f'GET {redirect.path}?{urlencode(pairs)} HTTP/1.1\r\nHost: {redirect.netloc}\r\n\r\n'.encode()
                listener.peers.append(Peer(raw))
            return True
        return opened
    return listener,opener,clock


def test_picker_exact_singleton_listener_cleanup_and_replay(picker_receiver):
    listener,opener,_=picker_receiver
    result=loopback.get_file_authorization_code(CLIENT,file_id='fictional_file',opener=opener([[('picked_file_ids','fictional_file')],[('picked_file_ids','fictional_file')]]),timeout=2)
    assert result[0]==CODE and len(result)==3
    assert listener.closed and listener.accepted==1 and len(listener.peers)==1
    assert listener.accepted_peers[0].closed
    assert all(CODE.encode() not in response for response in listener.accepted_peers[0].sent)

@pytest.mark.parametrize('selection',[[],[('picked_file_ids','')],[('picked_file_ids','wrong')],[('picked_file_ids','fictional_file,other')],[('picked_file_ids','fictional_file,fictional_file')],[('picked_file_ids','fictional_file'),('picked_file_ids','fictional_file')],[('picked_file_ids',' fictional_file')],[('picked_file_ids','fictional_file'),('scope','broad')]])
def test_picker_selection_refusal_is_terminal_not_replaced(picker_receiver,selection):
    listener,opener,_=picker_receiver
    with pytest.raises(loopback.LoopbackError) as caught:
        loopback.get_file_authorization_code(CLIENT,file_id='fictional_file',opener=opener([selection,[('picked_file_ids','fictional_file')]]),timeout=2)
    assert caught.value.code=='loopback_selection_refused'
    assert listener.closed and listener.accepted==1

def test_picker_timeout_uses_fake_clock_and_closes_listener(picker_receiver):
    listener,opener,_=picker_receiver
    with pytest.raises(loopback.LoopbackError,match='loopback_timeout'):
        loopback.get_file_authorization_code(CLIENT,file_id='fictional_file',opener=opener([]),timeout=2)
    assert listener.closed


def test_picker_mixed_error_and_code_is_terminal(picker_receiver):
    listener,opener,_=picker_receiver
    with pytest.raises(loopback.LoopbackError) as caught:
        loopback.get_file_authorization_code(CLIENT,file_id='fictional_file',opener=opener([[('error','denied'),('picked_file_ids','fictional_file')],[('picked_file_ids','fictional_file')]]),timeout=2)
    assert caught.value.code=='loopback_selection_refused' and listener.closed and listener.accepted==1

@pytest.mark.parametrize('file_id',[None,'','*','one,two',123])
def test_picker_receiver_invalid_selector_precedes_listener(monkeypatch,file_id):
    def unexpected(*args,**kwargs):pytest.fail('Invalid selector opened a listener')
    monkeypatch.setattr(loopback.socket,'socket',unexpected)
    with pytest.raises(loopback.LoopbackError,match='loopback_configuration'):
        loopback.get_file_authorization_code(CLIENT,file_id=file_id)

def test_picker_legacy_result_shape_with_fake_listener(picker_receiver):
    listener,opener,_=picker_receiver
    result=loopback.get_authorization_code(CLIENT,opener=opener([[]]),timeout=2)
    assert len(result)==3 and result[0]==CODE and listener.closed

@pytest.mark.parametrize('mutation',['state','host','path','method','percent','scope','duplicate_state'])
def test_picker_callback_validates_protocol_and_selection_without_sockets(mutation):
    state='s'*43;host='127.0.0.1:123';method='GET';path='/oauth2/callback'
    pairs=[('state',state),('code',CODE),('picked_file_ids','fictional_file')]
    expected=None
    if mutation=='state':pairs[0]=('state','wrong')
    elif mutation=='host':host='other.invalid'
    elif mutation=='path':path='/wrong'
    elif mutation=='method':method='POST'
    elif mutation=='percent':path+='?bad=%ZZ';pairs=[]
    elif mutation=='scope':pairs.append(('scope','broad'));expected=('selection-refused','')
    else:pairs.append(('state',state));expected=('selection-refused','')
    target=path+'?'+urlencode(pairs) if pairs else path
    raw=f'{method} {target} HTTP/1.1\r\nHost: {host}\r\n\r\n'.encode()
    assert loopback._callback_result(raw,'127.0.0.1:123',state,expected_file_id='fictional_file')==expected


def test_picker_denial_closes_fake_receiver_before_later_success(picker_receiver):
    listener,_,_=picker_receiver
    def opened(url):
        fields,redirect=details(url)
        for pairs in [[('state',fields['state'][0]),('error','access_denied')],[('state',fields['state'][0]),('code',CODE),('picked_file_ids','fictional_file')]]:
            raw=f'GET {redirect.path}?{urlencode(pairs)} HTTP/1.1\r\nHost: {redirect.netloc}\r\n\r\n'.encode()
            listener.peers.append(listener.peer_type(raw))
        return True
    with pytest.raises(loopback.LoopbackError,match='loopback_denied'):
        loopback.get_file_authorization_code(CLIENT,file_id='fictional_file',opener=opened,timeout=2)
    assert listener.closed and listener.accepted==1


def test_picker_csrf_frame_cannot_replace_matching_nonce_result(picker_receiver):
    listener,_,_=picker_receiver
    def opened(url):
        fields,redirect=details(url)
        for state in ['wrong',fields['state'][0]]:
            query=urlencode({'state':state,'code':CODE,'picked_file_ids':'fictional_file'})
            listener.peers.append(listener.peer_type(f'GET {redirect.path}?{query} HTTP/1.1\r\nHost: {redirect.netloc}\r\n\r\n'.encode()))
        return True
    assert loopback.get_file_authorization_code(CLIENT,file_id='fictional_file',opener=opened,timeout=2)[0]==CODE
    assert listener.closed and listener.accepted==2
    assert b'400 Bad Request' in listener.accepted_peers[0].sent[0]


def test_picker_fresh_invocations_have_distinct_state_and_pkce(picker_receiver):
    listener,opener,_=picker_receiver
    first=loopback.get_file_authorization_code(CLIENT,file_id='fictional_file',opener=opener([[('picked_file_ids','fictional_file')]]),timeout=2)
    second=loopback.get_file_authorization_code(CLIENT,file_id='fictional_file',opener=opener([[('picked_file_ids','fictional_file')]]),timeout=2)
    one=details(listener.urls[0])[0];two=details(listener.urls[1])[0]
    assert one['state']!=two['state'] and one['code_challenge']!=two['code_challenge']
    assert first[2]!=second[2]


def test_picker_prior_state_replay_never_yields_a_code():
    old='o'*43;current='n'*43;host='127.0.0.1:123'
    query=urlencode({'state':old,'code':CODE,'picked_file_ids':'fictional_file'})
    raw=f'GET /oauth2/callback?{query} HTTP/1.1\r\nHost: {host}\r\n\r\n'.encode()
    assert loopback._callback_result(raw,host,current,expected_file_id='fictional_file') is None


@pytest.mark.parametrize('states',[['current','current'],['wrong','current']])
def test_picker_duplicate_current_state_is_terminal_before_later_valid(picker_receiver,states):
    listener,_,_=picker_receiver
    def opened(url):
        fields,redirect=details(url)
        bad=[('state',fields['state'][0] if value=='current' else 'wrong') for value in states]
        bad += [('code',CODE),('picked_file_ids','fictional_file')]
        good=[('state',fields['state'][0]),('code',CODE),('picked_file_ids','fictional_file')]
        for pairs in [bad,good]:
            raw=f'GET {redirect.path}?{urlencode(pairs)} HTTP/1.1\r\nHost: {redirect.netloc}\r\n\r\n'.encode()
            listener.peers.append(listener.peer_type(raw))
        return True
    with pytest.raises(loopback.LoopbackError,match='loopback_selection_refused'):
        loopback.get_file_authorization_code(CLIENT,file_id='fictional_file',opener=opened,timeout=2)
    assert listener.closed and listener.accepted==1 and listener.accepted_peers[0].closed


def test_picker_duplicate_wrong_states_remain_bounded_untrusted_frames():
    host='127.0.0.1:123';state='s'*43
    pairs=[('state','wrong'),('state','also-wrong'),('code',CODE),('picked_file_ids','fictional_file')]
    raw=f'GET /oauth2/callback?{urlencode(pairs)} HTTP/1.1\r\nHost: {host}\r\n\r\n'.encode()
    assert loopback._callback_result(raw,host,state,expected_file_id='fictional_file') is None
