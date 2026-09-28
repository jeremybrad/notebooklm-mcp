# WOR-189 / WOR-191 — first scheduled publication and source observation

The agreed one-time follow-up inspected the first 02:00 America/Denver run after
the [approved cutover](2026-09-27_wor189_nightly_cutover.md). The observer used
read-only job/log/receipt/map checks and did not invoke publication or repair.
Jeremy's subsequent continuation completed the separate C021 source observation
and recorded it through the existing guarded map writer.

## First calendar-triggered result

At the 2026-09-28 08:15 UTC check, `gui/501/com.notebooklm-mcp.refresh` reported
one run, not running, and last exit code 0. The activation baseline had zero runs.
The installed calendar remained 02:00 local with RunAtLoad and KeepAlive false.
The publication log contained the matching terminal success; its error log was
empty. Receipt:

`publication-9b9cde86c6c9400da5a70e950ce2f0ba.json`

- Started `2026-09-28T08:00:07.476906Z`; completed `08:00:15.520381Z`.
- Status success, exit code 0, two remote verifications; both pending fields null.
- Receipt SHA-256 `7ff0b43aaabe8e4f19d0bafe905112d245d5f9460be03da8eca73dfcc626c509`.
- Approved manifest SHA-256 `836481cb63fa9a8e27b977d5614ef8f2cbddae86789e7a216dd5b4bbd7bd7f1c`.
- C014 was unchanged and remotely verified at source commit
  `00524380f7dffb74a21ea3c1b4a206071fa3d555`, bundle
  `d1737541ff2dece5834656931fd1e5878896310a0697beb995fc9d6e4219a384`.
- C021 was replaced and remotely verified at source commit
  `b9ea5f75caad5edcba65f0de58df9c456399f055`, bundle
  `7313a800ee7ec5bc8de9e411597c94addddbcd54962846d3bcb146d06e161056`.

This is distinct from manual background acceptance run
`df3ea4841d39445eb264e06edf7ce4e5`, completed before schedule activation.
The stdout/receipt identities, fetched-origin preflight, manifest hash and
current map hashes were checked together. No additional run or retry occurred.
[Owning result on WOR-189](https://linear.app/macromancer/issue/WOR-189#comment-ad1d3818-0682-4e68-82df-b4ce33bbc587)
is crosslinked from WOR-188. The one-time observer is complete.

## NotebookLM source observation

The existing C021 notebook was opened at 08:26:00.603Z; opening its existing
source at 08:26:22.695Z displayed `Checking freshness...`. The actual source
viewer at 08:26:38.327Z contained these published Git blob revisions:

| Selected document | Git blob |
|---|---|
| `docs/doc_refresh/PUBLICATION_STATE.md` | `82faae34b92e766ff83322115d098b3e9efb9a62` |
| `docs/doc_refresh/PUBLISHER.md` | `814de811ab1ac41033e349f9319156e293f99861` |
| `docs/doc_refresh/SOURCE_BUNDLES.md` | `249f3781e6d6e67ef1f705ef8f2577ceb0fb7fcb` |

All three path/blob/content-hash markers matched the immutable bundle built at
the scheduled commit. The complete rendered source also matched after whitespace
normalization and removing the viewer-only `Tab 1` label. This is not a raw
byte-equality claim. No manual Sync, import, new query or generation was submitted.
Old saved chat answers were not used as current-source evidence.

**Limit:** the source was current after opening. The visible freshness check
means this observation does not isolate unattended ingestion. It does not
establish new citations or regenerate any prior artifact. The previously
verified source/citation and artifact evidence remains version-bound.

At 08:29:22Z, `record_observation` changed only C021's source observation in
`~/.config/notebooklm-mcp/publication-map.yaml`. Full semantic comparison verified
that C014, both Docs bindings, pending fields and all artifact records were
preserved. Map SHA-256 before/after:

- `6ac770bb0f20517d5cc5b7de41b35ba000a1e3bc97ea870dcc1c211c5803d047`
- `903361d070e63cf8f491e6a65adf6ec065422682d0aa565f20ac3ccc4df48d5a`

The map now records both approved source observations at the receipt's hashes.
C014 retains its two [corrected artifact observations](2026-09-27_wor191_artifact_corrections.md),
including the audio's limitations; C021 has no artifact observation. The map
update made no cloud calls. Private source text, screenshot, before-map and
comparison results remain local; the map observation points to their evidence.
[Concise source result on WOR-189](https://linear.app/macromancer/issue/WOR-189#comment-3b844b46-6825-4bf0-8bc9-bc4921d3bb9c)
is crosslinked from WOR-188.

## Boundaries and validation

The active source selection, destination IDs, credentials, installed runtime,
scheduler, old backups and separate primer mirror did not change during these
observations. C001 remains outside the approved cohort. The canonical runtime
remains at the assessed PR23 code; these later changes are documentation only.
Future publication can advance Docs beyond these observations and requires its
own evidence. Credential lifetime and a permanent alert service are not proven.

The existing offline builder reproduced the exact published bundle and selected
three approved paths. Source comparison and the guarded map before/after check
passed. Receipt/relative-link/whitespace checks and independent review apply to
the documentation PR separately; no runtime-code change or new runtime test is
claimed here. Updated files are this receipt, CHANGELOG.md, CLAUDE.md and the
operator guide PUBLISHER.md. Jeremy remains sole merger.
