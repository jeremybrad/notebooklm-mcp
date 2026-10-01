from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest

from notebooklm_mcp.doc_refresh.google_docs_transport import (
    AccountExpectation, CredentialLease, DestinationExpectation, DRIVE_FILE_SCOPE, TransportError,
)
from notebooklm_mcp.doc_refresh.google_markdown_transport import GoogleMarkdownTransport


class API:
    def __init__(self): self.content = b'# Original\r\n'; self.etag = '"one"'; self.writes = []; self.changed = False; self.oversized = False
    def handle(self, request):
        assert request.headers.get('cookie') is None
        path = request.url.path
        if path.endswith('/about'): return httpx.Response(200, json={'user': {'permissionId': 'owner', 'emailAddress': 'fixture@example.invalid'}})
        if path.endswith('/permissions'): return httpx.Response(200, json={'permissions': [{'id': 'owner', 'type': 'user', 'role': 'owner', 'emailAddress': 'fixture@example.invalid', 'deleted': False}]})
        if path == '/drive/v2/files/file_1': return httpx.Response(200, json={'id': 'file_1', 'etag': self.etag})
        if request.method == 'PATCH':
            self.writes.append(request)
            if request.headers['if-match'] != self.etag: return httpx.Response(412)
            self.content = request.content; self.etag = '"two"'; return httpx.Response(200, json={'id': 'file_1'})
        if request.url.params.get('alt') == 'media':
            content = self.content
            if self.changed: self.etag = '"raced"'
            return httpx.Response(200, content=content, headers={'content-encoding':'gzip'} if self.oversized else {})
        return httpx.Response(200, json={'id':'file_1','mimeType':'text/markdown','trashed':False,'parents':['parent_1'], 'capabilities':{'canEdit':True},'owners':[{'permissionId':'owner','emailAddress':'fixture@example.invalid'}]})


def transport(api, evidence=None):
    return GoogleMarkdownTransport(
        CredentialLease('fictional-bearer',datetime.now(timezone.utc)+timedelta(hours=1),frozenset({DRIVE_FILE_SCOPE}),'fixture','synthetic'),
        AccountExpectation('owner','fixture@example.invalid'), DestinationExpectation('file_1','parent_1'),
        http_transport=httpx.MockTransport(api.handle), conditional_write_evidence=evidence)


def test_exact_media_read_and_conditional_write():
    api=API()
    with transport(api, 'synthetic negative-precondition evidence') as t:
        snap=t.read('file_1'); assert snap.content==api.content
        t.write('file_1',b'# Correction\n',snap.etag)
        assert t.read('file_1').content==b'# Correction\n'
    assert len(api.writes)==1 and api.writes[0].headers['if-match']=='"one"'
    assert api.writes[0].url.path=='/upload/drive/v2/files/file_1'


def test_unqualified_update_refuses_before_request():
    api=API()
    with transport(api) as t:
        with pytest.raises(TransportError): t.write('file_1',b'new','"one"')
    assert api.writes==[]


@pytest.mark.parametrize('mode',['race','gzip','weak'])
def test_incoherent_or_unsupported_read_refuses(mode):
    api=API(); api.changed=mode=='race'; api.oversized=mode=='gzip'
    if mode=='weak': api.etag='W/"one"'
    with transport(api) as t:
        with pytest.raises(TransportError): t.read('file_1')


def test_stale_precondition_refuses_before_upload():
    api=API()
    with transport(api,'synthetic evidence') as t:
        old=t.read('file_1'); api.etag='"manual"'
        with pytest.raises(TransportError): t.write('file_1',b'new',old.etag)
    assert api.writes==[]
