"""Explicit Google data OAuth; no credential discovery, browser or store access.

Only the caller's registered desktop client and approved grant are accepted.
HTTP response bodies, tokens and underlying exceptions never enter public errors.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import time
from typing import Callable
from urllib.parse import urlencode, urlsplit

import httpx

from .google_docs_transport import AccountExpectation, CredentialLease, DRIVE_FILE_SCOPE

TOKEN_URL = 'https://oauth2.googleapis.com/token'
ABOUT_URL = 'https://www.googleapis.com/drive/v3/about'
AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
MAX_BYTES = 64 * 1024
REQUEST_SECONDS = 60
ERROR_CODES = frozenset({
    'invalid_configuration', 'grant_invalid', 'credential_scope', 'credential_expired',
    'account_mismatch', 'response_invalid', 'response_too_large', 'request_timeout',
    'request_failed', 'http_rejected', 'invalid_grant', 'invalid_client', 'access_denied',
    'refresh_token_changed', 'closed',
})


class OAuthError(ValueError):
    def __init__(self, code: str):
        self.code = code if code in ERROR_CODES else 'invalid_configuration'
        super().__init__('Google data OAuth: ' + self.code)


def _secret(value, maximum=8192):
    return (isinstance(value, str) and 0 < len(value) <= maximum
            and all(33 <= ord(char) <= 126 for char in value))


def _aware(value):
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _email(value):
    return (isinstance(value, str) and len(value) <= 254
            and re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+', value) is not None)


def _account(value):
    return (isinstance(value, AccountExpectation) and _email(value.email_address)
            and isinstance(value.permission_id, str)
            and re.fullmatch(r'[A-Za-z0-9_-]{1,256}', value.permission_id) is not None)


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate')
        result[key] = value
    return result


def _constant(_):
    raise ValueError('nonfinite')


def _decode(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('size')
    result = json.loads(raw.decode('utf-8'), object_pairs_hook=_strict_object,
                        parse_constant=_constant)
    if not isinstance(result, dict):
        raise ValueError('shape')
    return result


@dataclass(frozen=True)
class DesktopClient:
    client_id: str
    client_secret: str | None = field(default=None, repr=False)

    def __post_init__(self):
        if (not isinstance(self.client_id, str) or len(self.client_id) > 256
                or re.fullmatch(r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', self.client_id) is None
                or (self.client_secret is not None and not _secret(self.client_secret))):
            raise OAuthError('invalid_configuration')


@dataclass(frozen=True)
class StoredGrant:
    client: DesktopClient
    refresh_token: str = field(repr=False)
    account: AccountExpectation
    issued_at: datetime
    refresh_expires_at: datetime | None = None
    schema: int = 1
    scopes: frozenset[str] = field(default_factory=lambda: frozenset({DRIVE_FILE_SCOPE}))

    def __post_init__(self):
        if (not isinstance(self.client, DesktopClient) or not _secret(self.refresh_token)
                or not _account(self.account) or not _aware(self.issued_at)
                or type(self.schema) is not int or self.schema != 1
                or not isinstance(self.scopes, (frozenset, set, tuple, list))
                or self.scopes != frozenset({DRIVE_FILE_SCOPE})
                or (self.refresh_expires_at is not None and
                    (not _aware(self.refresh_expires_at) or self.refresh_expires_at <= self.issued_at))):
            raise OAuthError('grant_invalid')
        object.__setattr__(self, 'scopes', frozenset(self.scopes))

    def serialize(self) -> bytes:
        """Secret bytes for the explicitly selected secure store, never a log value."""
        return json.dumps({
            'schema': self.schema,
            'client': {'client_id': self.client.client_id, 'client_secret': self.client.client_secret},
            'refresh_token': self.refresh_token,
            'account': {'permission_id': self.account.permission_id, 'email_address': self.account.email_address},
            'issued_at': self.issued_at.isoformat(),
            'refresh_expires_at': self.refresh_expires_at.isoformat() if self.refresh_expires_at else None,
            'scopes': sorted(self.scopes),
        }, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

    @classmethod
    def parse(cls, raw: bytes) -> StoredGrant:
        grant = None
        try:
            obj = _decode(raw)
            if set(obj) != {'schema', 'client', 'refresh_token', 'account', 'issued_at', 'refresh_expires_at', 'scopes'}:
                raise ValueError('shape')
            if set(obj['client']) != {'client_id', 'client_secret'} or set(obj['account']) != {'permission_id', 'email_address'}:
                raise ValueError('shape')
            if obj['scopes'] != [DRIVE_FILE_SCOPE]:
                raise ValueError('scope')
            grant = cls(DesktopClient(**obj['client']), obj['refresh_token'],
                        AccountExpectation(**obj['account']), datetime.fromisoformat(obj['issued_at']),
                        datetime.fromisoformat(obj['refresh_expires_at']) if obj['refresh_expires_at'] is not None else None,
                        schema=obj['schema'], scopes=frozenset(obj['scopes']))
        except Exception:
            pass
        if grant is None:
            raise OAuthError('grant_invalid')
        return grant


def _redirect(value):
    valid = False
    try:
        parts = urlsplit(value)
        valid = (isinstance(value, str) and len(value) <= 1024 and parts.scheme == 'http'
                 and parts.hostname in {'127.0.0.1', '::1'} and parts.port is not None
                 and 1 <= parts.port <= 65535 and parts.username is None and parts.password is None
                 and not parts.query and not parts.fragment
                 and re.fullmatch(r'/[A-Za-z0-9/_-]*', parts.path) is not None
                 and '%' not in value and '\\' not in value
                 and all(33 <= ord(char) <= 126 for char in value))
    except Exception:
        pass
    if not valid:
        raise OAuthError('invalid_configuration')


def _verifier(value):
    if not isinstance(value, str) or re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', value) is None:
        raise OAuthError('invalid_configuration')


def authorization_url(client: DesktopClient, redirect_uri: str, state: str, verifier: str) -> str:
    if not isinstance(client, DesktopClient) or not isinstance(state, str) or re.fullmatch(r'[A-Za-z0-9_-]{32,128}', state) is None:
        raise OAuthError('invalid_configuration')
    _redirect(redirect_uri)
    _verifier(verifier)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).decode('ascii').rstrip('=')
    return AUTHORIZE_URL + '?' + urlencode({
        'client_id': client.client_id, 'redirect_uri': redirect_uri, 'response_type': 'code',
        'scope': DRIVE_FILE_SCOPE, 'state': state, 'code_challenge': challenge,
        'code_challenge_method': 'S256', 'access_type': 'offline', 'prompt': 'consent',
    })


class OAuthClient:
    """No retry, cookie auth, store discovery, user interaction or grant repair."""
    def __init__(self, *, http_transport: httpx.BaseTransport | None = None,
                 clock: Callable[[], datetime] | None = None):
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._closed = False
        failed = False
        try:
            self._http = httpx.Client(transport=http_transport, trust_env=False, follow_redirects=False,
                                     timeout=httpx.Timeout(connect=10, read=20, write=20, pool=5),
                                     headers={'Accept': 'application/json', 'Accept-Encoding': 'identity'})
        except Exception:
            failed = True
        if failed:
            raise OAuthError('invalid_configuration')

    def __enter__(self):
        if self._closed:
            raise OAuthError('closed')
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self._closed:
            return
        self._closed = True
        failed = False
        try:
            self._http.close()
        except Exception:
            failed = True
        if failed:
            raise OAuthError('request_failed')

    def _now(self):
        now = None
        try:
            value = self._clock()
            if _aware(value):
                now = value
        except Exception:
            pass
        if now is None:
            raise OAuthError('invalid_configuration')
        return now

    def _request(self, *, form=None, bearer=None):
        if self._closed:
            raise OAuthError('closed')
        result, failure = None, None
        started = time.monotonic()
        try:
            if form is not None:
                request = self._http.build_request('POST', TOKEN_URL, data=form)
            else:
                request = self._http.build_request('GET', ABOUT_URL,
                    params={'fields': 'user(permissionId,emailAddress)'}, headers={'Authorization': 'Bearer ' + bearer})
            request.headers.pop('cookie', None)
            response = self._http.send(request, stream=True)
            try:
                if response.headers.get('content-encoding', 'identity') != 'identity':
                    raise OAuthError('response_invalid')
                length = response.headers.get('content-length')
                if length is not None and (not length.isascii() or not length.isdecimal()):
                    raise OAuthError('response_invalid')
                if length is not None and int(length) > MAX_BYTES:
                    raise OAuthError('response_too_large')
                data = bytearray()
                chunks = [response.content] if response.is_stream_consumed else response.iter_raw()
                for chunk in chunks:
                    if time.monotonic() - started > REQUEST_SECONDS:
                        raise OAuthError('request_timeout')
                    if len(data) + len(chunk) > MAX_BYTES:
                        raise OAuthError('response_too_large')
                    data.extend(chunk)
                if time.monotonic() - started > REQUEST_SECONDS:
                    raise OAuthError('request_timeout')
                result = _decode(bytes(data))
                if response.status_code != 200:
                    code = result.get('error')
                    raise OAuthError(code if form is not None and code in {'invalid_grant', 'invalid_client', 'access_denied'} else 'http_rejected')
            finally:
                response.close()
        except OAuthError as error:
            failure = error.code
        except httpx.TimeoutException:
            failure = 'request_timeout'
        except (ValueError, UnicodeError, RecursionError):
            failure = 'response_invalid'
        except Exception:
            failure = 'request_failed'
        if failure:
            raise OAuthError(failure)
        return result

    def _tokens(self, result, started, *, enrollment):
        if result.get('token_type') != 'Bearer' or not _secret(result.get('access_token')):
            raise OAuthError('response_invalid')
        scope = result.get('scope')
        if 'scope' not in result and not enrollment:
            scope = DRIVE_FILE_SCOPE
        if not isinstance(scope, str) or scope.split() != [DRIVE_FILE_SCOPE]:
            raise OAuthError('credential_scope')
        seconds = result.get('expires_in')
        if type(seconds) is not int or not 30 < seconds <= 86400:
            raise OAuthError('credential_expired')
        expires = started + timedelta(seconds=seconds)
        if expires - self._now() <= timedelta(seconds=30):
            raise OAuthError('credential_expired')
        return result['access_token'], expires

    def _identity(self, bearer, expected_email):
        result = self._request(bearer=bearer)
        user = result.get('user')
        if not isinstance(user, dict) or user.get('emailAddress') != expected_email:
            raise OAuthError('account_mismatch')
        permission = user.get('permissionId')
        if not isinstance(permission, str) or re.fullmatch(r'[A-Za-z0-9_-]{1,256}', permission) is None:
            raise OAuthError('account_mismatch')
        return AccountExpectation(permission, expected_email)

    @staticmethod
    def _form(client):
        if not isinstance(client, DesktopClient):
            raise OAuthError('invalid_configuration')
        form = {'client_id': client.client_id}
        if client.client_secret is not None:
            form['client_secret'] = client.client_secret
        return form

    def exchange_code(self, client: DesktopClient, code: str, redirect_uri: str,
                      verifier: str, expected_email: str) -> StoredGrant:
        _redirect(redirect_uri)
        _verifier(verifier)
        if not _secret(code) or not _email(expected_email):
            raise OAuthError('invalid_configuration')
        form = self._form(client)
        form.update(grant_type='authorization_code', code=code, redirect_uri=redirect_uri, code_verifier=verifier)
        started = self._now()
        result = self._request(form=form)
        bearer, expires = self._tokens(result, started, enrollment=True)
        if not _secret(result.get('refresh_token')):
            raise OAuthError('response_invalid')
        refresh_expiry = None
        if 'refresh_token_expires_in' in result:
            seconds = result['refresh_token_expires_in']
            if type(seconds) is not int or not 30 < seconds <= 10 * 366 * 86400:
                raise OAuthError('response_invalid')
            refresh_expiry = started + timedelta(seconds=seconds)
        account = self._identity(bearer, expected_email)
        if expires - self._now() <= timedelta(seconds=30):
            raise OAuthError('credential_expired')
        return StoredGrant(client, result['refresh_token'], account, started, refresh_expiry)

    def refresh(self, grant: StoredGrant) -> CredentialLease:
        if not isinstance(grant, StoredGrant):
            raise OAuthError('grant_invalid')
        # A strict roundtrip fixes the complete caller input for this operation.
        grant = StoredGrant.parse(grant.serialize())
        started = self._now()
        if grant.issued_at > started or (grant.refresh_expires_at is not None
                and grant.refresh_expires_at - started <= timedelta(seconds=30)):
            raise OAuthError('credential_expired')
        form = self._form(grant.client)
        form.update(grant_type='refresh_token', refresh_token=grant.refresh_token)
        result = self._request(form=form)
        bearer, expires = self._tokens(result, started, enrollment=False)
        if 'refresh_token' in result and result['refresh_token'] != grant.refresh_token:
            raise OAuthError('refresh_token_changed')
        account = self._identity(bearer, grant.account.email_address)
        if account != grant.account:
            raise OAuthError('account_mismatch')
        if expires - self._now() <= timedelta(seconds=30):
            raise OAuthError('credential_expired')
        return CredentialLease(bearer, expires, grant.scopes, grant.client.client_id, 'c021-google-data-oauth-v1')
