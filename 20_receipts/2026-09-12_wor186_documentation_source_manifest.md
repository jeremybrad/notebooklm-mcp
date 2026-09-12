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
