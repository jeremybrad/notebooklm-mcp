# WOR-183 five-repository documentation publication

## Authority and scope

Under Jeremy's approved [WOR-183 selected-source rollout](https://linear.app/macromancer/issue/WOR-183/c021-revive-notebooklm-repo-docs-automation),
this receipt records the completed C001/C003/C010 publication, subsequent
NotebookLM source observations and extension of the existing nightly cohort to
five repositories on 2026-09-28. The earlier C014/C021 manual batch is recorded in
[the retained-publication receipt](2026-09-28_wor183_priority_documentation_publication.md)
and merged PR #28. These are separate completed operations.

Jeremy merged the source-documentation PRs before this publication: C001 #193,
C003 #559 and C010 #644. The publisher consumed the exact merged commits below.
It selected two C001 files (`10_docs/OVERVIEW.md`, `40_src/pipeline/README.md`),
four C003 files (`10_docs/ARCHITECTURE.md`, `10_docs/PIPELINE_DOC_CANON.md`,
`10_docs/STAGE_S2_CONTRACT.md`, `10_docs/STAGE_X1_CONTRACT.md`) and three C010
files (`docs/standards/OVERVIEW.md`, `docs/standards/ARCHITECTURE.md`,
`docs/standards/SCHEMAS.md`). Existing C014/C021 source selections were retained.

## Native Docs creation and publication

Each repository's retained bootstrap record reports success, one document
creation, one credential refresh and zero content writes during bootstrap.
Each retained creation response records the native Google Docs MIME type.
Successful guarded transport preflight/readback checked the expected account,
sole ownership and owner-only permissions before binding and again during
publication. Raw permission responses were intentionally not persisted; these
checks are not an independent stored permission snapshot or a global duplicate
search. The new Docs were bound to the corresponding existing restricted
NotebookLM destinations before content publication. Existing C014/C021
document identities and source observations were preserved.

Batch `301e81842c2141c3bc74cefdbb5c8e11` ran from
2026-09-28T21:18:37.012120Z to 21:23:17.300730Z. Its terminal receipt reports
exit 0, `status: success`, `remote_verified_count: 3`, and successful text
replacement with remote readback for every item:

| Repository | Exact merged source commit | Verified bundle SHA-256 |
|---|---|---|
| C001 | `b8e6fef816d173f818e240aa7e881a19a76e3e4b` | `c112f3d5baeab53fbc36bc2a4a6dacfa904707ae264af519ddae4f370154cce5` |
| C003 | `47ef9ca2233ed988067d44050022f2cd37d743f5` | `8ec99201cffd3e96441ff41f82136c63041a124cffa200802cc9da8021c8c2ff` |
| C010 | `64d206c1afc21083ccd6864943577abc8129f871` | `9f42c3337415c827918771ae5014cf58a0caff35d771ec9e678f28f56db2a483` |

The terminal JSON is retained as
`~/.config/notebooklm-mcp/publication-receipts/publication-301e81842c2141c3bc74cefdbb5c8e11.json`,
SHA-256 `83ee34e122b4623e9c498dac00e0371f3a2dd99d4aa4ccab8e59f93a73f0727b`.
Its NotebookLM attestation fields were false at batch completion; the later
source observations below are the separate evidence for that layer.

## NotebookLM source observations

At approximately 21:26:33 UTC, each retained comparison record reports a complete
source-text match to its published bundle after removing the viewer-only
`Tab 1` wrapper and whitespace. Only the managed source was selected in each
notebook; legacy sources were retained and no artifact was generated.

| Repository | Normalized characters | Normalized text SHA-256 |
|---|---:|---|
| C001 | 14,211 | `7ac48a1197242f108326067340ce6413e01dcb9bc4389d3a0ac447fca909f22f` |
| C003 | 41,010 | `098bfb2dc6c8e0c56d745cc59046e8a1d1655502dbff4b345d3fd0a9e41e6bd9` |
| C010 | 15,488 | `a97cbe20abe0948ffcd512a0554efbd8f7c1951e8f40667fbbe778e297e53e5b` |

These observations followed opening/importing the sources. They do not establish
unattended NotebookLM ingestion, future source freshness or freshness of earlier
chat answers and artifacts.

## Existing nightly cohort extended

At 21:27:18.175232 UTC, the existing configuration was activated in the order
`publication-provider.json`, `publication-sources.yaml`, then
`publication-cohort.json`. The resulting cohort is C014, C021, C001, C003 and
C010; the existing two-repository selections and privacy exclusions are retained.

| Configuration | Activated SHA-256 |
|---|---|
| `publication-provider.json` | `78c60ac59bbffe25a7534258b80f9eb5cef18ca9f24837dbf9a4c0ab12c0db95` |
| `publication-sources.yaml` | `f56835ad7a55e08a569a6722599217c803b961ae854dcf3158f4f03c78c19ff1` |
| `publication-cohort.json` | `4fc4e1b423b6175e81ca7ba1dcfc6cd195096154aa93887c8c37c775c57c2ee3` |

The existing `com.notebooklm-mcp.refresh` schedule remains 02:00
America/Denver. The activation observation reported one prior run, last exit 0
and no process running. That prior run is not a scheduled acceptance of the new
five-repository cohort. The installed plist remained SHA-256
`3a70fcde7844625ddc967742d98b295a239f5f289264ce084366e42faddfe125`,
with `RunAtLoad: false` and `KeepAlive: false`; its runtime program and
configuration paths were unchanged. No new scheduler or runtime installation
occurred.

The subsequent active-cohort `plan --fetch` completed with exit 0 from
21:28:16.236666 to 21:32:42.954983 UTC. Batch
`4562ccf1f63941ce8d8449226e0eb9de` resolved fetched origins and the activated
manifest, reporting all five repositories successful and locally unchanged,
with source counts 2, 3, 2, 4 and 3 for C014, C021, C001, C003 and C010.
It assessed C014 at `00524380f7dffb74a21ea3c1b4a206071fa3d555`, C021 at
`ef87b069e100cb3d1595a1e1afacd55db249404a`, and the three merged commits above.
Its verification was **offline**, with `remote_verified_count: 0`; it was no
additional cloud check, publication or scheduled run. The terminal JSON is
`publication-4562ccf1f63941ce8d8449226e0eb9de.json` in the existing local
publication-receipts directory.

Jeremy separately approved normalization of the stored C001/C010 origin URLs.
The retained 19:19:49 UTC observation records SSH-form stored URLs changed to
the same repositories' HTTPS URLs; effective fetch/push destinations were already
those HTTPS URLs and remained unchanged. No checkout migration followed.

## Retained evidence and rollback anchors

Private operational metadata remains under
`~/LocalWork/Codex/c021-rollout/priority-repos-20260928/`:

- Each of `C001_mission-control/`, `C003_sadb_canonical/` and `C010_standards/`
  contains `bootstrap-result.json`, `created-document.json`, `destination.json`
  and `notebook-source-verification.json`. The comparison records point to complete
  local observed text and screenshots; those contents are not copied here.
- `origin-normalization-evidence.json` records the approved URL changes.
- `cohort-activation-evidence.json` records activation hashes and rollback paths.
- `publication-provider.json.before`, `publication-sources.yaml.before` and
  `publication-cohort.json.before` retain the pre-extension configuration bytes.
  `publication-map.yaml.before` is retained as historical evidence; it predates
  the completed publication and source observations and is not current state.

No rollback, document/source deletion, credential enrollment/change, runtime
installation or migration was performed by this receipt follow-up. The branch
adds only this receipt and a changelog prepend; it changes no publisher behavior,
configuration or schedule. Jeremy remains sole merger.
