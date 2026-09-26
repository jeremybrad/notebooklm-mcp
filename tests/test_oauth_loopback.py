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
