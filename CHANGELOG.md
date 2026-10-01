## 2026-10-01

- Add explicit individual original-Markdown publication with stable per-path bindings, exact readback and pending recovery (WOR-851); live qualification/enrollment remain separate.

## 2026-09-28

- **docs(receipt): five-repository documentation publication recorded** —
  WOR-183: record merged C001/C003/C010 publication, complete NotebookLM source
  observations and extension of the existing 02:00 cohort to five repositories.
  The expanded cohort has no new scheduled-run acceptance in this receipt.
  See `20_receipts/2026-09-28_wor183_five_repository_publication.md`.

## 2026-09-28

- **docs(receipt): retained documentation refreshed for priority rollout** —
  WOR-183: record successful C014 remote verification, C021 publication and
  complete NotebookLM source comparison after opening. Additional repository
  enrollment is outside this receipt's execution scope.
  See `20_receipts/2026-09-28_wor183_priority_documentation_publication.md`.

## 2026-09-28

- **docs(operations): first scheduled publication accepted** — Record the first
  successful C014/C021 calendar run and C021 source verification after opening,
  with a version-bound local observation and explicit ingestion limits.
  See `20_receipts/2026-09-28_wor189_first_scheduled_publication.md`.

## 2026-09-27

- **docs(receipt): C014 artifact corrections** — WOR-191: record the approved
  one-image/one-audio extension, original audio findings, verified source/access,
  corrected diagram and qualified audio acceptance with local attestations.
  Originals retained; see `20_receipts/2026-09-27_wor191_artifact_corrections.md`.

# Changelog

All notable changes to NotebookLM MCP Server are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Version numbers in pyproject.toml (no git tags).

## [Unreleased]

### Added
- WOR-189: explicit, manifest-pinned multi-repository cohort preflight for the
  existing publisher. Offline planning reports unverified ref freshness; live
  cohort publication requires successful fetches and fixed commit inputs, with
  all configured source/destination checks before credential access. No scheduler
  installation, enrollment, credential change or cloud publication is included.
- WOR-188: explicit Google Desktop OAuth enrollment/renewal and refresh-to-lease
  provider for the existing documentation publisher. Uses one selected macOS
  login-Keychain item, bounded PKCE loopback consent, pinned account/client and
  destinations, fixed redacted failures and synthetic tests. Adds `repo-doc-auth`
  and `repo-doc-publish --credentials-config`; offline commands stay credential-free.
  No live credentials, host acceptance, uploads, installation or scheduling changes.

### Fixed
- WOR-788 / WOR-789: require explicit inline-suggestions Docs responses for
  planning/readback and reject empty or sourceless publication bundles. Document
  intentional U+000B refusal accurately; preserve the three PR #7 review findings.
  Offline helpers only; no live transport or scheduling activation.

### Added
- WOR-187 offline `repo-doc-bundle` CLI: one-repo/batch manifest selection at
  pinned Git revisions, verified blob provenance, deterministic Markdown,
  content-addressed local artifacts and receipts. No live publication or scheduling.
- WOR-186 documentation source manifest: JSON Schema draft 2020-12 for
  `canonical_docs.yaml`, default privacy/build exclusions with fail-closed
  path and symlink containment, `extra_docs` consumption, AGENTS.md and
  PROJECT_PRIMER.md includes, and synthetic three-repo fixtures.
  Schema id `c021.canonical_docs.v1`. Adds runtime `jsonschema>=4.18`.
- WOR-183 / WOR-187 / WOR-188: approved stable Google Docs publication design and
  synthetic offline bundle/update/readback pilot. Real source selection, uploads
  and scheduler integration remain gated; see `docs/doc_refresh/DRIVE_PILOT.md`.
- WOR-185 capability matrix for NotebookLM / Gemini notebooks / Drive / MCP
  refresh paths (`docs/audits/2026-09-12_wor185_capability_matrix.md` plus
  `docs/audits/wor185_capability_matrix.json`). Preferred path is the
  existing consumer MCP write surface; Enterprise REST and Gemini UI sync
  are documented and rejected as the C021 default. No live Google calls.
- WOR-184 existing-implementation audit: reuse (not rebuild) the 31-tool MCP
  server and doc-refresh YAML producer; record unavailable host evidence and
  the WOR-186 schema/exclusions gap
  (`docs/audits/2026-09-12_wor184_existing_implementation.md`).
- Nightly/manual CI runs now upload `pytest.xml` and `coverage.xml` artifacts for failure review.
- Helper regression tests now cover auth/sync/server parsing plus receipt and refresh-log helpers.
- Nightly documentation refresh automation (PRD-NR01) with launchd scheduling helpers in
  `00_run/install_refresh_schedule.sh` and `00_run/uninstall_refresh_schedule.sh`, plus `Makefile` targets
  `install-schedule`/`uninstall-schedule`.
- CI workflow (`.github/workflows/ci.yml`) to run tests, coverage report, and package build on push/PR.
- `doc-refresh` console script entrypoint for the doc-refresh runner.
- Regression tests for sync safety, artifact completion polling, major-version detection, and cookie parsing.
- `notebooklm-sync --all --apply --changed-only` mode for automated nightly updates (runs only changed repos by default).
- Project-scoped `.mcp.json` declaring the `notebooklm-mcp` server (PATH-portable `command`), so the server is discoverable to contributors and scoped to this repo rather than relying on a global registration.

