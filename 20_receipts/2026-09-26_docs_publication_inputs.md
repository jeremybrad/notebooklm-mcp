# WOR-788 / WOR-789: offline publication input safeguards

Jeremy asked Betty to continue the NotebookLM work after merging PR #5. This
bounded follow-up implements the three owned prerequisites deferred from the
completed synthetic pilot PR #7. It changes the supported input contract of the
existing offline helpers, not runtime topology or live transport.

Known: PR #5's accepted manifest is on main at
6317b5db57f82a9df0e1302cacb05fb80ccb2011. PR #7 remains merged with five recorded
reservations (four substantive/inference-ambiguous runs and one proven pre-inference
failure), its final Grok result and original finding ledger intact. Its fixed
synthetic-pilot acceptance is complete. This follow-up neither replaces that PR
nor reuses its review as clearance for the new input rules. All three identities
and original severities below are preserved.

- DRIVE-F1 (P3), WOR-788: require explicit SUGGESTIONS_INLINE response metadata
  before parsing either a planning snapshot or a readback. Missing/default,
  unknown and preview modes fail. Existing suggested-marker refusals remain.
- DRIVE-F2 (P2), WOR-789: keep U+000B unsupported and correct the misleading
  stripping rationale. Google supports soft breaks; this adapter deliberately
  supports only LF/TAB among C0 controls. Source CR/CRLF normalization remains.
- DRIVE-F3 (P3), WOR-789: no clear-to-empty publication. Reject empty/whitespace
  body or non-positive/non-integer source count before a plan, even for no-ops.
  Empty source content remains valid because rendering supplies provenance.

Evidence: 26 reproduced failures among 50 targeted cases before the repair;
51 targeted cases pass afterward. Full suite: 268 passed, one filesystem-dependent
skip on Python 3.11 and 3.13; whole-package coverage 34%; wheel and sdist build.
Synthetic request application independently checks UTF-16 operations, readback,
revision conflicts and stable reruns. No Google call was made. An empty-insert API
rejection is not claimed. Red/green logs are retained in the owning Codex task's
work/docs-safeguards directory; exact independent review follows on the PR.

Assumed: future transport uses parse_document for every response; directly
constructing trusted fixture dataclasses supplies no external validation.
Needs verification: account-specific OAuth, live Docs writes, NotebookLM refresh
and generated-artifact freshness remain for the separately authorized canary.
Risk: older callers omitting suggestion-mode metadata now refuse; the only current
callers are updated synthetic fixtures. No source selector, auth, installed
runtime, scheduler, live mapping or canonical checkout was changed. Rollback is
an ordinary revert of this PR before any live adapter adopts its contract.

Files: drive_publication.py, drive_pilot.py, test_drive_publication.py,
DRIVE_PILOT.md, CHANGELOG.md and this receipt. Existing glossary startup tool ran,
but required glossary data was missing/invalid; no governed terminology was inferred.
