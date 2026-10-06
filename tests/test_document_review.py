"""Synthetic caller evidence; providers and publication state are never used."""

from copy import deepcopy
import hashlib
import json

import pytest
from notebooklm_mcp.doc_refresh.document_review import (
    reduce_review,
    successful_review_baseline,
)

A, B, C = "a" * 40, "b" * 40, "c" * 40
PROFILE = {
    "topics": {
        "contract": {
            "implementation_paths": ["src/contract.py"],
            "document_paths": ["docs/contract.md"],
        },
        "operations": {
            "implementation_paths": ["src/runner.py"],
            "document_paths": ["docs/operations.md"],
        },
    },
    "irrelevant_paths": ["fixtures/noise.json", "logs/noise.log"],
}
DOCUMENTS = {"docs/contract.md": "d" * 64, "docs/operations.md": "e" * 64}


def evidence(candidate=B, paths=("src/contract.py",)):
    return {
        "base": A,
        "candidate": candidate,
        "complete": True,
        "changes": [
            {
                "path": path,
                "kind": "modified",
                "before_blob": "1" * 40,
                "after_blob": "2" * 40,
                "old_path": None,
            }
            for path in paths
        ],
    }


def test_code_only_change_requires_review_with_identical_doc_hashes():
    before = deepcopy(DOCUMENTS)
    result = reduce_review(A, B, evidence(), DOCUMENTS, PROFILE)
    assert result["state"] == "review_needed"
    assert result["affected_topics"] == ["contract"]
    assert result["reviewed_baseline"] == A
    assert result["pending"]["documents"] == before == DOCUMENTS
    assert result == reduce_review(A, B, evidence(), DOCUMENTS, PROFILE)


def test_explicit_irrelevant_fixture_and_log_churn_is_no_change():
    result = reduce_review(
        A,
        B,
        evidence(paths=("fixtures/noise.json", "logs/noise.log")),
        DOCUMENTS,
        PROFILE,
    )
    assert result["state"] == "no_change" and result["pending"] is None
    assert result["reviewed_baseline"] == A


def test_relevant_C_coalesces_and_interruption_keeps_A_and_pending():
    first = reduce_review(A, B, evidence(), DOCUMENTS, PROFILE)
    old = deepcopy(first["pending"])
    latest = reduce_review(
        A, C, evidence(C, ("src/contract.py", "src/runner.py")), DOCUMENTS, PROFILE, old
    )
    assert latest["pending"]["baseline"] == A and latest["pending"]["candidate"] == C
    assert latest["affected_topics"] == ["contract", "operations"]
    assert old == first["pending"]
    failed = evidence(C)
    failed["complete"] = False
    interrupted = reduce_review(A, C, failed, DOCUMENTS, PROFILE, old)
    assert interrupted["state"] == "blocked" and interrupted["reviewed_baseline"] == A
    assert interrupted["pending"] == old


@pytest.mark.parametrize("kind", ["deleted", "renamed"])
def test_bound_path_removal_blocks(kind):
    changes = evidence()
    item = changes["changes"][0]
    item["kind"] = kind
    if kind == "deleted":
        item["after_blob"] = None
    else:
        item["old_path"] = item["path"]
        item["path"] = "src/renamed.py"
    assert reduce_review(A, B, changes, DOCUMENTS, PROFILE)["state"] == "blocked"


@pytest.mark.parametrize(
    "case", ["baseline", "documents", "evidence", "profile", "unknown"]
)
def test_missing_or_unknown_inputs_cannot_claim_no_change(case):
    baseline, docs, changes, profile = A, DOCUMENTS, evidence(paths=()), PROFILE
    if case == "baseline":
        baseline = None
    if case == "documents":
        docs = {}
    if case == "evidence":
        changes = None
    if case == "profile":
        profile = {}
    if case == "unknown":
        changes = evidence(paths=("src/unclassified.py",))
    assert reduce_review(baseline, B, changes, docs, profile)["state"] == "blocked"


def test_document_change_is_attention_not_success_and_exact_success_is_required():
    result = reduce_review(
        A, B, evidence(paths=("docs/contract.md",)), DOCUMENTS, PROFILE
    )
    assert result["state"] == "review_needed" and result["reviewed_baseline"] == A
    profile_hash = hashlib.sha256(
        json.dumps(PROFILE, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    success = {
        "status": "success",
        "candidate": B,
        "profile_sha256": profile_hash,
        "documents": DOCUMENTS,
    }
    assert successful_review_baseline(B, PROFILE, DOCUMENTS, success) == B
    for key, value in [
        ("status", "failed"),
        ("candidate", C),
        ("profile_sha256", "f" * 64),
        ("documents", {}),
    ]:
        wrong = dict(success)
        wrong[key] = value
        with pytest.raises(ValueError):
            successful_review_baseline(B, PROFILE, DOCUMENTS, wrong)
    assert result["reviewed_baseline"] == A


def test_injected_providers_never_called_and_publication_bindings_unchanged():
    def forbidden(*args, **kwargs):
        raise AssertionError("provider/model was called")

    publication = {
        "drive_documents": {
            "docs/contract.md": {
                "file_id": "fictional",
                "pending": {"intent": "retain"},
            }
        }
    }
    before = deepcopy(publication)
    result = reduce_review(
        A, B, evidence(), DOCUMENTS, PROFILE, provider=forbidden, model=forbidden
    )
    assert result["state"] == "blocked" and result["reasons"] == [
        "provider_functions_not_supported"
    ]
    assert publication == before


def test_pending_survives_irrelevant_later_change_and_profile_mismatch_blocks():
    pending = reduce_review(A, B, evidence(), DOCUMENTS, PROFILE)["pending"]
    result = reduce_review(
        A, C, evidence(C, ("logs/noise.log",)), DOCUMENTS, PROFILE, pending
    )
    assert result["state"] == "review_needed" and result["affected_topics"] == [
        "contract"
    ]
    assert result["reviewed_baseline"] == A
    changed_profile = deepcopy(PROFILE)
    changed_profile["irrelevant_paths"].append("new.log")
    refused = reduce_review(A, C, evidence(C), DOCUMENTS, changed_profile, pending)
    assert refused["state"] == "blocked" and refused["pending"] == pending


def test_inconsistent_blob_inventory_and_unknown_change_kind_block():
    for patch in [
        {"after_blob": "1" * 40},
        {"kind": "unknown"},
        {"old_path": "unexpected"},
    ]:
        change = evidence()
        change["changes"][0].update(patch)
        assert reduce_review(A, B, change, DOCUMENTS, PROFILE)["state"] == "blocked"
    duplicate = evidence()
    duplicate["changes"] *= 2
    assert reduce_review(A, B, duplicate, DOCUMENTS, PROFILE)["state"] == "blocked"


@pytest.mark.parametrize(
    "path", ["/absolute.py", "src/../contract.py", "src//contract.py"]
)
def test_profile_paths_must_be_canonical_relative_paths(path):
    profile = deepcopy(PROFILE)
    profile["topics"]["contract"]["implementation_paths"] = [path]
    result = reduce_review(A, B, evidence(paths=(path,)), DOCUMENTS, profile)
    assert result["state"] == "blocked" and result["reasons"] == [
        "canonical_path_required"
    ]
