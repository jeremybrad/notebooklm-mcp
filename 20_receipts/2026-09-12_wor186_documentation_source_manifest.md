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

## Literal basename identity continuation (2026-09-12)

Round 5 retained F4: a literal basename exclusion `RESTRICTED.md` was resolved against the repository root, so the macOS alias of `docs/restricted.md` remained selectable. Jeremy's reply “Approved” was observed at 23:41:06 UTC in response to the pending bounded decision: resolve literal basename identity beside each candidate, preserve wildcard/case-sensitive/containment behavior, and permit exactly one independent repair review with a 15-minute limit and $0 metered usage. Stop if F4 persists, an equal/higher regression appears, scope expands, or another review is needed. The observation time is not an asserted message timestamp.

Nested, deeper-nested and Unicode-normalization alias fixtures failed on the prior implementation. Literal basename exclusions now resolve beside the candidate's actual parent; an unrelated root file cannot control that identity. Wildcards and root-relative exclusions retain existing behavior. The full synthetic suite passes: 112 passed, 1 filesystem-dependent skip. All five prior review rounds and findings remain in the append-only PR record; this change supplies no independent clearance. No live uploads, source processing, authentication or scheduler changes occurred.


## Literal parent spelling repair (2026-09-26, separately authorized)

Round 6 retained F4: the literal parent in `docs[1]/restricted.md` was
reinterpreted as a glob when matching the resolved `RESTRICTED.md` basename.
Jeremy replied “I approve - please proceed” to Betty's explicit bounded request
(observed 2026-09-26T01:09:42Z, not asserted message timestamp): repair this
defect, integrate current main, and run one Grok repair review at medium effort
with up to 60 minutes; stop if the defect persists after repair or scope expands.
All six earlier reviews and findings remain in the append-only PR #5 history.

Four regression cases failed before the repair: direct exclusion checks and
actual extra_docs discovery under bracket-containing and nested bracket-containing
parents. They now pass. Resolved literal basename paths use equality; explicit
glob patterns keep their previous matching semantics. Ordinary, question-mark
and asterisk parents, Unicode/case aliases, missing exclusions, allowed siblings
and existing symlink/containment regressions remain covered. No real repository
documentation or private payload was selected for these tests.

Integrated main at `546688c43495d403ee2336bfbd0891a4e60b7e24` (PR #7's
already-reviewed offline pilot), retaining both changelog additions. The only
merge conflict was CHANGELOG.md. The inherited pilot stays disconnected from
source discovery and live I/O; its WOR-788/789 follow-ups remain separate.
Exact test/build results, independent review and readiness are recorded on PR #5;
this receipt alone is not clearance. No live uploads, credentials, scheduler or
canonical-checkout runtime changes are included.

## Full-scope R8 repairs (2026-09-26, separately authorized)

R7 completed without repair findings. R8 restored a complete primary assessment
after a historical capture gap and identified R8-N1 (P1 malformed supplied
manifests), R8-N2 (P2 directory scans through ancestor aliases), reopened F3
(P2 manifest byte-provenance race), and R8-N3 (P2 Git pathspec interpretation).
All four reproduced locally using synthetic fixtures. Jeremy replied
“Authorize repairs and one review” to the four-item plan and exactly one
full-scope Codex subscription review, at most 30 minutes and $0 API spend
(reply observed 2026-09-26T01:43:16Z, not asserted message timestamp).
All eight earlier rounds and original finding identities/severities are retained.

Eight regression cases failed before repair. Discovery now validates an owned
copy of supplied mappings before selection. Manifest loading captures one byte
sequence for parsing, validation and hashing; supplied mappings receive that
hash only when they match the captured parse. Scan matches are made relative
to the same lexical root used by glob, with containment still checked separately.
Git last-touch lookup uses literal pathspec mode.

The prior case/Unicode/path fixtures omitted schema-required purpose/reason
metadata. Those fixtures now satisfy the existing schema so their original
selection assertions continue to execute; malformed-input tests still require
refusal. Full tests pass on Python 3.11 and 3.13: 148 passed, one
filesystem-dependent skip. Coverage command passes with 31% whole-package
coverage; wheel and source-distribution builds pass. Scope: discover.py,
manifest.py, their existing test file, INTERFACES.md, this receipt and changelog.
Independent R9 review and final readiness remain separate evidence on PR #5.
No live sources, uploads, credentials, scheduling or canonical runtime changes.

