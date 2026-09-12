# Receipt: WOR-186 documentation source manifest

**Date:** 2026-09-12
**Issue:** WOR-186
**Branch:** `jeremybradford1977/wor-186-c021-define-repo-documentation-source-manifest`
**Base:** `origin/main` (`3681e88a5ad0bd633f7497cce4ee9c623f4479cd`)
**Executor:** Grok Build sandbox
**Status:** implementation on isolated checkout; independent review not yet launched; not merged

## What

Extended the existing `canonical_docs.yaml` producer (no second registry) with:

- JSON Schema draft 2020-12 (`c021.canonical_docs.v1`)
- Default privacy/build exclusions
- Fail-closed path and symlink containment
- `extra_docs` actually consumed, still subject to exclusions
- Freshness fields on `DocItem` (`source_title`, `last_commit`, `generated_bundle_id`) plus manifest byte hash
- Synthetic fixtures for simple / complex / kitted representative repos

No NotebookLM upload, Drive, auth, or scheduler work.

## Verification

Offline pytest against `tests/` including `tests/test_canonical_docs_manifest.py`.

## Stop lines honored

- No `notebook_add_*`
- No Drive
- No `doc-refresh --apply` against a live notebook
- No scheduler install
- No cookie writes

## Mac finishing review repairs

Independent guarded Codex round 1 proposed F1 internal symlink privacy bypass, F2 tier-3 absolute path acceptance/crash, F3 in-memory manifest false byte provenance. Each reproduced with synthetic fixtures before repair. Discovery now rejects symlink components, checks original tier-3 names before joining, and only assigns manifest file hash when file content matches selection. 72 offline tests pass on Mac. Full-context independent re-review follows at pushed head. No uploads or runtime changes.

Round2 F4/F5 confirmed and repaired: dot-segment aliases bypassed exact exclusions; absolute scan patterns crashed discovery. Three synthetic regressions red before repair;75 offline tests pass after rejecting ambiguous relative spellings and unsupported scan patterns.

Round3 reopened F4 once for repeated separators (docs//restricted.md). Reproduced before repair; empty interior components now refused.76 offline tests pass. Prior F1-F3/F5 remain resolved.


## Bounded canonical-identity repair (2026-09-12)

Jeremy authorized at 17:07:24 UTC: “I authorize one canonical-path identity repair and at most two additional repair-focused independent reviews. Preserve all history. Stop if F4 persists or scope expands. No live uploads, authentication changes, or scheduler activation.”

Round4 retained F4: trailing separators were accepted by containment but exclusion matching used a different spelling from the Path stored and subsequently read. Four synthetic variants failed before this repair. Exclusion matching now uses that same lexical Path identity; containment still rejects symlinks, parent traversal and interior ambiguous components. The regression matrix covers trailing single/double separators, leading ./, backslash spellings, earlier dot/interior separator cases, and preserved directory discovery. Empty input remains empty rather than becoming a current-directory identity. No path is resolved to load private content in these tests. Full offline validation and independent review are recorded on PR #5; previous review findings and counts are retained.

## Filesystem-identity repair (2026-09-12, separately authorized)

The prior lexical repair did not close F4: a synthetic macOS case alias selected an excluded file. Jeremy authorized at 17:58:28 UTC: “One filesystem-identity repair covering the reproduced macOS case-alias defect and relevant exclusion/containment behavior, followed by one independent repair review. Use synthetic fixtures; no live uploads or source processing. Stop if F4 persists or scope expands.”

Seven synthetic filename/directory case, exclusion-prefix and Unicode-normalization cases failed before this repair. Existing literal path components now use directory-entry identity: alternate include spellings fail closed, and literal exclusion prefixes resolve to their actual spelling before matching. Wildcards retain the existing case-sensitive matching semantics. Missing suffixes remain eligible for ordinary missing-required reporting. Filesystem lookup errors fail closed. Existing lexical separator and symlink defenses remain. No file contents are read to establish identity.

Guarded Grok supplied an implementation-only proposal (not independent clearance); Betty applied and verified the bounded repair. Synthetic tests cover selection, scans, alternates, filtering, canonical paths, missing paths, lookup errors and symlink containment. Exact review and current-base check results remain on PR #5. Previous rounds, findings, lexical repair and operator decisions are preserved. No uploads or live source processing occurred.
