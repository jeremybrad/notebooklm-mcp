"""Pure, caller-profile documentation attention; no provider or persistence route."""

from copy import deepcopy
import hashlib
import json
import re
from pathlib import PurePosixPath

from .selection import normalize_relpath


def _commit(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-f]{40}|[0-9a-f]{64}", value
    ):
        raise ValueError("immutable_commit_required")


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("document_hash_required")


def _path(value):
    if (
        not isinstance(value, str)
        or not value
        or normalize_relpath(value) != value
        or "\\" in value
        or PurePosixPath(value).is_absolute()
        or ".." in PurePosixPath(value).parts
        or PurePosixPath(value).as_posix() != value
        or "\x00" in value
    ):
        raise ValueError("canonical_path_required")


def _profile(profile, documents):
    if not isinstance(profile, dict) or set(profile) != {"topics", "irrelevant_paths"}:
        raise ValueError("explicit_profile_required")
    topics = profile["topics"]
    if not isinstance(topics, dict) or not topics:
        raise ValueError("topic_bindings_required")
    bindings = {}
    required_docs = set()
    for topic, binding in topics.items():
        if not isinstance(topic, str) or not topic or not isinstance(binding, dict):
            raise ValueError("invalid_topic")
        if set(binding) != {"implementation_paths", "document_paths"}:
            raise ValueError("explicit_topic_paths_required")
        for key in binding:
            paths = binding[key]
            if (
                not isinstance(paths, list)
                or not paths
                or len(set(paths)) != len(paths)
            ):
                raise ValueError("invalid_topic_paths")
            for path in paths:
                _path(path)
                bindings.setdefault(path, set()).add(topic)
                if key == "document_paths":
                    required_docs.add(path)
    irrelevant = profile["irrelevant_paths"]
    if not isinstance(irrelevant, list) or len(set(irrelevant)) != len(irrelevant):
        raise ValueError("invalid_irrelevant_paths")
    for path in irrelevant:
        _path(path)
        if path in bindings:
            raise ValueError("ambiguous_profile")
    if not isinstance(documents, dict) or set(documents) != required_docs:
        raise ValueError("selected_document_inputs_missing_or_unknown")
    for value in documents.values():
        _hash(value)
    digest = hashlib.sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return bindings, set(irrelevant), digest


def successful_review_baseline(candidate, profile, documents, evidence):
    """Return an eligible later baseline only for explicit exact-bound success.

    This validates the caller's evidence contract; it does not attest a real review
    or merge. It neither writes nor advances any stored baseline.
    """
    _commit(candidate)
    _, _, profile_hash = _profile(profile, documents)
    if not isinstance(evidence, dict) or set(evidence) != {
        "status",
        "candidate",
        "profile_sha256",
        "documents",
    }:
        raise ValueError("exact_review_evidence_required")
    if (
        evidence["status"] != "success"
        or evidence["candidate"] != candidate
        or evidence["profile_sha256"] != profile_hash
        or evidence["documents"] != documents
    ):
        raise ValueError("successful_exact_review_required")
    return candidate


def reduce_review(
    last_reviewed,
    candidate,
    changed_evidence,
    documents,
    profile,
    pending=None,
    *,
    provider=None,
    model=None,
):
    """Coalesce attention without ever promoting last_reviewed or calling models.

    changed_evidence must be the caller's complete base-to-candidate immutable
    path/blob inventory, not a delta from the last attempted review.
    """
    result = {
        "state": "blocked",
        "reviewed_baseline": last_reviewed,
        "candidate": candidate,
        "affected_topics": [],
        "pending": deepcopy(pending),
        "reasons": [],
    }
    try:
        if provider is not None or model is not None:
            raise ValueError("provider_functions_not_supported")
        _commit(last_reviewed)
        _commit(candidate)
        bindings, irrelevant, profile_hash = _profile(profile, documents)
        if (
            not isinstance(changed_evidence, dict)
            or set(changed_evidence) != {"base", "candidate", "complete", "changes"}
            or changed_evidence["base"] != last_reviewed
            or changed_evidence["candidate"] != candidate
            or changed_evidence["complete"] is not True
            or not isinstance(changed_evidence["changes"], list)
        ):
            raise ValueError("complete_baseline_to_candidate_evidence_required")
        affected = set()
        if pending is not None:
            if (
                not isinstance(pending, dict)
                or set(pending)
                != {"baseline", "candidate", "profile_sha256", "topics", "documents"}
                or pending["baseline"] != last_reviewed
                or pending["profile_sha256"] != profile_hash
                or not isinstance(pending["topics"], list)
                or not pending["topics"]
                or not set(pending["topics"]) <= set(profile["topics"])
                or not isinstance(pending["documents"], dict)
                or set(pending["documents"]) != set(documents)
            ):
                raise ValueError("pending_context_mismatch")
            _commit(pending["candidate"])
            for value in pending["documents"].values():
                _hash(value)
            affected.update(pending["topics"])
        seen = set()
        for change in changed_evidence["changes"]:
            if not isinstance(change, dict) or set(change) != {
                "path",
                "kind",
                "before_blob",
                "after_blob",
                "old_path",
            }:
                raise ValueError("explicit_blob_change_required")
            path = change["path"]
            _path(path)
            if path in seen:
                raise ValueError("duplicate_changed_path")
            seen.add(path)
            kind = change["kind"]
            before, after, old = (
                change["before_blob"],
                change["after_blob"],
                change["old_path"],
            )
            if kind not in {"modified", "added", "deleted", "renamed"}:
                raise ValueError("unknown_change_kind")
            if before is not None:
                _commit(before)
            if after is not None:
                _commit(after)
            if (
                (kind == "added" and (before is not None or after is None))
                or (kind == "deleted" and (before is None or after is not None))
                or (
                    kind in {"modified", "renamed"}
                    and (before is None or after is None)
                )
                or (kind == "modified" and before == after)
            ):
                raise ValueError("inconsistent_blob_evidence")
            paths = {path}
            if kind == "renamed":
                _path(old)
                paths.add(old)
            elif old is not None:
                raise ValueError("unexpected_old_path")
            topics = set().union(*(bindings.get(p, set()) for p in paths))
            if kind in {"deleted", "renamed"} and topics:
                raise ValueError("bound_path_deleted_or_renamed")
            if any(p not in bindings and p not in irrelevant for p in paths):
                raise ValueError("unknown_path_classification")
            affected.update(topics)
        if candidate == last_reviewed and changed_evidence["changes"]:
            raise ValueError("same_revision_has_changes")
        result["affected_topics"] = sorted(affected)
        if affected:
            result.update(
                state="review_needed",
                pending={
                    "baseline": last_reviewed,
                    "candidate": candidate,
                    "profile_sha256": profile_hash,
                    "topics": sorted(affected),
                    "documents": deepcopy(documents),
                },
            )
        else:
            result.update(state="no_change", pending=None)
    except (ValueError, TypeError, KeyError) as error:
        # Validation errors are fixed codes; never serialize arbitrary input text.
        result["reasons"] = [
            str(error) if isinstance(error, ValueError) else "malformed_input"
        ]
    return result
