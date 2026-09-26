"""Synthetic OAuth only: fictional tokens and HTTPX MockTransport, no store access."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import base64
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from notebooklm_mcp.doc_refresh import google_oauth as oauth
from notebooklm_mcp.doc_refresh.google_docs_transport import AccountExpectation, DRIVE_FILE_SCOPE

NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)
CLIENT = oauth.DesktopClient('fictional.apps.googleusercontent.com', 'SECRET-CLIENT')
ACCOUNT = AccountExpectation('fictional-owner', 'test@example.com')
VERIFIER = 'a' * 43
REDIRECT = 'http://127.0.0.1:12345/callback'
GRANT = oauth.StoredGrant(CLIENT, 'SECRET-REFRESH', ACCOUNT, NOW)


def token(**updates):
    value = {'token_type': 'Bearer', 'access_token': 'SECRET-ACCESS',
             'refresh_token': 'SECRET-REFRESH', 'expires_in': 3600, 'scope': DRIVE_FILE_SCOPE}
    value.update(updates)
    return value


def identity(**updates):
    return {'user': {'permissionId': ACCOUNT.permission_id, 'emailAddress': ACCOUNT.email_address, **updates}}


def client_for(token_response=None, identity_response=None):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.host == 'oauth2.googleapis.com':
            return httpx.Response(200, json=token() if token_response is None else token_response,
                                  headers={'set-cookie': 'session=SECRET-COOKIE; Domain=.googleapis.com; Path=/'})
        return httpx.Response(200, json=identity() if identity_response is None else identity_response)

    return oauth.OAuthClient(http_transport=httpx.MockTransport(handler), clock=lambda: NOW), seen


def exchange(client):
    return client.exchange_code(CLIENT, 'SECRET-CODE', REDIRECT, VERIFIER, ACCOUNT.email_address)


def test_authorization_pkce_and_narrow_scope_without_client_secret():
    url = oauth.authorization_url(CLIENT, REDIRECT, 's' * 43, VERIFIER)
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    assert parsed.scheme == 'https' and parsed.netloc == 'accounts.google.com'
    assert query['scope'] == [DRIVE_FILE_SCOPE]
    assert query['access_type'] == ['offline']
    assert query['code_challenge_method'] == ['S256']
    assert query['code_challenge'] == [base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip('=')]
    assert query['state'] == ['s' * 43]
    assert 'SECRET' not in url and VERIFIER not in url


@pytest.mark.parametrize('redirect', [
    'https://127.0.0.1:12345/callback', 'http://localhost:12345/callback',
    'http://127.0.0.1/callback', 'http://127.0.0.1:0/callback',
    'http://127.0.0.1:99999/callback', 'http://user@127.0.0.1:12345/callback',
    'http://127.0.0.1:12345/callback?x=1', 'http://127.0.0.1:12345/callback#x',
    'http://evil.example:12345/callback', 'http://127.0.0.1:12345/%2f',
    'http://127.0.0.1:12345/\ncallback', None,
])
def test_redirect_refused_before_any_exchange(redirect):
    client, seen = client_for()
    with client, pytest.raises(oauth.OAuthError, match='invalid_configuration'):
        client.exchange_code(CLIENT, 'code', redirect, VERIFIER, ACCOUNT.email_address)
    assert not seen


@pytest.mark.parametrize('state,verifier', [('short', VERIFIER), ('s' * 43, 'short'), ('s' * 43, '!' * 43)])
def test_authorization_inputs_refused(state, verifier):
    with pytest.raises(oauth.OAuthError):
        oauth.authorization_url(CLIENT, REDIRECT, state, verifier)


def test_grant_roundtrip_repr_and_no_access_token_persistence():
    client, seen = client_for()
    with client:
        grant = exchange(client)
    assert grant == GRANT
    assert oauth.StoredGrant.parse(grant.serialize()) == grant
    assert b'SECRET-ACCESS' not in grant.serialize()
    assert 'SECRET' not in repr(grant) and 'SECRET' not in repr(CLIENT)
    assert len(seen) == 2
    assert seen[0].method == 'POST' and str(seen[0].url) == oauth.TOKEN_URL
    body = parse_qs(seen[0].content.decode())
    assert body == {'client_id': [CLIENT.client_id], 'client_secret': ['SECRET-CLIENT'],
                    'grant_type': ['authorization_code'], 'code': ['SECRET-CODE'],
                    'redirect_uri': [REDIRECT], 'code_verifier': [VERIFIER]}
    assert seen[1].headers['authorization'] == 'Bearer SECRET-ACCESS'
    assert 'cookie' not in seen[1].headers
    assert seen[1].url.params['fields'] == 'user(permissionId,emailAddress)'


@pytest.mark.parametrize('mutation', [
    lambda data: data.update(schema=True), lambda data: data.update(schema=2),
    lambda data: data.update(extra='SECRET'), lambda data: data.update(issued_at='SECRET'),
    lambda data: data.update(issued_at='2026-09-26T00:00:00'),
    lambda data: data.update(refresh_expires_at='2026-09-25T00:00:00+00:00'),
    lambda data: data.update(scopes=[DRIVE_FILE_SCOPE, 'broad']),
    lambda data: data['client'].update(extra='SECRET'),
    lambda data: data['account'].update(permission_id=''),
    lambda data: data.update(refresh_token='SECRET\n'),
])
def test_grant_parser_strict_and_redacted(mutation):
    data = json.loads(GRANT.serialize())
    mutation(data)
    with pytest.raises(oauth.OAuthError) as error:
        oauth.StoredGrant.parse(json.dumps(data).encode())
    assert error.value.code == 'grant_invalid'
    assert error.value.__context__ is None
    assert 'SECRET' not in str(error.value)


@pytest.mark.parametrize('raw', [b'{}', b'[]', b'{"schema":1,"schema":1}', b'{"schema":NaN}',
                                 b'SECRET', b'\xff', b'x' * (oauth.MAX_BYTES + 1), 'not bytes'])
def test_bad_grant_bytes_refused(raw):
    with pytest.raises(oauth.OAuthError, match='grant_invalid') as error:
        oauth.StoredGrant.parse(raw)
    assert error.value.__context__ is None


def test_refresh_lease_uses_exact_pinned_client_account_and_inherited_scope():
    value = token()
    value.pop('scope')
    value.pop('refresh_token')
    client, seen = client_for(value)
    with client:
        lease = client.refresh(GRANT)
    assert lease.bearer == 'SECRET-ACCESS'
    assert lease.client_id == CLIENT.client_id and lease.scopes == frozenset({DRIVE_FILE_SCOPE})
    assert lease.expires_at == NOW + timedelta(hours=1)
    assert 'SECRET' not in repr(lease)
    assert parse_qs(seen[0].content.decode()) == {'client_id': [CLIENT.client_id],
        'client_secret': ['SECRET-CLIENT'], 'grant_type': ['refresh_token'], 'refresh_token': ['SECRET-REFRESH']}
    assert len(seen) == 2


@pytest.mark.parametrize('updates,code', [
    ({'scope': 'https://www.googleapis.com/auth/drive'}, 'credential_scope'),
    ({'scope': DRIVE_FILE_SCOPE + ' extra'}, 'credential_scope'),
    ({'scope': [DRIVE_FILE_SCOPE]}, 'credential_scope'),
    ({'scope': None}, 'credential_scope'),
    ({'scope': ''}, 'credential_scope'),
    ({'token_type': 'Basic'}, 'response_invalid'),
    ({'access_token': 'SECRET\n'}, 'response_invalid'),
    ({'expires_in': True}, 'credential_expired'),
    ({'expires_in': 30}, 'credential_expired'),
    ({'expires_in': 86401}, 'credential_expired'),
    ({'expires_in': '3600'}, 'credential_expired'),
])
def test_token_response_guard_before_account_lookup(updates, code):
    client, seen = client_for(token(**updates))
    with client, pytest.raises(oauth.OAuthError) as error:
        client.refresh(GRANT)
    assert error.value.code == code and len(seen) == 1


@pytest.mark.parametrize('missing', ['scope', 'refresh_token'])
def test_enrollment_requires_actual_granted_scope_and_refresh_token(missing):
    value = token()
    value.pop(missing)
    client, seen = client_for(value)
    with client, pytest.raises(oauth.OAuthError):
        exchange(client)
    assert len(seen) == 1


@pytest.mark.parametrize('mode', ['enroll', 'refresh'])
def test_account_email_mismatch(mode):
    client, seen = client_for(identity_response=identity(emailAddress='other@example.com'))
    with client, pytest.raises(oauth.OAuthError, match='account_mismatch'):
        exchange(client) if mode == 'enroll' else client.refresh(GRANT)
    assert len(seen) == 2


def test_refresh_permission_id_mismatch_and_rotation_refused():
    client, _ = client_for(identity_response=identity(permissionId='other-owner'))
    with client, pytest.raises(oauth.OAuthError, match='account_mismatch'):
        client.refresh(GRANT)
    client, seen = client_for(token(refresh_token='NEW-SECRET'))
    with client, pytest.raises(oauth.OAuthError, match='refresh_token_changed'):
        client.refresh(GRANT)
    assert len(seen) == 1


def test_expired_grant_refused_without_network_and_expiry_recorded_at_enrollment():
    grant = replace(GRANT, issued_at=NOW - timedelta(days=8), refresh_expires_at=NOW)
    client, seen = client_for()
    with client, pytest.raises(oauth.OAuthError, match='credential_expired'):
        client.refresh(grant)
    assert not seen
    client, _ = client_for(token(refresh_token_expires_in=604800))
    with client:
        grant = exchange(client)
    assert grant.refresh_expires_at == NOW + timedelta(days=7)


@pytest.mark.parametrize('status,body,expected', [
    (400, {'error': 'invalid_grant', 'error_description': 'SECRET'}, 'invalid_grant'),
    (401, {'error': 'invalid_client'}, 'invalid_client'),
    (403, {'error': 'access_denied'}, 'access_denied'),
    (500, {'error': 'SECRET'}, 'http_rejected'),
    (302, {}, 'http_rejected'),
])
def test_http_failure_no_retry_redirect_or_sensitive_context(status, body, expected):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(status, json=body, headers={'location': 'https://evil.example/SECRET'})
    with oauth.OAuthClient(http_transport=httpx.MockTransport(handler), clock=lambda: NOW) as client:
        with pytest.raises(oauth.OAuthError) as error:
            client.refresh(GRANT)
    assert error.value.code == expected and error.value.__context__ is None
    assert 'SECRET' not in str(error.value) and len(seen) == 1


@pytest.mark.parametrize('body,headers,expected', [
    (b'{"access_token":"SECRET","access_token":"OTHER"}', {}, 'response_invalid'),
    (b'SECRET', {}, 'response_invalid'), (b'[]', {}, 'response_invalid'),
    (b'{}', {'content-encoding': 'gzip'}, 'response_invalid'),
    (b'{}', {'content-length': str(oauth.MAX_BYTES + 1)}, 'response_too_large'),
    (b'x' * (oauth.MAX_BYTES + 1), {}, 'response_too_large'),
])
def test_response_shape_bounds(body, headers, expected):
    def handler(_):
        return httpx.Response(200, stream=httpx.ByteStream(body), headers=headers)
    with oauth.OAuthClient(http_transport=httpx.MockTransport(handler), clock=lambda: NOW) as client:
        with pytest.raises(oauth.OAuthError) as error:
            client.refresh(GRANT)
    assert error.value.code == expected and error.value.__context__ is None


def test_httpx_request_exception_not_retained():
    def handler(request):
        raise httpx.ReadTimeout('SECRET', request=request)
    with oauth.OAuthClient(http_transport=httpx.MockTransport(handler), clock=lambda: NOW) as client:
        with pytest.raises(oauth.OAuthError) as error:
            client.refresh(GRANT)
    assert error.value.code == 'request_timeout' and error.value.__context__ is None


def test_elapsed_token_lifetime_is_checked_after_identity():
    ticks = iter([NOW, NOW, NOW + timedelta(hours=1)])
    client, seen = client_for()
    client._clock = lambda: next(ticks)
    with client, pytest.raises(oauth.OAuthError, match='credential_expired'):
        client.refresh(GRANT)
    assert len(seen) == 2


def test_optional_client_secret_and_closed_client():
    client, seen = client_for()
    with client:
        grant = client.exchange_code(oauth.DesktopClient(CLIENT.client_id), 'code', REDIRECT, VERIFIER, ACCOUNT.email_address)
    assert grant.client.client_secret is None
    assert 'client_secret' not in parse_qs(seen[0].content.decode())
    with pytest.raises(oauth.OAuthError, match='closed'):
        client.refresh(grant)
