# WOR-183 priority documentation publication

## Authority and scope

Jeremy approved the prepared external steps with “I approve please proceed,”
received and recorded on 2026-09-28 at approximately 17:48 UTC. The decision is
[WOR-183 comment b23ac4e9](https://linear.app/macromancer/issue/WOR-183#comment-b23ac4e9-da95-4936-aa92-6a25977ba715).
It covers bounded documentation PRs, guarded independent reviews, and publication
of the selected merged documentation through the existing Google Docs publisher
into existing restricted NotebookLM notebooks. Jeremy remains sole merger and
will create artifacts. WOR-405 migration retains its separate owner and scope.

This receipt records only the retained C014/C021 publication and the source
observations completed through 2026-09-28T17:52:57Z. It does not record C001, C003
or C010 enrollment or publication. Approval is distinct from completed execution.

## Verified retained publication

The runtime remained at `ddc659f574355f9eae9c981ca7967485a0d4ede8`.
Its `src/`, `pyproject.toml` and `uv.lock` are unchanged against current C021
main `72ca91856b12dd1016d44c4298f911dfa95e321f`. No pull or installation occurred.
The existing manifest remained
`836481cb63fa9a8e27b977d5614ef8f2cbddae86789e7a216dd5b4bbd7bd7f1c`.
The publisher consumed exact immutable revisions and these five files:

- C014 at `00524380f7dffb74a21ea3c1b4a206071fa3d555`:
  `10_docs/ARCHITECTURE.md` and
  `10_docs/2026-09-22_wor772_partial_then_revise_lifecycle.md`.
- C021 at `72ca91856b12dd1016d44c4298f911dfa95e321f`:
  `docs/doc_refresh/PUBLICATION_STATE.md`, `docs/doc_refresh/PUBLISHER.md` and
  `docs/doc_refresh/SOURCE_BUNDLES.md`.

Batch `f2e3ae9f3ced4ed682f112cc1cf22b72` ran from
2026-09-28T17:50:14.579701Z to 17:50:23.695672Z and exited 0 with
`status: success`, `remote_verified_count: 2` and both items successful:

| Repository | Action | Verified bundle SHA-256 |
|---|---|---|
| C014 | Unchanged, remote verification | `d1737541ff2dece5834656931fd1e5878896310a0697beb995fc9d6e4219a384` |
| C021 | One text replacement and exact readback | `d9d815af6bfae54f8ef3ab6c29697798ab925568ab864d129c14c3b9f8b6c351` |

The terminal receipt is under the existing local
`~/.config/notebooklm-mcp/publication-receipts/` directory as
`publication-f2e3ae9f3ced4ed682f112cc1cf22b72.json`. Existing Doc identities,
notebook bindings, credentials, cohort, source manifest and schedule were retained.
This was an explicit manual publication, not an additional calendar-run claim.

## Separate NotebookLM source evidence

Opening C021's existing source displayed a freshness check. Its complete rendered
source text then matched the exact published bundle after removing whitespace
and the viewer-only `Tab 1` prefix: 26,983 normalized characters, SHA-256
`5e402eb0b1e64903fb54064560d2ba7b31693410c97490fbcb6d49da20521369`.
No manual Sync was clicked. The existing source observation was updated for that
verified bundle using the publication-state library.

C014's unchanged source had already passed a whole-source comparison against
this same immutable bundle earlier in this continuation. Its prior same-version
source and artifact observations remain. C021 has no artifact observation.
These are observations after opening; they do not establish unattended ingestion.
Earlier chat answers and generated artifacts can retain older source claims.
No new artifact was generated.

Local comparison records and the inspected selection are under
`~/LocalWork/Codex/c021-rollout/priority-repos-20260928/`:
`c014-source-verification.json`, `c021-source-verification.json`,
`existing-cohort-revisions.json` and the exact bundle files. The C021 comparison
record points to the source screenshot and the complete observed text is retained
alongside it in local visualization evidence. No credential or native response
body is included in this Git receipt.

## Scope boundary and follow-up

WOR-183 and the separate C001, C003 and C010 documentation PRs track the broader
rollout. Each additional repository needs assessed merged documentation,
publication/enrollment and complete source verification. The approved plan
retains existing notebooks and legacy sources and selects only refreshed managed
sources for future artifacts. At the end of the operations recorded here, the
prepared broader manifest had not replaced the active two-repository manifest.
No new scheduler, permission change or migration action occurred in this batch.
