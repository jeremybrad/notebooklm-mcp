"""Full synthetic Git -> accepted selector -> batch -> native HTTP -> recovery."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import httpx

from notebooklm_mcp.doc_refresh.google_docs_transport import (
    AccountExpectation, CredentialLease, DestinationExpectation, GoogleDocsTransport,
)
from notebooklm_mcp.doc_refresh.publication_batch import Job, execute
from notebooklm_mcp.doc_refresh.publication_state import KEY, MapStore, bind_empty
from notebooklm_mcp.doc_refresh.source_bundle import build_bundle
from tests.test_drive_publication import apply_requests, document
from tests.test_source_bundle import repo as source_repo, commit, git


class GoogleFixture:
    def __init__(self):
        self.raw = document()
        self.writes = 0
        self.lose_response = False
        self.account = "synthetic-owner"

    def __call__(self, request):
        assert request.headers["authorization"] == "Bearer fictional-bearer"
        path = request.url.path
        if path.endswith("/about"):
            return httpx.Response(200, json={"user": {
                "permissionId": self.account, "emailAddress": "test@example.invalid"}})
        if path.endswith("/permissions"):
            return httpx.Response(200, json={"permissions": [{
                "id": "synthetic-owner", "type": "user", "role": "owner",
                "emailAddress": "test@example.invalid", "deleted": False,
                "pendingOwner": False}]})
        if "/drive/v3/files/" in path:
            return httpx.Response(200, json={
                "id": "synthetic-doc", "mimeType": "application/vnd.google-apps.document",
                "trashed": False, "parents": ["synthetic-parent"], "ownedByMe": True,
                "shared": False, "capabilities": {"canEdit": True},
                "owners": [{"permissionId": "synthetic-owner", "emailAddress": "test@example.invalid",
                            "me": True}]})
        assert path.startswith("/v1/documents/synthetic-doc")
        if request.method == "GET":
            assert request.url.params["includeTabsContent"] == "true"
            assert request.url.params["suggestionsViewMode"] == "SUGGESTIONS_INLINE"
            assert "fields" not in request.url.params
            return httpx.Response(200, json=deepcopy(self.raw))
        assert request.method == "POST" and path.endswith(":batchUpdate")
        body = json.loads(request.content)
        assert body["writeControl"] == {"requiredRevisionId": self.raw["revisionId"]}
        assert "NEVER EXPORT" not in request.content.decode()
        self.raw = apply_requests(SimpleNamespace(body=body), self.raw)
        self.writes += 1
        self.raw["revisionId"] = "r" + str(self.writes + 1)
        if self.lose_response:
            raise httpx.ReadTimeout("fictional-bearer DO NOT LOG response body", request=request)
        return httpx.Response(200, json={"documentId": "synthetic-doc", "replies": []})


def setup(tmp_path, source_repo):
    store = MapStore(tmp_path / "notebook_map.yaml")
    remote = GoogleFixture()
    bind_empty(store, source_repo.name, "synthetic-notebook", remote.raw)
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    lease = CredentialLease("fictional-bearer", now + timedelta(hours=1),
                            frozenset({"https://www.googleapis.com/auth/drive.file"}),
                            "synthetic-client", "synthetic-test")

    def factory(job, document_id):
        assert job.repo == source_repo and document_id == "synthetic-doc"
        return GoogleDocsTransport(lease, AccountExpectation("synthetic-owner", "test@example.invalid"),
                                   DestinationExpectation(document_id, "synthetic-parent"),
                                   http_transport=httpx.MockTransport(remote), clock=lambda: now)

    return store, remote, receipts, factory


def test_publish_nochange_lost_response_then_explicit_reconcile(tmp_path, source_repo):
    store, remote, receipts, factory = setup(tmp_path, source_repo)
    job = Job(source_repo, git(source_repo, "rev-parse", "HEAD"))
    first = execute("publish", [job], store, receipts, transport_factory=factory)
    assert first["status"] == "success"
    assert remote.writes == 1
    assert build_bundle(source_repo, job.revision).bundle.text == remote.raw["tabs"][0]["documentTab"]["body"]["content"][1]["paragraph"]["elements"][0]["textRun"]["content"]
    assert execute("publish", [job], store, receipts, transport_factory=factory)["status"] == "success"
    assert remote.writes == 1
    (source_repo / "README.md").write_text("# Fictional version B 🐝\nThird source and verification step.\n")
    next_job = Job(source_repo, commit(source_repo))
    remote.lose_response = True
    failed = execute("publish", [next_job], store, receipts, transport_factory=factory)
    assert failed["status"] == "failed"
    assert remote.writes == 2  # No automatic retry after Google applied it.
    assert store.read().data["notebooks"][source_repo.name][KEY]["pending"] is not None
    remote.lose_response = False
    recovered = execute("reconcile", [next_job], store, receipts, transport_factory=factory)
    assert recovered["status"] == "success"
    assert remote.writes == 2
    entry = store.read().data["notebooks"][source_repo.name][KEY]
    assert entry["pending"] is None
    assert entry["verified"]["sha256"] == build_bundle(source_repo, next_job.revision).bundle.sha256
    assert entry["notebook"] is None and entry["artifacts"] == {}
    for path in receipts.glob("*.json"):
        text = path.read_text()
        assert "fictional-bearer" not in text and "DO NOT LOG" not in text
        assert "Third source" not in text and "NEVER EXPORT" not in text


def test_wrong_account_stops_before_post_or_pending(tmp_path, source_repo):
    store, remote, receipts, factory = setup(tmp_path, source_repo)
    before = store.path.read_bytes()
    remote.account = "wrong-account"
    result = execute("publish", [Job(source_repo, git(source_repo, "rev-parse", "HEAD"))],
                     store, receipts, transport_factory=factory)
    assert result["status"] == "failed"
    assert remote.writes == 0
    assert store.path.read_bytes() == before