### Infrastructure
- Tracked `.stignore` from canonical C010 template for Syncthing exclusion hygiene; re-aligned to the C010 Wave 1 canonical template.
- Deployed cross-platform LF normalization via `.gitattributes` from C010 template.
- Pinned local Python toolchain to 3.13 via `.python-version` (development convenience only; published `requires-python` remains `>=3.11`).

### Changed
- **CLAUDE.md** — Trimmed from 323 to 202 lines (~936 token savings) by extracting auth section to `docs/AUTHENTICATION.md` pointer, compressing redundant blocks, and consolidating doc references.
- **CLAUDE.md** — Further trimmed from 202 to 101 lines (~1,200 total token savings) via three optimization passes: architecture tree update, MCP tools table replaced with server.py pointer, sync CLI and ops sections replaced with docs/CLI.md pointer, redundant auth recovery collapsed, boilerplate removed.
- **CLAUDE.md** — Trimmed from 101 to 97 lines: removed a generic "always show current state" instruction (the `confirm=True` tool mechanism already enforces it) and the redundant License section (the `LICENSE` file is the source of truth).

- `PROJECT_PRIMER.md` operator auth and scheduled doc-sync guidance were refreshed.
- Doc-refresh runtime notebook map now defaults to `~/.config/notebooklm-mcp/notebook_map.yaml`.
- Added a packaged `notebook_map.template.yaml` bootstrap file instead of bundling mutable runtime state.
- Security and code-tour docs updated to reflect persisted local doc-refresh state.

### Fixed
- Preserve required-document flags across duplicate tier/override paths and
  classify repository tiers from the final document set, including extras.
- Reject repository-root case/Unicode aliases and root symlinks before override
  lookup, preserving exclusions and supported ancestor aliases. Keep malformed
  manifest diagnostics type-safe when invalid keys and values coexist.
- Reject non-string repository override names during manifest validation so YAML
  numeric, boolean or null keys cannot silently bypass repository exclusions.
  Quoted numeric and boolean-like repository names remain supported.
- WOR-186: reject duplicate manifest YAML keys and conflicting merges before
  overwritten privacy rules can disappear during parsing.
- WOR-186: honor recursive privacy exclusions at every directory depth; route
  legacy automatic sync and primer source gathering through the shared manifest,
  including optional RELATIONS.yaml and literal automatic CLI file handoff.
- WOR-186: validate supplied manifests before selection, bind provenance hashes
  to captured manifest bytes, retain scans through root ancestor aliases, and
  use literal Git paths for per-document last-touch metadata.
- WOR-186: literal basename exclusions compare resolved filesystem identities
  directly, preserving privacy exclusions beneath bracket-containing directories.
- Doc sync replacement flow now uses a safer add-before-delete order to avoid source loss if replacement fails.
- Artifact completion polling now validates completion against the artifact IDs created in the same run.
- Cookie parsing now handles headers with optional whitespace after `;`.
- Major version bump detection now compares stored `meta_version` with current `META.yaml` version.
- `save_auth_tokens` now parses cookie headers with or without spaces after semicolons.

### Security
- Bumped `fastmcp` from 2.14.2 to 3.2.4 to pick up upstream security fixes.

## [0.1.0] - 2026-01-10

### Added
- **Doc-Refresh Ralph Loop** (v0.3.0):
  - Canonical document discovery (Tier 1/2/3)
  - Hash-based change detection
  - NotebookLM source synchronization with deterministic titles
  - Standard 7 artifact refresh (mind map, briefing doc, study guide, audio, infographic, flashcards, quiz)
  - `--force`, `--artifacts`, `--skip-artifacts` CLI flags
  - Delta-based trigger logic (>15% change or major version bump)

- **MCP Tools** (31 total):
  - Notebook management: `notebook_list`, `notebook_create`, `notebook_get`, `notebook_describe`, `notebook_rename`, `notebook_delete`
  - Source management: `notebook_add_url`, `notebook_add_text`, `notebook_add_drive`, `source_describe`, `source_list_drive`, `source_sync_drive`, `source_delete`
  - Chat: `notebook_query`, `chat_configure`
  - Research: `research_start`, `research_status`, `research_import`
  - Studio: `audio_overview_create`, `video_overview_create`, `infographic_create`, `slide_deck_create`, `report_create`, `flashcards_create`, `quiz_create`, `data_table_create`, `mind_map_create`, `mind_map_list`, `studio_status`, `studio_delete`
  - Auth: `save_auth_tokens`

- **Authentication**:
  - Cookie-based auth with auto-extraction of CSRF token and session ID
  - Token caching in `~/.notebooklm-mcp/`
  - Auto-retry logic for auth token rotation
  - CLI tool `notebooklm-mcp-auth` for Chrome-based extraction

- **Documentation**:
  - Comprehensive CLAUDE.md with session recovery guidance
  - API reference (`docs/API_REFERENCE.md`)
  - Troubleshooting guide (`docs/TROUBLESHOOTING.md`)
  - MCP test plan (`docs/MCP_TEST_PLAN.md`)

### Technical Notes
- Reverse-engineered NotebookLM internal APIs (batchexecute RPC)
- Tested with personal/free tier accounts
- Python >=3.11 required
- FastMCP 2.14.2 for MCP protocol
