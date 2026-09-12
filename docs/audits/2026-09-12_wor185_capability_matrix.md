# WOR-185 — NotebookLM / Gemini notebooks / Drive / MCP capability matrix

**Date:** 2026-09-12
**Issue:** WOR-185
**Audited HEAD:** `3681e88a5ad0bd633f7497cce4ee9c623f4479cd` (`origin/main`, WOR-184 merge)
**Machine-readable matrix:** [`wor185_capability_matrix.json`](./wor185_capability_matrix.json)
**Live NotebookLM / Drive / Chrome / GCP:** not used. This is a source + public-docs proof.

WOR-184 already chose **reuse, do not rebuild** the existing 31-tool FastMCP
server. This issue answers a different question: *what is the safest current
mechanism for programmatically refreshing NotebookLM sources?* Linear
`blockedBy WOR-184` was stale (WOR-184 is Done and merged). WOR-186's draft
[#5](https://github.com/jeremybrad/notebooklm-mcp/pull/5) is not stacked on
this branch.

## Preferred path

**Reuse the existing consumer MCP write surface** (`existing_mcp_text_sources`).

Refresh git markdown by pasting text sources through `notebook_add_text` /
`doc_refresh.apply_sync_plan`. Replacement is **add the new source, then
delete the old one**. That ordering is already unit-tested offline.

| Role | Path | Why |
|---|---|---|
| Primary | Existing C021 MCP + doc-refresh | Only consumer path with a source-complete create/list/add/delete write surface |
| Freshness complement | Drive-linked sources | Native `check_source_freshness` / `source_sync_drive` for Docs/Slides/Gemini Notes that already live in Drive |
| Fallback | Browser UI playbook | After two failed MCP auth refreshes; never the nightly runner |
| Reject | Official consumer API | No public consumer write API identified in the reviewed first-party docs (2026-09-12) |
| Reject | Gemini Notebook Enterprise API | Official, but a different SKU (GCP project + Enterprise license). Not Jeremy's Gemini Ultra consumer notebooks |
| Reject | Gemini Notebooks UI sync | Bidirectional consumer sync is real; it is not a programmatic write API |

Do **not** wait for an official consumer API. Do **not** switch C021 onto
Enterprise unless Jeremy explicitly chooses that product. Do **not** invent a
second documentation manifest (WOR-186 owns schema/exclusions).

## Capability matrix

Legend: **supported** = first-party or existing C021 source implements it;
**partial** = works with caveats; **unsupported** = no current mechanism.

| Operation | Consumer official API | Enterprise official API | Gemini Notebooks UI sync | Drive-linked sources | Existing MCP | Browser UI fallback |
|---|---|---|---|---|---|---|
| Create notebook | unsupported | supported (`notebooks.create`) | partial (UI) | unsupported | supported (`notebook_create`) | partial (clicks) |
| Add source | unsupported | supported (`sources.batchCreate` / `uploadFile`) | partial (UI) | partial (Drive files only) | supported (`notebook_add_text` / `_url` / `_drive`) | partial (clicks) |
| Replace source | unsupported | partial (delete + create; no update RPC) | unsupported | partial (`source_sync_drive` in place) | partial (add-before-delete for text) | partial (clicks) |
| Delete notebook | unsupported | supported (`notebooks.batchDelete`) | partial (UI) | unsupported | supported (`notebook_delete`, `confirm=True`) | partial (clicks) |
| List notebooks | unsupported | supported (`listRecentlyViewed`) | partial (UI) | unsupported | supported (`notebook_list`) | partial (clicks) |
| Validate source freshness | unsupported | unsupported (not documented) | unsupported | partial (Drive / Gemini Notes) | partial (`source_list_drive` + `check_source_freshness`) | unsupported |

### What "partial" means on the preferred path

- **Replace source:** there is no in-place replace RPC for pasted text. The
  implemented contract is add-new-then-delete-old so a failed add cannot
  leave the notebook empty. `tests/test_doc_refresh.py` already locks that
  order.
- **Freshness:** `api_client.check_source_freshness` is a Drive/Gemini-Notes
  RPC. Pasted markdown and URL sources are static after ingest. Git-doc
  freshness is therefore a **hash comparison in `doc_refresh`**, not a
  NotebookLM-side freshness bit.
- **Live proof:** last in-repo live attempt
  (`docs/receipts/2026-01-03_mcp_verification_attempt.md`) failed because
  cached cookies pointed at the wrong Google session. This sandbox has no
  `~/.notebooklm-mcp/auth.json` and made no Google calls. Source-complete ≠
  operational.

## Candidate paths, tested as far as this host allows

### 1. Direct NotebookLM automation / official API

No public consumer NotebookLM write API was identified in the first-party documentation reviewed on 2026-09-12; this is a bounded research result, not proof that no private interface exists. Google Cloud's
documented REST surface (updated 2026-09-03) is **Gemini Notebook
Enterprise** on Discovery Engine:

- `POST .../notebooks` create
- `GET .../notebooks/{id}` get
- `GET .../notebooks:listRecentlyViewed` list
- `POST .../notebooks:batchDelete` delete
- `POST .../notebooks/{id}/sources:batchCreate` add
- `POST .../sources:uploadFile` upload
- `GET` / `batchDelete` sources

Auth is `gcloud auth print-access-token` against a GCP project. That is not
the Gemini Ultra consumer product WOR-183 named. Enterprise is a valid
future option only if Jeremy wants a Cloud SKU; it is not the C021 default.

### 2. Gemini notebooks sync path

April 2026 bidirectional sync between Gemini Notebooks and NotebookLM is a
**UI product feature** (sources, in-notebook chats, custom instructions).
Studio outputs do not sync. There is no API to create a Gemini notebook,
push a repo bundle, or assert freshness. Using Gemini as a mirror does not
remove the consumer-API gap.

### 3. Google Drive / Docs indirection

Best **native** freshness on the consumer product:

1. Keep the living document in Drive.
2. `notebook_add_drive`.
3. `source_list_drive` → `is_fresh` / `needs_sync`.
4. `source_sync_drive(..., confirm=True)` when stale.

Repo markdown is not a Drive file. A git-to-Drive publisher does not exist
in this repo. Building one would be new scope (auth, MIME, folder mapping,
privacy). **Do not make Drive the primary git-doc path in WOR-188.** Use it
only for documents that already live in Drive.

### 4. Existing MCP wrapper (validated write surface in source)

WOR-184 inventory still holds. The write tools required by this issue exist:

| Operation | MCP tool / client method | Confirm flag |
|---|---|---|
| Create | `notebook_create` / `create_notebook` | no |
| List | `notebook_list` / `list_notebooks` | no |
| Add text / URL / Drive | `notebook_add_text`, `notebook_add_url`, `notebook_add_drive` | no |
| Freshness | `source_list_drive` / `check_source_freshness` | no |
| Sync Drive | `source_sync_drive` / `sync_drive_source` | yes |
| Delete source | `source_delete` / `delete_source` | yes |
| Delete notebook | `notebook_delete` / `delete_notebook` | yes |

`doc_refresh.ensure_notebook` reuses a stored ID or title
`"{repo_key} Documentation"` and only creates when missing. That is **in-place
refresh**, not WOR-183's create-new-then-retire-old lifecycle. Call that out
for WOR-188; do not silently change it here.

Auth is cookie-based. Cookies expire in ~2–4 weeks. `bl` build labels drift.
Those are documented in `docs/KNOWN_ISSUES.md`.

### 5. Browser automation

`docs/NOTEBOOKLM_UI_FALLBACK_PLAYBOOK.md` remains the last-resort prototype.
Guardrail already on file: MCP first; UI only after two failed auth refresh
attempts on a time-sensitive task. Coordinate-click fragility is explicit.
**Not a scheduler.**

## Manual-only gaps (before WOR-188 implementation)

These are **not** optional polish. They are the live surface this research
could not close:

1. Chrome login + cookie extract to `~/.notebooklm-mcp/auth.json`.
2. Cookie rotation every 2–4 weeks.
3. Host install / MCP client registration.
4. `make install-schedule` on Jeremy's Mac (launchd).
5. A successful live `notebook_list` against the Gemini Ultra account.
6. No freshness bit for pasted text / URL sources.
7. No native replace-source RPC for text.
8. No git-to-Drive publisher if Drive freshness is desired for markdown.
9. `ensure_notebook` does not implement create-new-then-retire.
10. Enterprise REST requires a GCP SKU Jeremy has not chosen.
11. Gemini Notebooks sync has no API.
12. Destructive MCP tools require `confirm=True` / `--apply`.

## WOR-188 implementation packet (proposed, not started)

- Implement against **existing MCP + `apply_sync_plan`**.
- Preserve the observed in-place implementation as evidence only. WOR-188 owns the create-new-then-retire adapter and must satisfy its retirement gates; this audit does not downgrade that acceptance.
- For WOR-188 create-new-then-retire, gate old-notebook delete on:
  new notebook exists, source count matches bundle, content hashes match,
  and a read-only `notebook_query` returns a citation. Never delete first.
- Drive sync is optional and only for Drive-native sources.
- Stop lines: no live mutations from this research PR; no second manifest;
  no scheduler install; no cookie writes; no Enterprise client.

## Evidence this sandbox did and did not collect

| Did | Did not |
|---|---|
| Read WOR-184 audit, server.py, api_client.py, notebook_sync.py, AUTHENTICATION, UI fallback, OPEN_QUESTIONS, KNOWN_ISSUES | Call notebooklm.google.com |
| Confirm MCP tool names and confirm flags in source | Read `~/.notebooklm-mcp/auth.json` (absent) |
| Confirm add-before-delete unit tests already exist | Install Chrome, cookies, or launchd |
| Read Google Cloud Enterprise notebook/source API docs (2026-09-03) | Create a GCP project or Enterprise notebook |
| Encode the matrix as JSON + offline tests | Touch WOR-186 files or PR #5 |

## Follow-on

WOR-186 may continue on its own draft. WOR-188 stays blocked until this
issue is **Done** (merged + accepted) **and** WOR-187 is Done. In Review on
this draft is not Done.

## Public-source refresh on the finishing Mac (2026-09-12)

[Google Cloud notebook API documentation](https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks) identifies an Enterprise preview with license/project prerequisites and create/get/recent-list/delete operations. A recent-list endpoint is not an exhaustive inventory guarantee. [Consumer source guidance](https://support.google.com/gemininotebook/answer/16215270) now describes automatic updates for Drive imports, with manual sync available; the existing MCP freshness helpers remain source-level observations, not a live service canary. [Gemini notebook help](https://support.google.com/notebooklm/answer/17003757) search results describe cross-app syncing; opening that page was blocked by Google's browser challenge, so the full page was not revalidated here.

These public reads do not establish authenticated write health. No cookie files, private sources, or Google mutation endpoints were accessed. Authentication, runtime setup and scheduling are activation prerequisites; they do not prevent offline WOR-187 bundle generation or synthetic WOR-188 adapter development. Live upload/retirement and query acceptance still need their named operator authorization and working account access. Cookie lifetime is historical documentation, not a guaranteed rotation interval.
