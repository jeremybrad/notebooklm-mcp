"""Synthetic partial batches; injected transport never accesses a provider."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import json

import pytest
import yaml

from notebooklm_mcp.doc_refresh.individual_batch import execute
from notebooklm_mcp.doc_refresh.individual_publication import Snapshot, bind_empty
from notebooklm_mcp.doc_refresh.publication_batch import Job
from notebooklm_mcp.doc_refresh.publication_state import MapStore
from notebooklm_mcp.doc_refresh.source_bundle import build_bundle
from tests.test_individual_publication import selected as original_selected, git


@pytest.fixture
def selected(tmp_path):
    return original_selected.__wrapped__(tmp_path)


def setup_batch(selected, tmp_path, third=False):
    root, manifest = selected
    if third:
        (root / "c").mkdir()
        (root / "c/reference.md").write_text("# Third original\n")
        git(root, "add", ".")
        git(root, "commit", "-qm", "third original")
        data = yaml.safe_load(manifest.read_text())
        data["repo_overrides"][root.name]["extra_docs"].append(
            dict(
                path="c/reference.md",
                purpose="fixture",
                must_exist=True,
                stub_allowed=False,
            )
        )
        manifest.write_text(yaml.safe_dump(data))
    artifact = build_bundle(root, "HEAD", manifest_path=manifest)
    store = MapStore(tmp_path / "map.yaml")
    remotes = {}
    writes = {}
    reads = []
    for i, source in enumerate(artifact.documents):
        identity = f"file_{i}"
        remotes[identity] = Snapshot(identity, '"empty"', b"")
        writes[identity] = 0
        bind_empty(store, source, "notebook_1", remotes[identity])

    @contextmanager
    def factory(job, identity):
        class Transport:
            def read(self, file_id):
                assert file_id == identity
                reads.append(identity)
                return remotes[identity]

            def write(self, file_id, content, etag):
                assert file_id == identity and etag == remotes[identity].etag
                writes[identity] += 1
                remotes[identity] = Snapshot(identity, '"written"', content)
                if identity == "file_1":
                    raise TimeoutError("synthetic lost reply")

        yield Transport()

    jobs = [Job(root, artifact.receipt["commit"])]
    receipts = tmp_path / "receipts"
    receipts.mkdir()

    def run(mode, jobs_override=None):
        return execute(
            mode,
            jobs_override or jobs,
            store,
            receipts,
            manifest_path=manifest,
            transport_factory=factory,
        )

    failed = run("publish")
    assert [i["status"] for i in failed["items"]] == (
        ["success", "failed", "not_attempted"] if third else ["success", "failed"]
    )
    return root, manifest, store, remotes, writes, reads, run


@pytest.mark.parametrize("third", [False, True])
def test_original_batch_recovery_never_replays_success_or_attempts_tail(
    selected, tmp_path, third
):
    _, _, store, remotes, writes, reads, run = setup_batch(selected, tmp_path, third)
    before = deepcopy(store.read().data["notebooks"])
    reads.clear()
    result = run("reconcile")
    items = result["items"]
    assert [i["status"] for i in items] == (
        ["success", "success", "not_attempted"] if third else ["success", "success"]
    )
    assert [i["action"] for i in items[:2]] == ["verified_sibling", "verified_target"]
    assert result["exit_code"] == (1 if third else 0)
    assert reads == ["file_0", "file_1"]
    assert writes == (
        {"file_0": 1, "file_1": 1, "file_2": 0} if third else {"file_0": 1, "file_1": 1}
    )
    after = store.read().data["notebooks"]
    repo = next(iter(before))
    assert (
        after[repo]["drive_documents"]["a/reference.md"]
        == before[repo]["drive_documents"]["a/reference.md"]
    )
    assert after[repo]["drive_documents"]["b/reference.md"]["pending"] is None
    if third:
        assert (
            after[repo]["drive_documents"]["c/reference.md"]
            == before[repo]["drive_documents"]["c/reference.md"]
        )
        assert remotes["file_2"].content == b""
    receipt = json.loads(open(result["receipt_path"]).read())
    assert receipt["items"] == items and "file_0" not in json.dumps(receipt)


@pytest.mark.parametrize(
    "changed", ["commit", "manifest", "sibling_remote", "pending_remote"]
)
def test_recovery_refuses_changed_inputs_or_ambiguous_remote_without_writes(
    selected, tmp_path, changed
):
    root, manifest, store, remotes, writes, reads, run = setup_batch(selected, tmp_path)
    jobs = None
    if changed == "commit":
        (root / "a/reference.md").write_text("# Changed original\n")
        git(root, "add", ".")
        git(root, "commit", "-qm", "changed inputs")
        jobs = [Job(root, git(root, "rev-parse", "HEAD"))]
    elif changed == "manifest":
        data = yaml.safe_load(manifest.read_text())
        data["repo_overrides"][root.name]["extra_docs"][0]["purpose"] = (
            "changed profile"
        )
        manifest.write_text(yaml.safe_dump(data))
    else:
        identity = "file_0" if changed == "sibling_remote" else "file_1"
        remotes[identity] = replace(remotes[identity], content=b"manual external edit")
    before = store.path.read_bytes()
    reads.clear()
    result = run("reconcile", jobs)
    assert result["exit_code"] == 1
    assert store.path.read_bytes() == before
    assert writes == {"file_0": 1, "file_1": 1}
    if changed in {"commit", "manifest"}:
        assert reads == []


def test_recovery_to_base_and_repeat_do_not_publish(selected, tmp_path):
    _, _, store, remotes, writes, reads, run = setup_batch(selected, tmp_path)
    remotes["file_1"] = Snapshot("file_1", '"empty"', b"")
    result = run("reconcile")
    assert result["exit_code"] == 0
    assert result["items"][1]["action"] == "verified_base"
    before = store.path.read_bytes()
    reads.clear()
    repeated = run("reconcile")
    assert repeated["error"] == "individual_preflight_failed"
    assert reads == [] and store.path.read_bytes() == before
    assert writes == {"file_0": 1, "file_1": 1}


def test_nonempty_unpending_sibling_is_ambiguous(selected, tmp_path):
    _, _, store, _, writes, reads, run = setup_batch(selected, tmp_path, True)
    with store.transaction() as transaction:
        old = store.read()
        data = deepcopy(old.data)
        repo = next(iter(data["notebooks"]))
        entry = data["notebooks"][repo]["drive_documents"]["c/reference.md"]
        # A prior publication is not proof of an unattempted tail for this batch.
        import hashlib

        entry["verified"]["sha256"] = hashlib.sha256(b"prior content").hexdigest()
        transaction.save(old, data)
    before = store.path.read_bytes()
    reads.clear()
    result = run("reconcile")
    assert result["error"] == "individual_preflight_failed"
    assert reads == [] and store.path.read_bytes() == before
    assert writes == {"file_0": 1, "file_1": 1, "file_2": 0}


@pytest.mark.parametrize("identity", ["file_0", "file_1"])
@pytest.mark.parametrize("failure", ["suppressed_operation", "finalization"])
def test_recovery_requires_completed_operation_and_context(
    selected, tmp_path, identity, failure
):
    from notebooklm_mcp.doc_refresh.publication_state import StateError

    root, manifest, store, remotes, writes, reads, _ = setup_batch(
        selected, tmp_path, True
    )
    artifact = build_bundle(root, "HEAD", manifest_path=manifest)
    if failure == "suppressed_operation":
        remotes[identity] = replace(remotes[identity], content=b"external edit")
    reads.clear()

    @contextmanager
    def factory(job, file_id):
        class Transport:
            def read(self, requested):
                reads.append(requested)
                return remotes[requested]

            def write(self, *args):
                pytest.fail("reconciliation must not write")

        try:
            yield Transport()
        except StateError:
            if file_id != identity or failure != "suppressed_operation":
                raise
        if file_id == identity and failure == "finalization":
            raise OSError("synthetic context finalization failure")

    result = execute(
        "reconcile", [Job(root, artifact.receipt["commit"])], store,
        tmp_path / "receipts", manifest_path=manifest, transport_factory=factory,
    )
    failed = 0 if identity == "file_0" else 1
    assert result["exit_code"] == 1
    assert result["items"][failed]["status"] == "failed"
    assert result["items"][failed]["verification"] == "offline"
    assert all(item["status"] == "not_attempted" for item in result["items"][failed + 1:])
    assert reads == (["file_0"] if failed == 0 else ["file_0", "file_1"])
    assert writes == {"file_0": 1, "file_1": 1, "file_2": 0}
    if failure == "suppressed_operation":
        assert store.read().data["notebooks"][root.name]["drive_documents"][
            "b/reference.md"
        ]["pending"] is not None
    receipt = json.loads(open(result["receipt_path"]).read())
    assert receipt["items"] == result["items"]


@pytest.mark.parametrize("identity", ["file_0", "file_1"])
@pytest.mark.parametrize("configured", [False, True])
def test_recovery_pins_preflight_destination_before_forwarding(
    selected, tmp_path, identity, configured
):
    from types import SimpleNamespace
    from notebooklm_mcp.doc_refresh.individual_publication import document_key

    root, manifest, store, remotes, writes, reads, _ = setup_batch(
        selected, tmp_path, True
    )
    artifact = build_bundle(root, "HEAD", manifest_path=manifest)
    config = SimpleNamespace(destinations={
        document_key(source): SimpleNamespace(document_id=f"file_{i}")
        for i, source in enumerate(artifact.documents)
    }) if configured else None
    reads.clear()

    @contextmanager
    def factory(job, file_id):
        if file_id == identity:
            with store.transaction() as transaction:
                old = store.read()
                data = deepcopy(old.data)
                data["notebooks"][root.name]["drive_documents"][job.source.path][
                    "file_id"
                ] = "file_alt"
                transaction.save(old, data)
            remotes["file_alt"] = replace(remotes[identity], file_id="file_alt")

        class Transport:
            def read(self, requested):
                reads.append(requested)
                return remotes[requested]

            def write(self, *args):
                pytest.fail("reconciliation must not write")

        yield Transport()

    result = execute(
        "reconcile", [Job(root, artifact.receipt["commit"])], store,
        tmp_path / "receipts", manifest_path=manifest, transport_factory=factory,
        config=config,
    )
    failed = 0 if identity == "file_0" else 1
    assert result["exit_code"] == 1
    assert result["items"][failed]["status"] == "failed"
    assert reads == ([] if failed == 0 else ["file_0"])
    assert all(item["status"] == "not_attempted" for item in result["items"][failed + 1:])
    assert writes == {"file_0": 1, "file_1": 1, "file_2": 0}
    assert store.read().data["notebooks"][root.name]["drive_documents"][
        "b/reference.md"
    ]["pending"] is not None
