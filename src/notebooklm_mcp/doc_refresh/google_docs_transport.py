"""Explicit, native Google data transport; no credential discovery or refresh.

The caller supplies a trusted credential lease and approved account/destination.
Lease metadata declarations are not proof of OAuth issuance. Metadata checks are
point-in-time observations, not an atomic lock against subsequent sharing edits.
This module never creates a document, calls NotebookLM, or retries a request.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import time
from typing import Any, Callable
from urllib.parse import quote

import httpx

from .drive_publication import Bundle, DocsBinding, DocsSnapshot, parse_document, plan_update


DRIVE_FILE_SCOPE = 'https://www.googleapis.com/auth/drive.file'
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_PERMISSION_PAGES = 32
LEASE_MARGIN = timedelta(seconds=30)
REQUEST_SECONDS = 60
ERROR_CODES = frozenset({
    'invalid_configuration', 'credential_scope', 'credential_expired',
    'account_mismatch', 'destination_rejected', 'permissions_rejected',
    'response_invalid', 'response_too_large', 'request_timeout', 'request_failed',
    'http_rejected', 'document_mismatch', 'document_unsupported', 'planner_guard', 'closed',
})


class TransportError(ValueError):
    """A fixed, non-sensitive code; no response text, token, URL or request object."""
    def __init__(self, code: str):
        self.code = code if code in ERROR_CODES else 'invalid_configuration'
        super().__init__('Google Docs transport: ' + self.code)


def _label(value: Any) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= 1024 and value == value.strip()
            and all(ord(char) >= 32 and ord(char) != 127 for char in value))


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,256}', value) is not None


def _aware(value: Any) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True)
class CredentialLease:
    """Trusted provider assertion, held fixed for an operation; bearer never in repr."""
    bearer: str = field(repr=False)
    expires_at: datetime
    scopes: frozenset[str]
    client_id: str
    provenance: str

    def __post_init__(self):
        if (not isinstance(self.bearer, str) or not 0 < len(self.bearer) <= 8192
                or any(not 33 <= ord(char) <= 126 for char in self.bearer)
                or not _aware(self.expires_at)
                or not _label(self.client_id) or not _label(self.provenance)
                or not isinstance(self.scopes, (set, frozenset, tuple, list))
                or not all(_label(scope) for scope in self.scopes)):
            raise TransportError('invalid_configuration')
        object.__setattr__(self, 'scopes', frozenset(self.scopes))


@dataclass(frozen=True)
class AccountExpectation:
    permission_id: str
    email_address: str

    def __post_init__(self):
        if not _label(self.permission_id) or not _label(self.email_address):
            raise TransportError('invalid_configuration')


@dataclass(frozen=True)
class DestinationExpectation:
    document_id: str
    parent_id: str

    def __post_init__(self):
        if not _identifier(self.document_id) or not _identifier(self.parent_id):
            raise TransportError('invalid_configuration')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError('nonfinite value')


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


class GoogleDocsTransport:
    """One fixed lease/account/destination, owning a bounded synchronous HTTP client.

    Every read and write repeats account, file metadata and full permission checks.
    Each request requires more than 30 seconds of declared lease lifetime; no
    request refreshes the lease. HTTP inactivity limits and a 60-second elapsed
    budget checked between stream chunks bound requests (one blocking read can
    additionally consume its 20-second inactivity limit). The explicit test
    transport and clock are trusted dependency-injection seams, not CLI options.
    """
    MIME_TYPE = 'application/vnd.google-apps.document'

    def __init__(self, lease: CredentialLease, account: AccountExpectation,
                 destination: DestinationExpectation, *,
                 http_transport: httpx.BaseTransport | None = None,
                 clock: Callable[[], datetime] | None = None):
        if not isinstance(lease, CredentialLease) or not isinstance(account, AccountExpectation) \
                or not isinstance(destination, DestinationExpectation):
            raise TransportError('invalid_configuration')
        # Copy even frozen caller objects: a provider cannot swap the token between
        # identity verification and mutation by replacing its own lease fields.
        self._lease = CredentialLease(lease.bearer, lease.expires_at, lease.scopes,
                                      lease.client_id, lease.provenance)
        self._account = AccountExpectation(account.permission_id, account.email_address)
        self._destination = DestinationExpectation(destination.document_id, destination.parent_id)
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self._snapshot: DocsSnapshot | None = None
        self._closed = False
        self._check_lease()
        failure = False
        try:
            self._client = httpx.Client(
                transport=http_transport, trust_env=False, follow_redirects=False,
                timeout=httpx.Timeout(connect=10, read=20, write=20, pool=5),
                headers={'Accept': 'application/json', 'Accept-Encoding': 'identity'},
            )
        except Exception:
            failure = True
        if failure:
            raise TransportError('invalid_configuration')

    def __enter__(self) -> GoogleDocsTransport:
        self._check_lease()
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._snapshot = None
            failure = False
            try:
                self._client.close()
            except Exception:
                failure = True
            if failure:
                raise TransportError('request_failed')

    def _check_lease(self) -> None:
        if self._closed:
            raise TransportError('closed')
        if DRIVE_FILE_SCOPE not in self._lease.scopes:
            raise TransportError('credential_scope')
        valid = False
        try:
            now = self._clock()
            valid = _aware(now) and self._lease.expires_at - now > LEASE_MARGIN
        except Exception:
            pass
        if not valid:
            raise TransportError('credential_expired')

    def _request(self, method: str, url: str, *, params=None, content=None) -> dict[str, Any]:
        self._check_lease()
        failure = None
        result = None
        started = time.monotonic()
        try:
            request = self._client.build_request(
                method, url, params=params, content=content,
                headers={'Authorization': 'Bearer ' + self._lease.bearer,
                         **({'Content-Type': 'application/json'} if content is not None else {})},
            )
            # Even a server-set cookie is not an authorization input to this lane.
            request.headers.pop('cookie', None)
            response = self._client.send(request, stream=True)
            try:
                if not 200 <= response.status_code < 300:
                    raise TransportError('http_rejected')
                if response.headers.get('content-encoding', 'identity') != 'identity':
                    raise TransportError('response_invalid')
                declared = response.headers.get('content-length')
                if declared is not None:
                    if not declared.isascii() or not declared.isdecimal():
                        raise TransportError('response_invalid')
                    if int(declared) > MAX_RESPONSE_BYTES:
                        raise TransportError('response_too_large')
                data = bytearray()
                # Mock/preloaded responses may already have consumed their stream;
                # real network responses remain streamed without decompression.
                chunks = [response.content] if response.is_stream_consumed else response.iter_raw()
                for chunk in chunks:
                    if time.monotonic() - started > REQUEST_SECONDS:
                        raise TransportError('request_timeout')
                    if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise TransportError('response_too_large')
                    data.extend(chunk)
                self._check_lease()
                if time.monotonic() - started > REQUEST_SECONDS:
                    raise TransportError('request_timeout')
                result = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_object,
                                    parse_constant=_invalid_constant)
                if not isinstance(result, dict):
                    raise TransportError('response_invalid')
            finally:
                response.close()
        except TransportError as error:
            failure = error.code
        except httpx.TimeoutException:
            failure = 'request_timeout'
        except (UnicodeError, ValueError, RecursionError):
            failure = 'response_invalid'
        except Exception:
            failure = 'request_failed'
        # Raise outside except: not even __context__ retains a sensitive HTTPX
        # request/response or JSON decoder exception containing source text.
        if failure:
            raise TransportError(failure)
        return result

    def _matches_user(self, value: Any, *, permission: bool = False) -> bool:
        return (isinstance(value, dict)
                and value.get('id' if permission else 'permissionId') == self._account.permission_id
                and isinstance(value.get('emailAddress'), str)
                and value['emailAddress'].casefold() == self._account.email_address.casefold())

    def preflight(self) -> None:
        """Same-lease account, destination and complete owner-only permission checks."""
        about = self._request('GET', 'https://www.googleapis.com/drive/v3/about',
                              params={'fields': 'user(permissionId,emailAddress)'})
        if not self._matches_user(about.get('user')):
            raise TransportError('account_mismatch')
        file_url = 'https://www.googleapis.com/drive/v3/files/' + quote(self._destination.document_id, safe='')
        metadata = self._request('GET', file_url, params={
            'fields': 'id,mimeType,trashed,parents,capabilities(canEdit),owners(permissionId,emailAddress)',
        })
        owners = metadata.get('owners')
        capabilities = metadata.get('capabilities')
        if (metadata.get('id') != self._destination.document_id
                or metadata.get('mimeType') != self.MIME_TYPE
                or metadata.get('trashed') is not False
                or metadata.get('parents') != [self._destination.parent_id]
                or not isinstance(capabilities, dict) or capabilities.get('canEdit') is not True
                or not isinstance(owners, list) or len(owners) != 1
                or not self._matches_user(owners[0])):
            raise TransportError('destination_rejected')
        permissions = []
        token = None
        seen = set()
        for _ in range(MAX_PERMISSION_PAGES):
            params = {'fields': 'nextPageToken,permissions(id,type,role,emailAddress,deleted)',
                      'pageSize': '100'}
            if token is not None:
                params['pageToken'] = token
            page = self._request('GET', file_url + '/permissions', params=params)
            values = page.get('permissions')
            if not isinstance(values, list):
                raise TransportError('permissions_rejected')
            permissions.extend(values)
            if len(permissions) > 1:
                raise TransportError('permissions_rejected')
            if 'nextPageToken' not in page:
                break
            token = page['nextPageToken']
            if not _label(token) or token in seen:
                raise TransportError('permissions_rejected')
            seen.add(token)
        else:
            raise TransportError('permissions_rejected')
        if (len(permissions) != 1 or not self._matches_user(permissions[0], permission=True)
                or permissions[0].get('type') != 'user' or permissions[0].get('role') != 'owner'
                or permissions[0].get('deleted') is not False):
            raise TransportError('permissions_rejected')

    def _check_document(self, document_id: str) -> None:
        self._check_lease()
        if document_id != self._destination.document_id:
            raise TransportError('document_mismatch')

    def read(self, document_id: str) -> dict[str, Any]:
        self._snapshot = None
        self._check_document(document_id)
        self.preflight()
        raw = self._request('GET', 'https://docs.googleapis.com/v1/documents/' + quote(document_id, safe=''),
                            params={'includeTabsContent': 'true', 'suggestionsViewMode': 'SUGGESTIONS_INLINE'})
        snapshot = None
        try:
            snapshot = parse_document(raw)
        except Exception:
            pass
        if snapshot is None:
            raise TransportError('document_unsupported')
        if snapshot.document_id != document_id:
            raise TransportError('document_mismatch')
        self._snapshot = snapshot
        return raw

    def write(self, document_id: str, body: dict[str, Any]) -> None:
        self._check_document(document_id)
        snapshot, self._snapshot = self._snapshot, None
        if snapshot is None:
            raise TransportError('planner_guard')
        content = None
        try:
            # Regenerate the existing planner's exact shape, including UTF-16
            # ranges and revision. Only its plain-text replacement is supported.
            target = body['requests'][-1]['insertText']['text'] + '\n'
            expected = plan_update(
                Bundle(target, hashlib.sha256(target.encode('utf-8')).hexdigest(), 1), snapshot,
                DocsBinding(snapshot.document_id, snapshot.tab_id,
                            hashlib.sha256(snapshot.text.encode('utf-8')).hexdigest()),
            ).body
            candidate = _json_bytes(body)
            if expected is not None and candidate == _json_bytes(expected) and len(candidate) <= MAX_REQUEST_BYTES:
                content = candidate
        except Exception:
            pass
        if content is None:
            raise TransportError('planner_guard')
        self.preflight()
        raw = self._request('POST', 'https://docs.googleapis.com/v1/documents/'
                            + quote(document_id, safe='') + ':batchUpdate', content=content)
        if raw.get('documentId') != document_id:
            raise TransportError('document_mismatch')
