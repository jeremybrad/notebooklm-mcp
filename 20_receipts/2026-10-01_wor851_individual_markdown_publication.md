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
