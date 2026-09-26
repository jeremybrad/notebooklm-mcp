"""Fictional credentials and mocked Google HTTP only; no credential stores or network."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import hashlib
import json
import traceback

import httpx
import pytest

from notebooklm_mcp.doc_refresh.drive_publication import (
    Bundle, DocsBinding, parse_document, plan_update,
)
from notebooklm_mcp.doc_refresh.google_docs_transport import (
    AccountExpectation, CredentialLease, DestinationExpectation,
    GoogleDocsTransport, TransportError,
)


NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)
TOKEN = 'fictional-sensitive-bearer'
SCOPE = 'https://www.googleapis.com/auth/drive.file'
ACCOUNT = AccountExpectation('fictional-permission', 'synthetic@example.invalid')
DESTINATION = DestinationExpectation('fictional-doc', 'fictional-parent')


def lease(**changes):
    values = dict(bearer=TOKEN, expires_at=NOW + timedelta(hours=1),
                  scopes=frozenset({SCOPE}), client_id='fictional-client',
                  provenance='synthetic-test-provider')
    values.update(changes)
    return CredentialLease(**values)


def document(text='Old 🐝\n', revision='revision-1', document_id='fictional-doc'):
    end = 1 + len(text.encode('utf-16-le')) // 2
    return {'documentId': document_id, 'revisionId': revision,
            'suggestionsViewMode': 'SUGGESTIONS_INLINE', 'preservedUnknown': {'value': 42},
            'tabs': [{'tabProperties': {'tabId': 't.0'}, 'documentTab': {'body': {'content': [
                {'endIndex': 1, 'sectionBreak': {}},
                {'startIndex': 1, 'endIndex': end, 'paragraph': {'elements': [
                    {'startIndex': 1, 'endIndex': end, 'textRun': {'content': text}},
                ]}},
            ]}}}]}


def plan(raw):
    text = 'New synthetic source 🐝\n'
    digest = hashlib.sha256(text.encode()).hexdigest()
    remote = parse_document(raw)
    return plan_update(Bundle(text, digest, 1), remote,
                       DocsBinding(remote.document_id, remote.tab_id,
                                   hashlib.sha256(remote.text.encode()).hexdigest())).body


class Google:
    def __init__(self):
        self.requests = []
        self.about = {'user': {'permissionId': ACCOUNT.permission_id,
                               'emailAddress': ACCOUNT.email_address}}
        self.metadata = {'id': DESTINATION.document_id,
                         'mimeType': 'application/vnd.google-apps.document',
                         'trashed': False, 'parents': [DESTINATION.parent_id],
                         'capabilities': {'canEdit': True},
                         'owners': [dict(self.about['user'])]}
        self.permissions = [{'permissions': [{
            'id': ACCOUNT.permission_id, 'type': 'user', 'role': 'owner',
            'emailAddress': ACCOUNT.email_address, 'deleted': False,
        }]}]
        self.raw = document()
        self.override = None

    def __call__(self, request):
        self.requests.append(request)
        if self.override:
            response = self.override(request)
            if response is not None:
                return response
        path = request.url.path
        if path == '/drive/v3/about':
            payload = self.about
        elif path == '/drive/v3/files/fictional-doc':
            payload = self.metadata
        elif path == '/drive/v3/files/fictional-doc/permissions':
            page = int(request.url.params.get('pageToken', '0'))
            payload = self.permissions[page]
        elif path == '/v1/documents/fictional-doc' and request.method == 'GET':
            payload = self.raw
        elif path == '/v1/documents/fictional-doc:batchUpdate' and request.method == 'POST':
            payload = {'documentId': DESTINATION.document_id, 'replies': []}
        else:
            pytest.fail('Unexpected endpoint')
        return httpx.Response(200, json=payload)

    def adapter(self, **kwargs):
        return GoogleDocsTransport(lease(), ACCOUNT, DESTINATION,
                                   http_transport=httpx.MockTransport(self),
                                   clock=lambda: NOW, **kwargs)


def test_complete_native_read_and_revision_guarded_write_are_preserved():
    google = Google()
    with google.adapter() as adapter:
        raw = adapter.read(DESTINATION.document_id)
        assert raw == google.raw
        body = plan(raw)
        adapter.write(DESTINATION.document_id, body)
    docs = [r for r in google.requests if r.url.host == 'docs.googleapis.com']
    assert len(docs) == 2
    assert dict(docs[0].url.params) == {
        'includeTabsContent': 'true', 'suggestionsViewMode': 'SUGGESTIONS_INLINE',
    }
    assert json.loads(docs[1].content) == body
    assert body['requests'][0]['deleteContentRange']['range']['endIndex'] == 7
    assert [r.url.path for r in google.requests].count('/drive/v3/about') == 2
    assert all(r.headers['authorization'] == 'Bearer ' + TOKEN for r in google.requests)


def test_empty_document_uses_planner_insert_only_body():
    google = Google()
    google.raw = document('\n')
    with google.adapter() as adapter:
        adapter.write(DESTINATION.document_id, plan(adapter.read(DESTINATION.document_id)))
    body = json.loads(google.requests[-1].content)
    assert len(body['requests']) == 1


def test_lease_is_immutable_nonprinting_and_freezes_scope_collection():
    scopes = {SCOPE}
    credential = lease(scopes=scopes)
    scopes.clear()
    assert credential.scopes == frozenset({SCOPE})
    assert TOKEN not in repr(credential)
    with pytest.raises(FrozenInstanceError):
        credential.bearer = 'different'


@pytest.mark.parametrize('changes', [
    {'expires_at': NOW.replace(tzinfo=None)}, {'expires_at': 'not-a-date'},
    {'bearer': ''}, {'bearer': 'header\ninjection'}, {'scopes': 'not-a-set'},
    {'client_id': ''}, {'provenance': ''},
])
def test_invalid_lease_contract_is_refused(changes):
    with pytest.raises(TransportError):
        lease(**changes)


@pytest.mark.parametrize('changes', [
    {'scopes': frozenset()}, {'scopes': frozenset({'https://www.googleapis.com/auth/drive'})},
    {'expires_at': NOW}, {'expires_at': NOW + timedelta(seconds=30)},
])
def test_insufficient_scope_or_expiry_refuses_before_request(changes):
    google = Google()
    with pytest.raises(TransportError):
        with GoogleDocsTransport(lease(**changes), ACCOUNT, DESTINATION,
                                 http_transport=httpx.MockTransport(google), clock=lambda: NOW) as adapter:
            adapter.preflight()
    assert not google.requests


@pytest.mark.parametrize('part,key,value', [
    ('about', 'user', {}),
    ('about', 'user', {'permissionId': 'other', 'emailAddress': ACCOUNT.email_address}),
    ('about', 'user', {'permissionId': ACCOUNT.permission_id, 'emailAddress': 'other@example.invalid'}),
    ('metadata', 'id', 'other'), ('metadata', 'mimeType', 'text/plain'),
    ('metadata', 'trashed', True), ('metadata', 'capabilities', {'canEdit': False}),
    ('metadata', 'parents', []), ('metadata', 'parents', ['unapproved']),
    ('metadata', 'parents', [DESTINATION.parent_id, 'other']),
    ('metadata', 'owners', []),
    ('metadata', 'owners', [{'permissionId': 'other', 'emailAddress': ACCOUNT.email_address}]),
])
def test_account_and_destination_refusals_precede_docs_access(part, key, value):
    google = Google()
    getattr(google, part)[key] = value
    with google.adapter() as adapter, pytest.raises(TransportError):
        adapter.read(DESTINATION.document_id)
    assert all(r.url.host == 'www.googleapis.com' for r in google.requests)


@pytest.mark.parametrize('field', ['id', 'mimeType', 'trashed', 'parents', 'capabilities', 'owners'])
def test_missing_file_metadata_fails_closed(field):
    google = Google()
    google.metadata.pop(field)
    with google.adapter() as adapter, pytest.raises(TransportError):
        adapter.preflight()


def test_permissions_require_complete_pagination():
    google = Google()
    owner = google.permissions[0]
    google.permissions = [{'permissions': [], 'nextPageToken': '1'}, owner]
    with google.adapter() as adapter:
        adapter.preflight()
    pages = [r for r in google.requests if r.url.path.endswith('/permissions')]
    assert len(pages) == 2
    assert pages[1].url.params['pageToken'] == '1'


@pytest.mark.parametrize('permissions', [
    [{}], [{'permissions': []}], [{'permissions': {}, 'nextPageToken': '1'}],
    [{'permissions': [], 'nextPageToken': 123}],
    [{'permissions': [], 'nextPageToken': '0'}],
    [{'permissions': [{'type': 'anyone', 'role': 'reader'}]}],
])
def test_malformed_shared_or_cyclic_permission_lists_fail_closed(permissions):
    google = Google()
    google.permissions = permissions
    with google.adapter() as adapter, pytest.raises(TransportError):
        adapter.preflight()
    assert len(google.requests) < 10


@pytest.mark.parametrize('field,value', [
    ('id', 'other'), ('type', 'group'), ('role', 'writer'),
    ('emailAddress', 'other@example.invalid'), ('deleted', True), ('deleted', None),
])
def test_only_exact_active_owner_permission_is_accepted(field, value):
    google = Google()
    google.permissions[0]['permissions'][0][field] = value
    with google.adapter() as adapter, pytest.raises(TransportError):
        adapter.preflight()


def test_later_permission_page_cannot_hide_public_sharing():
    google = Google()
    google.permissions[0]['nextPageToken'] = '1'
    google.permissions.append({'permissions': [{'type': 'anyone', 'role': 'reader'}]})
    with google.adapter() as adapter, pytest.raises(TransportError):
        adapter.preflight()


def test_expiry_is_rechecked_between_requests():
    google = Google()
    now = [NOW]
    def advance(request):
        now[0] += timedelta(hours=2)
    google.override = advance
    with GoogleDocsTransport(lease(), ACCOUNT, DESTINATION,
                             http_transport=httpx.MockTransport(google), clock=lambda: now[0]) as adapter:
        with pytest.raises(TransportError):
            adapter.preflight()
    assert len(google.requests) == 1


def test_lease_copy_and_account_recheck_prevent_identity_switch_before_write():
    google = Google()
    credential = lease()
    with GoogleDocsTransport(credential, ACCOUNT, DESTINATION,
                             http_transport=httpx.MockTransport(google), clock=lambda: NOW) as adapter:
        body = plan(adapter.read(DESTINATION.document_id))
        # Even a caller circumventing the public frozen-dataclass contract cannot
        # replace the transport's copied bearer after its account check.
        object.__setattr__(credential, 'bearer', 'different-bearer')
        google.about['user']['permissionId'] = 'different-account'
        with pytest.raises(TransportError):
            adapter.write(DESTINATION.document_id, body)
    assert all(r.headers['authorization'] == 'Bearer ' + TOKEN for r in google.requests)
    assert all(r.method != 'POST' for r in google.requests)


@pytest.mark.parametrize('status', [301, 302, 307, 308, 400, 401, 403, 409, 429, 500, 503])
def test_http_errors_and_redirects_are_redacted_and_never_retried(status):
    google = Google()
    google.override = lambda r: httpx.Response(status, text=TOKEN,
                                                headers={'Location': 'https://example.invalid/secret'})
    with google.adapter() as adapter, pytest.raises(TransportError) as caught:
        adapter.read(DESTINATION.document_id)
    assert len(google.requests) == 1
    assert TOKEN not in ''.join(traceback.format_exception(caught.value))
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_lost_post_response_is_one_attempt_and_has_no_sensitive_exception_chain():
    google = Google()
    def failure(request):
        if request.method == 'POST':
            raise httpx.ReadTimeout(TOKEN + ' New synthetic source', request=request)
    google.override = failure
    with google.adapter() as adapter:
        body = plan(adapter.read(DESTINATION.document_id))
        with pytest.raises(TransportError) as caught:
            adapter.write(DESTINATION.document_id, body)
        # Same instance cannot replay after an uncertain response.
        with pytest.raises(TransportError):
            adapter.write(DESTINATION.document_id, body)
    assert sum(r.method == 'POST' for r in google.requests) == 1
    rendered = ''.join(traceback.format_exception(caught.value))
    assert TOKEN not in rendered and 'New synthetic source' not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None


@pytest.mark.parametrize('content', [b'not json', b'[]', b'null', b'{"x":NaN}', b'{"x":1,"x":2}'])
def test_malformed_native_json_is_refused(content):
    google = Google()
    google.override = lambda r: httpx.Response(200, content=content)
    with google.adapter() as adapter, pytest.raises(TransportError) as caught:
        adapter.preflight()
    assert caught.value.__context__ is None


def test_oversized_stream_is_stopped_and_closed():
    google = Google()
    class Stream(httpx.SyncByteStream):
        closed = False
        reads = 0
        def __iter__(self):
            for _ in range(100):
                self.reads += 1
                yield b'x' * (1024 * 1024)
        def close(self):
            self.closed = True
    stream = Stream()
    google.override = lambda r: httpx.Response(200, stream=stream)
    with google.adapter() as adapter, pytest.raises(TransportError):
        adapter.preflight()
    assert stream.closed and stream.reads < 100


@pytest.mark.parametrize('mutation', [
    lambda b: b.pop('writeControl'),
    lambda b: b['writeControl'].update(requiredRevisionId='wrong'),
    lambda b: b['writeControl'].update(targetRevisionId='revision-1'),
    lambda b: b['requests'].append({'deleteNamedRange': {'name': 'unapproved'}}),
    lambda b: b['requests'][0]['deleteContentRange']['range'].update(tabId='wrong'),
    lambda b: b['requests'][0]['deleteContentRange']['range'].update(startIndex=True),
    lambda b: b['requests'][-1]['insertText']['location'].update(index=2),
    lambda b: b.update(unapproved='extra'),
])
def test_nonplanner_or_wrong_revision_body_refuses_before_post(mutation):
    google = Google()
    with google.adapter() as adapter:
        body = plan(adapter.read(DESTINATION.document_id))
        mutation(body)
        with pytest.raises(TransportError):
            adapter.write(DESTINATION.document_id, body)
    assert all(r.method != 'POST' for r in google.requests)


def test_write_requires_prior_read_and_bound_destination():
    google = Google()
    with google.adapter() as adapter:
        for doc_id in ['other', DESTINATION.document_id]:
            with pytest.raises(TransportError):
                adapter.write(doc_id, plan(google.raw))
        with pytest.raises(TransportError):
            adapter.read('other')
    assert not google.requests


def test_wrong_native_identity_is_refused_and_cannot_seed_a_write():
    google = Google()
    google.raw['documentId'] = 'other'
    with google.adapter() as adapter:
        with pytest.raises(TransportError):
            adapter.read(DESTINATION.document_id)
        with pytest.raises(TransportError):
            adapter.write(DESTINATION.document_id, plan(document()))
    assert all(r.method != 'POST' for r in google.requests)


def test_client_ignores_ambient_proxy_and_authorization(monkeypatch):
    monkeypatch.setenv('HTTPS_PROXY', 'https://unapproved.invalid')
    monkeypatch.setenv('GOOGLE_API_KEY', TOKEN + '-ambient')
    google = Google()
    original = httpx.Client
    observed = {}
    def client(*args, **kwargs):
        observed.update(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(httpx, 'Client', client)
    with google.adapter() as adapter:
        adapter.preflight()
    assert observed['trust_env'] is False
    assert observed['follow_redirects'] is False
    assert isinstance(observed['timeout'], httpx.Timeout)
    assert observed['timeout'].connect is not None


def test_closed_transport_refuses_and_context_manager_closes():
    google = Google()
    adapter = google.adapter()
    with adapter:
        adapter.preflight()
    with pytest.raises(TransportError):
        adapter.read(DESTINATION.document_id)


@pytest.mark.parametrize('field,value', [
    ('content-length', '9000000'), ('content-length', 'ambiguous'),
    ('content-encoding', 'gzip'),
])
def test_oversize_or_ambiguous_body_headers_refuse_without_reading(field, value):
    google = Google()
    google.override = lambda r: httpx.Response(200, headers={field: value}, stream=httpx.ByteStream(b'{}'))
    with google.adapter() as adapter, pytest.raises(TransportError) as caught:
        adapter.preflight()
    assert caught.value.code in {'response_too_large', 'response_invalid'}


@pytest.mark.parametrize('failure', [httpx.ConnectError, httpx.ReadTimeout, RuntimeError])
def test_transport_failures_do_not_retain_sensitive_cause_or_context(failure):
    google = Google()
    def reject(request):
        if failure is RuntimeError:
            raise failure(TOKEN)
        raise failure(TOKEN, request=request)
    google.override = reject
    with google.adapter() as adapter, pytest.raises(TransportError) as caught:
        adapter.preflight()
    assert TOKEN not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert len(google.requests) == 1


def test_stream_elapsed_budget_refuses_slow_drip(monkeypatch):
    import notebooklm_mcp.doc_refresh.google_docs_transport as transport_module
    ticks = iter([0, 61])
    monkeypatch.setattr(transport_module.time, 'monotonic', lambda: next(ticks))
    google = Google()
    with google.adapter() as adapter, pytest.raises(TransportError) as caught:
        adapter.preflight()
    assert caught.value.code == 'request_timeout'


def test_endless_distinct_permission_pages_hit_a_finite_bound():
    google = Google()
    google.permissions = [{'permissions': [], 'nextPageToken': str(i + 1)} for i in range(40)]
    with google.adapter() as adapter, pytest.raises(TransportError) as caught:
        adapter.preflight()
    assert caught.value.code == 'permissions_rejected'
    assert sum(r.url.path.endswith('/permissions') for r in google.requests) == 32


@pytest.mark.parametrize('mutation', [
    lambda raw: raw.pop('suggestionsViewMode'),
    lambda raw: raw['tabs'].append(raw['tabs'][0]),
    lambda raw: raw.update(suggestedChange={'sensitive': TOKEN}),
])
def test_complete_response_is_parsed_without_hiding_unsupported_content(mutation):
    google = Google()
    mutation(google.raw)
    with google.adapter() as adapter, pytest.raises(TransportError) as caught:
        adapter.read(DESTINATION.document_id)
    assert caught.value.code == 'document_unsupported'
    assert caught.value.__context__ is None


def test_permission_change_after_read_stops_the_write():
    google = Google()
    with google.adapter() as adapter:
        body = plan(adapter.read(DESTINATION.document_id))
        google.permissions[0]['permissions'].append({'type': 'anyone', 'role': 'reader'})
        with pytest.raises(TransportError):
            adapter.write(DESTINATION.document_id, body)
    assert all(r.method != 'POST' for r in google.requests)


def test_success_status_with_wrong_write_document_id_remains_uncertain():
    google = Google()
    google.override = lambda r: httpx.Response(200, json={'documentId': 'other'}) if r.method == 'POST' else None
    with google.adapter() as adapter:
        body = plan(adapter.read(DESTINATION.document_id))
        with pytest.raises(TransportError) as caught:
            adapter.write(DESTINATION.document_id, body)
    assert caught.value.code == 'document_mismatch'
    assert sum(r.method == 'POST' for r in google.requests) == 1


@pytest.mark.parametrize('bad_id', ['https://example.invalid/doc', '../other', 'a/b', 'a?query', 'a#fragment', ''])
def test_destination_ids_cannot_change_endpoint_origin_or_path(bad_id):
    with pytest.raises(TransportError):
        DestinationExpectation(bad_id, DESTINATION.parent_id)


def test_set_cookie_never_becomes_an_authorization_input():
    google = Google()
    def cookie(request):
        if request.url.path == '/drive/v3/about':
            return httpx.Response(200, json=google.about,
                                  headers={'Set-Cookie': 'unapproved=secret; Domain=.googleapis.com; Path=/'})
    google.override = cookie
    with google.adapter() as adapter:
        adapter.read(DESTINATION.document_id)
    assert all('cookie' not in request.headers for request in google.requests)