## R9 consumer consolidation (2026-09-26, separately authorized)

R9 accepted all four prior repairs but found three P1 privacy gaps: recursive
exclusions missed zero-directory interior matches; the legacy automatic sync
selector bypassed the manifest; and the deprecated primer gatherer appended
unchecked RELATIONS content. All reproduced with synthetic data. Jeremy replied
“Authorize consolidation and one review” to these fixes, explicitly adding
`src/notebooklm_mcp/sync_cli.py` and `src/notebooklm_mcp/primer_gen/sources.py`
to scope and permitting one full-scope Codex subscription review, 30 minutes and
$0 API spend (observed 2026-09-26T01:58:07Z, not asserted message timestamp).
The nine prior rounds and all original findings/severities remain recorded.

Eight of twelve new regression cases failed before repair; the other four
established retained behavior. A component-state walk now recognizes zero or
more directories for recursive ** components at any position, retaining earlier
fnmatch matches. The legacy --tier3 automatic selector uses common validated
discovery and returns existing files only; automatic paths remain literal
through CLI handoff rather than being expanded a second time. This replaces
its former broad Markdown glob with the manifest's tiers/overrides. Explicit
manual-file CLI input remains a separate, unchanged operator-directed path.

RELATIONS.yaml is an optional tier-1 manifest entry. The deprecated primer
reader no longer appends it independently, so explicit exclusions and internal
or external symlinks are refused by ordinary discovery. Safe RELATIONS content
remains available. Tests cover zero/nested/multiple recursive components,
retained allowed files, private files and symlinks in automatic selection,
CLI handoff of literal wildcard filenames, explicit RELATIONS exclusions and
both symlink directions, and safe RELATIONS inclusion. No network or model call
is needed by these tests. Full test/build evidence and the independently
assessed revision remain on PR #5; this receipt does not certify readiness.
No live upload, authentication, scheduler activation or canonical runtime change.

Validation: 160 passed and one filesystem-dependent skip on Python 3.11/3.13;
whole-package coverage 33%; wheel/sdist build passed. The existing
`tests/test_cli_helpers.py` assertion expected the superseded broad legacy glob.
It now asserts canonical manifest membership and omission of unlisted docs;
this necessary compatibility-test update adds no new behavior beyond the
approved selector consolidation. Its path is included in the complete review
context alongside the two newly admitted consumer code paths.

## Strict manifest YAML construction (2026-09-26, separately authorized)

R10 accepted all eleven previous findings but identified R10-N1 (P1): PyYAML
silently replaced duplicate exclusion keys before schema validation. A synthetic
duplicate global exclusion block reproduced inclusion of a fictional private
file. Jeremy replied “Approved - please continue” to this bounded loader repair
and one full-scope Codex subscription review, at most 30 minutes/$0 API
(observed 2026-09-26T02:16:43Z, not asserted message timestamp). Preserve all ten
prior rounds and stop for a new/unresolved blocker or further review need.

Fifteen cases failed before repair: global exclusion duplicates, repeated
repository override names, nested exclusion duplicates, merge collisions and
repeated merge keys, each through loader, discovery and schema-opt-out entry
points. A manifest-only SafeLoader subclass checks mapping keys before and after
merge flattening, rejecting overwrites with ManifestError. Nonconflicting merges
remain supported, with a regression preserving exclusion behavior and exact
captured-byte provenance. Ordinary schema checks remain separate. Other YAML
loaders, runtime state and authentication are unchanged. Test/build results and
the exact independent R11 assessment are recorded on PR #5; this receipt alone
does not establish readiness. No live sources, uploads or scheduler changes.

## String repository override names (2026-09-26, separately authorized)

R11 accepted the duplicate-key repair and all twelve prior findings. New P1
R11-N1 was reproduced through file-loaded and supplied manifests: numeric or
boolean override keys passed validation but missed string repository names,
selecting a fictional README despite its explicit exclusion. Quoted controls
correctly excluded it. Jeremy replied “Approved” to the bounded schema repair
and exactly one full-scope Codex subscription review, at most 30 minutes/$0 API
(observed 2026-09-26T02:32:32Z, not asserted message timestamp; PR comment
5842407060). Preserve all eleven prior reviews; stop for new/unresolved blockers,
material scope/base movement, incomplete result or further review need.

