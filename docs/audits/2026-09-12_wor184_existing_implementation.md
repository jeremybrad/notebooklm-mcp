# WOR-184 — Existing C021 NotebookLM implementation audit

**Date:** 2026-09-12
**Issue:** WOR-184
**Audited HEAD:** `de8169fe84d679d54621556a6fafcb1a1548e0d1` (`origin/main`)
**Remote:** `jeremybrad/notebooklm-mcp` (C010 `github_repo` override; repo_id `C021_notebooklm-mcp`)
**Auditor host:** Grok Build Linux sandbox (not Jeremy's Mac)
**Live NotebookLM / Chrome / launchd:** not present here

This is a source-inventory audit of the hosted clone plus what this sandbox
could execute. It is **not** proof of Jeremy's local runtime.

## Verdict

**Reuse the existing package. Do not rebuild the MCP server or API client.**

The repo already contains a 31-tool FastMCP server, a reverse-engineered
batchexecute client, cookie auth, a doc-refresh pipeline with a YAML
canonical-docs manifest, and an offline unit suite that passes. The gaps
that remain are schema/exclusion formality (WOR-186), host-local auth
proof, and unattended nightly soak — none of those require a rewrite.

## What exists (source)

| Surface | Path | Size | Role |
|---|---|---|---|
| MCP server | `src/notebooklm_mcp/server.py` | 1846 lines, 31 `@mcp.tool()` | Tool surface |
| API client | `src/notebooklm_mcp/api_client.py` | 2773 lines | Reverse-engineered NotebookLM API |
| Auth cache | `src/notebooklm_mcp/auth.py` | 220 lines | `~/.notebooklm-mcp/auth.json` |
| Auth CLI | `src/notebooklm_mcp/auth_cli.py` | 703 lines | `notebooklm-mcp-auth` (Chrome) |
| Sync CLI | `src/notebooklm_mcp/sync_cli.py` | 981 lines | `notebooklm-sync` |
| Doc refresh | `src/notebooklm_mcp/doc_refresh/` | 8 modules | Discovery, hashing, manifest, validate, sync, artifacts, runner |
| Canonical docs YAML | `src/notebooklm_mcp/doc_refresh/canonical_docs.yaml` | v0.2.0, 2026-01-10 | Tier 1/2/3 document list — **not a JSON Schema, no exclusions field** |
| Primer gen | `src/notebooklm_mcp/primer_gen/` | present | Marked **DEPRECATED** in `CLAUDE.md` (moved to C010) |
| Nightly PRD | `10_docs/prds/PRD-NR01_nightly_notebook_refresh.md` | — | Implemented in source; soak still pending |
| Scheduler scripts | `00_run/install_refresh_schedule.sh` | — | launchd helpers; install is host work |
| Tests | `tests/` | 4 files, 887 lines | Offline unit tests; FastMCP stubbed |

Console scripts in `pyproject.toml`: `notebooklm-mcp`, `notebooklm-mcp-auth`,
`notebooklm-sync`, `generate-project-primer`, `doc-refresh`.

Package: `notebooklm-mcp-server` 0.1.0, `requires-python >=3.11`, FastMCP
pinned `3.2.4`. Local pin `.python-version` is 3.13 (dev convenience only).
Upstream origin is jacob-bd/notebooklm-mcp-cli; this remote is Jeremy's fork
`jeremybrad/notebooklm-mcp`.

### MCP tools registered (31)

`notebook_list`, `notebook_create`, `notebook_get`, `notebook_describe`,
`source_describe`, `notebook_add_url`, `notebook_add_text`,
`notebook_add_drive`, `notebook_query`, `notebook_delete`, `notebook_rename`,
`chat_configure`, `source_list_drive`, `source_sync_drive`, `source_delete`,
`research_start`, `research_status`, `research_import`,
`audio_overview_create`, `video_overview_create`, `studio_status`,
`studio_delete`, `infographic_create`, `slide_deck_create`, `report_create`,
`flashcards_create`, `quiz_create`, `data_table_create`, `mind_map_create`,
`mind_map_list`, `save_auth_tokens`.

No `@mcp.tool` stub returns `NotImplemented`. Tools call `api_client` /
auth helpers. That is implementation, not live proof.

## What works by evidence (this sandbox)

| Claim | Evidence | Not evidence of |
|---|---|---|
| Offline unit suite is green | `PYTHONPATH=src python -m pytest tests` → **53 passed** in 3.25s on Python 3.11 (C019 venv, FastMCP stubbed) | Live NotebookLM, Jeremy's Mac, cookies |
| Cookie header parsing | `tests/test_server_tools.py` (`save_auth_tokens` with/without `; ` spacing; Chrome export `=` values) | Token validity against Google |
| Doc-refresh manifest loads | `tests/test_doc_refresh.py::TestManifest::test_load_manifest` | That Jeremy's `notebook_map.yaml` exists |
| Hashing is deterministic | `TestHashing` | That nightly sync ran |
| Sync safety unit tests exist | CHANGELOG + `test_doc_refresh.py` (add-before-delete, artifact ID polling) | Zero-orphan soak on a real notebook |
| CI workflow exists | `.github/workflows/ci.yml` referenced in CHANGELOG | This sandbox did not re-run GitHub Actions |

Last recorded **live** MCP attempt in-repo:
`docs/receipts/2026-01-03_mcp_verification_attempt.md` — `notebook_list`
returned 0, `notebook_get` null, `notebook_create` failed (wrong cached
Google session). That is historical failure evidence, not a 2026-09-12
runtime result.

## What remains aspirational / unproven here

1. **Live MCP against notebooklm.google.com.** No cookies, no Chrome, no
   `~/.notebooklm-mcp/auth.json` on this host. README "Tested with Pro/free
   tier" is upstream/operator claim, not reproduced.
2. **Jeremy's installed tool.** `uv tool install notebooklm-mcp-server` was
   not run; PATH has no `notebooklm-mcp`.
3. **Nightly soak (PRD-NR01).** Status is "Implemented … orphan criterion
   still pending". ROADMAP item 1 still asks whether remaining artifact
   timeouts are acceptable. `refresh.log` / `sync_receipts/` from the Mac
   are not in this clone.
4. **launchd installation.** Scripts exist; this Linux sandbox cannot prove
   they are loaded on Jeremy's Mac. User instruction forbids scheduler
   installation here.
5. **Free-tier rate limits / `bl` build-label freshness.** Documented in
   `docs/KNOWN_ISSUES.md`; not measured.
6. **Canonical-docs contract formality.** `canonical_docs.yaml` is a hand
   YAML list. There is no JSON Schema, no `exclusions` collection, no
   per-file metadata envelope, no representative synthetic repo fixtures
   beyond temp dirs inside `test_doc_refresh.py`. That is the WOR-186 gap.
7. **primer_gen** is still in the tree and still a console script, while
   `CLAUDE.md` says it moved to C010. Treat as leftover, not a product
   surface to extend.

## Local / machine evidence that is unavailable

State these as **absent**, not "probably present on the Mac":

| Evidence | Status in this sandbox |
|---|---|
| `~/.notebooklm-mcp/auth.json` | missing |
| `~/.notebooklm-mcp/chrome-profile` | missing |
| `~/.config/notebooklm-mcp/notebook_map.yaml` | missing |
| Chrome / Chromium binary | not on PATH |
| launchd / macOS | Linux sandbox |
| Jeremy's SyncedProjects checkout + nightly logs | not mounted |
| Google cookies | only `cookies.example.txt` (template) |
| Network calls to notebooklm.google.com | not attempted (out of scope) |
| `uv tool` install of this package | not present |

A green clone + 53 unit tests **does not** mean Jeremy's Claude Code MCP
connection works.

## Reuse vs rebuild

| Option | Recommendation | Why |
|---|---|---|
| Rebuild MCP server/client | **No** | 4.6k lines of reverse-engineered API + 31 tools already exist; rewrite would reintroduce `bl`/cookie fragility without new evidence |
| Reuse server/auth/sync as-is | **Yes** | Source is complete; live proof is a host concern |
| Formalize the documentation source manifest | **Yes — WOR-186** | YAML producer exists; schema, exclusions, metadata, synthetic examples do not |
| Promote docs-only smoke ladder to `make smoke` | Later, host-only | Requires valid auth and a known notebook |
| Delete primer_gen | Optional cleanup, not blocking | Deprecated pointer; do not use it for WOR-186 |

## Implementation map (follow-on)

### WOR-186 — documentation source manifest (authorized next)

Reuse `src/notebooklm_mcp/doc_refresh/canonical_docs.yaml` + `manifest.py` +
`models.py` as the **producer**. Add, without live upload:

1. **JSON Schema** (draft 2020-12) for the canonical-docs document:
   `schema`/`version`, `tiers`, per-document `path`, `purpose`,
   `must_exist`, `stub_allowed`, `is_directory`, `scan_pattern`,
   `alternate_names`, `validation` rule ids.
2. **Testable exclusions:** an `exclusions` (or equivalent) list with
   glob/path rules; tests that a matching path is omitted from discovery
   and that a non-matching authorized doc is still included.
3. **Metadata:** schema version, last_updated, optional content-hash of
   the manifest bytes; discovery output already has 12-char SHA prefix
   per file (`models.DocItem.content_hash`) — keep that, do not invent a
   second hash scheme.
4. **Representative synthetic fixtures:** small fake repos covering
   simple / complex / kitted tiers plus one exclusion hit. Use temp
   trees; do **not** point at Jeremy's SyncedProjects or C017 live docs
   as the only fixture.
5. **Stop lines:** no `notebook_add_*`, no Drive, no `doc-refresh --apply`
   against a real notebook, no scheduler install, no cookie writes.

### Out of this issue (held)

- Merges
- Runtime activation / MCP registration
- Cookie extraction
- Nightly soak closeout
- Official-API wait (OPEN_QUESTIONS)

## Sources consulted

- `pyproject.toml`, `META.yaml`, `CLAUDE.md`, `README.md`, `ROADMAP.md`
- `src/notebooklm_mcp/{server,api_client,auth,auth_cli,sync_cli}.py`
- `src/notebooklm_mcp/doc_refresh/*`
- `tests/test_{server_tools,doc_refresh,cli_helpers,primer_gen}.py`
- `docs/KNOWN_ISSUES.md`, `docs/NOTEBOOKLM_MCP_TOOL_AUDIT.md` (stale 2026-01-03)
- `docs/receipts/2026-01-03_mcp_verification_attempt.md`
- `10_docs/prds/PRD-NR01_nightly_notebook_refresh.md`
- C010 `registry/repos.yaml` entry `C021_notebooklm-mcp`
