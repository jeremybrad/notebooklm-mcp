"""Bounded original-Markdown Drive adapter, reusing the fixed OAuth/account checks.

No creation, consent, refresh, enrollment or retry. Drive v2 provides the file
ETag; media is downloaded through v3. Writes use v2 media PATCH plus If-Match.
Documentation is not account-specific proof of conditional enforcement: callers
must supply a reference to separately reviewed live negative-precondition evidence
before writes. This is a trusted operator assertion, not parsed/verified evidence.
"""
import json
import time
from urllib.parse import quote

import httpx

from .google_docs_transport import (
    GoogleDocsTransport, TransportError, REQUEST_SECONDS, _unique_object, _invalid_constant,
)
from .individual_publication import Snapshot, StateError, MAX_CONTENT_BYTES, _etag


class GoogleMarkdownTransport(GoogleDocsTransport):
    MIME_TYPE = 'text/markdown'

    def __init__(self, *args, conditional_write_evidence=None, **kwargs):
        self._conditional_write_evidence = conditional_write_evidence
        if conditional_write_evidence is not None and (
            not isinstance(conditional_write_evidence, str) or not conditional_write_evidence.strip()
            or len(conditional_write_evidence) > 1024
            or any(ord(c) < 32 for c in conditional_write_evidence)):
            raise TransportError('invalid_configuration')
        super().__init__(*args, **kwargs)

    def _media(self, method, url, *, params=None, content=None, etag=None):
        """Complete bounded binary response; no redirect/cookie/env/retry inputs."""
        self._check_lease()
        headers = {'Authorization': 'Bearer ' + self._lease.bearer}
        if content is not None: headers['Content-Type'] = 'text/markdown; charset=utf-8'
        if etag is not None: headers['If-Match'] = etag
        failure, raw = None, None
        started = time.monotonic()
        try:
            request = self._client.build_request(method, url, params=params, content=content, headers=headers)
            request.headers.pop('cookie', None)
            response = self._client.send(request, stream=True)
            try:
                if not 200 <= response.status_code < 300: raise TransportError('http_rejected')
                if response.headers.get('content-encoding', 'identity') != 'identity': raise TransportError('response_invalid')
                declared = response.headers.get('content-length')
                if declared is not None and (not declared.isascii() or not declared.isdecimal()
                                             or int(declared) > MAX_CONTENT_BYTES):
                    raise TransportError('response_too_large')
                pieces = []; length = 0
                chunks = [response.content] if response.is_stream_consumed else response.iter_raw()
                for chunk in chunks:
                    length += len(chunk)
                    if length > MAX_CONTENT_BYTES: raise TransportError('response_too_large')
                    if time.monotonic() - started > REQUEST_SECONDS: raise TransportError('request_timeout')
                    pieces.append(chunk)
                if time.monotonic() - started > REQUEST_SECONDS: raise TransportError('request_timeout')
                self._check_lease()
                raw = b''.join(pieces)
                if declared is not None and int(declared) != len(raw): raise TransportError('response_invalid')
            finally: response.close()
        except TransportError as error: failure = error.code
        except httpx.TimeoutException: failure = 'request_timeout'
        except Exception: failure = 'request_failed'
        if failure: raise TransportError(failure) from None
        return raw

    def _file_etag(self, file_id):
        metadata = self._request('GET', 'https://www.googleapis.com/drive/v2/files/' + quote(file_id, safe=''),
                                 params={'fields': 'id,etag'})
        try:
            if metadata.get('id') != file_id: raise StateError('identity')
            _etag(metadata.get('etag'))
        except StateError: raise TransportError('response_invalid') from None
        return metadata['etag']

    def read(self, file_id):
        self._check_document(file_id)
        self.preflight()
        before = self._file_etag(file_id)
        raw = self._media('GET', 'https://www.googleapis.com/drive/v3/files/' + quote(file_id, safe=''),
                          params={'alt': 'media'})
        after = self._file_etag(file_id)
        if before != after: raise TransportError('planner_guard')
        return Snapshot(file_id, after, raw)

    def write(self, file_id, content, etag):
        self._check_document(file_id)
        if self._conditional_write_evidence is None: raise TransportError('planner_guard')
        try:
            _etag(etag)
            if not isinstance(content, bytes) or not content.strip() or len(content) > MAX_CONTENT_BYTES:
                raise StateError('unsupported original')
            content.decode('utf-8')
        except (StateError, UnicodeError): raise TransportError('planner_guard') from None
        self.preflight()
        if self._file_etag(file_id) != etag: raise TransportError('planner_guard')
        raw = self._media('PATCH', 'https://www.googleapis.com/upload/drive/v2/files/' + quote(file_id, safe=''),
                          params={'uploadType': 'media', 'fields': 'id'}, content=content, etag=etag)
        try:
            value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
            if not isinstance(value, dict) or value.get('id') != file_id: raise ValueError('identity')
        except (ValueError, UnicodeError): raise TransportError('response_invalid') from None