The existing schema now requires string property names in `repo_overrides`.
It rejects malformed names rather than coercing them. Twenty-four regressions
failed before the patch: integer, boolean, null and float keys, alone or mixed
with a valid name, through loader, file discovery and supplied discovery.
Eight string-name controls preserve exclusions through both discovery paths.
The existing shared validator needs no change. No selector or runtime wiring
was added. Full validation and exact independent R12 assessment are recorded
on PR #5; this receipt alone does not establish readiness. No live publication,
authentication, scheduler or merge action is included.

Local validation: 208 passed and one filesystem-dependent skip on Python 3.11
and 3.13; whole-package coverage 33%; wheel and sdist builds passed. The targeted
manifest suite passed 118 tests with one skip. Hosted CI remains disabled for
inactivity; these are local results. Guarded Codex login preflight verified
ChatGPT subscription authentication without inference before review.

## Repository-root identity and diagnostic handling (2026-09-26)

R12 accepted the override-name schema repair but identified R12-N1 (P1): root
case/Unicode aliases miss repository-specific exclusion keys, and R12-N2 (P2):
mixed malformed names/values raise TypeError while sorting diagnostic paths.
Both were reproduced with temporary fictional data. Jeremy replied “Approved!
Thank you!” to the bounded two-fix plan plus exactly one full-scope Codex review,
at most 30 minutes/$0 API (observed 2026-09-26T02:46:32Z, not asserted message
timestamp; PR comment5842504951). Preserve all twelve prior reviews; stop for
new/unresolved blockers, material scope/base movement, incomplete result or
further review need.

Fifteen regression cases failed before repair. Discovery now checks the root's
literal basename against its parent's directory entries before override lookup,
rejecting case/Unicode aliases and direct root symlinks. Canonical exclusion and
allowed-file controls pass through both discovery and the automatic legacy
selector, including a symlinked ancestor. No global lowercasing or Unicode
coercion changes repository identities. Missing roots retain empty discovery.
Validation diagnostics preserve validator order rather than sorting mixed path
component types; loader/file/supplied cases consistently raise ManifestError.
Existing discovery/schema/test/interface/changelog files only; no runtime or
consumer wiring added. Exact test/build and R13 review evidence is on PR #5;
this receipt alone does not establish readiness. No live publication,
authentication, scheduler or merge operation is included.

Local validation: 223 passed and one filesystem-dependent skip on Python 3.11
and 3.13; whole-package coverage 33%; wheel and sdist passed. Targeted manifest
suite: 133 passed/one skip. Guarded subscription login preflight passed without
inference. No hosted CI run is claimed; the inactive workflow remains unchanged.

## Required overrides and final-document tier classification (2026-09-26)

R13 accepted both R12 repairs and reported no further privacy/containment finding,
but identified two P2 correctness defects: duplicate paths lose requiredness
(R13-N1), and existing extra documents are omitted from tier classification
(R13-N2). Both were reproduced locally using synthetic repositories. Jeremy
replied “Great plan - I approve!” to these repairs and up to two full-scope Codex
subscription reviews (14–15), at most 30 minutes each/$0 API total, including
necessary same-scope repairs from the first review. Observed reply time
2026-09-26T03:02:07Z, not asserted message timestamp; approval5842604918.
All thirteen earlier reviews remain. A clean first pass ends review work; stops
remain for material scope/base changes, incomplete results, repeated/reopened
defects or repair regressions, consequential disagreement, or blockers/further
review need after the second pass. No merge or live activation is authorized.

Seven of sixteen new regression/control cases failed before repair. Duplicate
paths now preserve the first item's tier/metadata and combine requiredness,
without weakening an earlier required flag. Classification uses the final
consolidated items, including extras. Tests cover missing/existing duplicate
paths, both requirement orders, validation errors, canonical tier/metadata,
existing versus missing extras, tier-1 duplicates and kitted precedence.
Changes stay in existing discovery/tests/interface/changelog/receipt files.
Exact local validation and independent review evidence are on PR #5; this
receipt alone does not establish readiness. No runtime wiring, source upload,
authentication or scheduler changes.

Local validation: 239 passed and one filesystem-dependent skip on Python 3.11
and 3.13; whole-package coverage 34%; wheel and sdist passed. Targeted manifest
suite: 149 passed/one skip. Guarded ChatGPT subscription login preflight passed
without inference. The inactive hosted workflow remains unchanged.
