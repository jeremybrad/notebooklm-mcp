# WOR-851: individual original Markdown transport and state

Jeremy approved the bounded per-document implementation plan in the October 1
Codex session: “Plan approved - Please proceed.” Decision record:
[WOR-183](https://linear.app/macromancer/issue/WOR-183#comment-e21aaa2b-0b62-49f8-a5b1-d4db88f76097).
Implementation is isolated on `codex/c021-individual-sources`; canonical/runtime
checkout, installed provider/map, credentials and scheduling are not changed.

The accepted immutable selector now returns individual original sources in
addition to the unchanged bundle. New opt-in CLI/state/transport supports full-path
identity, exact original byte hashes, empty-file adoption, pending intent before
one conditional update, complete readback and read-only reconciliation. These
contract changes are kept in the assessed branch along with this receipt and
changelog. No cloud object, source or artifact was created or deleted.

Evidence: the new feature initially failed collection because the implementation
was absent. Focused fictional Git/state tests verify raw CRLF bytes, repeated
filenames, dirty-worktree isolation, changed/unchanged same-ID updates, manual-edit
refusal, lost-response recovery without replay, original-input refusal, duplicate
file bindings, and all-binding preflight before credentials. Mock HTTP tests verify
exact media reads, stale preconditions, unsupported/incoherent reads, and refusal
without separate live qualification. Existing credential tests caught a context
manager regression during development; preserving the entered transport resolved
it. Native Docs tests remain part of regression validation.

Live conditional enforcement is **unverified**. The raw adapter requires a
separately assessed negative-precondition evidence reference before writes; a
fixture is not qualification. An approved synthetic file test is required before
real writes. A failing raw guard is grounds to assess native Docs fallback, never
to bypass conditional protection. Enrollment, actual Notebook source freshness,
a genuine reviewed/merged C010 correction, broader source coverage and scheduled
cutover remain separate acceptance under WOR-851/853/847/850/854.

Files: source_bundle.py, publication_state.py, individual_publication.py,
google_docs_transport.py, google_markdown_transport.py, publication_credentials.py,
individual_batch.py, publication_cli.py; associated fictional tests and
`docs/doc_refresh/INDIVIDUAL_SOURCES.md`. Detailed validation and independent
review/triage evidence are recorded on the PR at their exact head/base.

## Independent review repair

Guarded Grok 4.7 R2 at `2089e1f` returned R2-F1 P2 (same-basename checkout aliasing), R2-F2 P3 (invalid evidence checked after credentials), R2-F3 P3 (changelog chronology). All verified locally: same-basename synthetic multi-checkout test failed to refuse; three malformed references accessed a mocked Keychain; changelog inspection showed misdated prior evidence. Repairs refuse duplicate logical repository names before any preparation, share one pure evidence predicate before credentials and transport, and restore date grouping. Four regression cases ran RED before repair, GREEN after repair. Original severities and history remain on PR #30; repaired head awaits independent re-review. No cloud, installed runtime or source membership change.

### Round-four residual repair

R4 reopened R2-F1 once: `Path.absolute()` preserved `a/..`, while the source producer used `os.path.abspath`. This bypassed both duplicate basename and omitted-bound-source checks. Two actual Git fixture regressions failed on `15bb72c76a69d81675908b5ed147f003cccefc3a` (2 failed, 2 passed): duplicate alias did not raise and narrowed alias returned success. Normalize every job once using the producer's same lexical `os.path.abspath` before receipt creation, identity checks, selection, binding lookup, and transport construction. Symlink resolution semantics remain the producer's existing semantics. Independent re-review follows this repair; no live write or schedule change.

Validation after normalization: 19 focused tests passed; both full suites passed 697 tests with 1 skip (Python 3.11.14: 30.47s; Python 3.13.11: 30.57s). Offline wheel/sdist build and diff whitespace check passed. The two alias regressions now refuse before credentials/writes and leave the map unchanged.


## Postmerge offline correction — October 1

Live PATCH404/empty-canary evidence is retained in `2026-10-01_synthetic_markdown_canary_failed.md`. Google v2 files.update documents PUT for the same upload URI. The former MockTransport accepted PATCH and therefore missed this defect. Tightening the service fixture to reject non-PUT methods reproduced one failing upload test on landed source (five other transport tests passed). The correction changes only the media method and its documentation; URL, file identity, If-Match, MIME, privacy preflight, recovery and no-retry guards remain. Prior review/test evidence is historical and unchanged; correction independent review and live qualification remain pending. No live request, enrollment, credentials, installed runtime or scheduler change accompanies this correction.

Offline correction validation: 698 passed / 1 skipped on Python 3.11 (31.53s) and 3.13 (31.64s); seven focused transport tests pass; diff check passes. Wheel/sdist build remains unverified in this continuation: existing interpreters lack `build`, and Python 3.13 also lacks `hatchling`; no dependency installation attempted. Independent review remains pending the exact postmerge-audit instruction and successor authorization; original five attempts retained, audit6/repair7 requires bounded round7 extension. Canary can be reused after clearance only if fresh same-ID privacy/account/parent/empty-byte/ETag checks still pass, followed by cleared PUT enforcement proof. This is a conditional reuse plan, not current live qualification.
