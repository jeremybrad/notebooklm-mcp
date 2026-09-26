# Stable Drive design and synthetic offline pilot

Date: 2026-09-25. Work: WOR-183 / preparatory WOR-187 and WOR-188.

## Authority and scope

Jeremy replied “Yes, I approve, thank you!” to Betty's request to approve the
Drive-based design and offline pilot direction in C021. Approval observed
2026-09-25 21:23 UTC (not asserted message timestamp), task
01a0d946-629f-7580-9cdb-972daf9c3ab6. Scope excludes live upload, auth change,
notebook retirement and scheduler activation. PR #5's explicit privacy repair
stop remains separate; its source-selection files/history are untouched.

The approved future path uses stable native Google Docs and linked NotebookLM
sources, superseding the earlier default of MCP text replacement / notebook
retirement for nightly publication. The existing C021 contract remains the
sole source-selection authority. C010 remains the primer generator.

## Change

Added pure in-memory bundle rendering, a narrow complete-response Google Docs
parser, revision-bound request planning and exact text readback checks. Added
an executable fixed synthetic pilot, tests and the design/runbook. No filesystem
source reader, network transport, credentials, mapping writes or scheduling.

Files: `src/notebooklm_mcp/doc_refresh/drive_publication.py`, `drive_pilot.py`,
`tests/test_drive_publication.py`, `docs/doc_refresh/DRIVE_PILOT.md`, this receipt,
`CHANGELOG.md`, and the capability-audit pointer to the superseding decision.

## Evidence

- Baseline: fetched origin/main ae8ac4fa9eb1d38b9bde280f928b07b49e244b04.
- Isolated branch codex/drive-offline-pilot; shared main not edited.
- Initial RED: missing preparation module; next RED: missing fixed pilot.
- GREEN: 90 offline tests passed (22 new cases), including request application
  with UTF-16 surrogate pairs, final newline preservation, no-change repeat,
  concurrent revision refusal, remote text conflict and wrong destination,
  malformed/structured Docs responses and prohibited pilot file/network I/O.
- Initial receipt reports local tests only. Independent review, final checks
  and exact pushed head/base are recorded in the PR's Current status/accounting.
- Official Docs reference checked for requiredRevisionId, tabId, UTF-16 ranges,
  undeletable final newline and stripped characters; links are in DRIVE_PILOT.md.

## Limits and rollback

Synthetic readback proves local behavior only. No Google or NotebookLM write was
performed; no source-safety or account freshness claim is made. Real-repository
acceptance and full WOR-187/188 completion remain pending. Rollback removes this
unwired preparation code; there is no runtime/data state to undo. No deployment,
merge, review clearance or PR #5 continuation is supplied by this receipt.
