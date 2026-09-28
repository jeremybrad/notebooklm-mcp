# WOR-191 — bounded C014 artifact corrections

This continues the [original C014 documentation pilot](2026-09-27_c014_notebooklm_pilot.md).
Its original infographic failed editorial checks; the later full transcript-based
audio review also found material source-grounding errors. Both originals remain.

Jeremy approved the concrete combined correction request with **“Approve one of
each”**, recorded 2026-09-28 at 01:29:10 UTC in Codex chat
`01a0e579-1fbc-7fa3-b598-440c3a2d0c7d` and
[WOR-191 decision](https://linear.app/macromancer/issue/WOR-191#comment-696fb7a3-2168-4ca2-b735-e2edf95d02c9).
The extension allows exactly one additional infographic and one additional audio
overview in the existing private C014 notebook, through the signed-in ULTRA
subscription, using its same single source and the prepared briefs. No source
upload, Docs write, deletion, sharing expansion, credential or scheduler action
is included. Generation is separate from quality acceptance.

## Source and submission verification

Before submission, the browser showed the expected account, ULTRA product,
Restricted access, sole expected owner and one selected source. The source pane
contained the same two Git blob revisions and normalized text hashes:

- C014 commit: `00524380f7dffb74a21ea3c1b4a206071fa3d555`.
- Lifecycle blob: `0b61896ae039af8c2442c3a47b7ccb8b2ab5c69a`.
- Architecture blob: `272699fd24b9e09b76bf5b54a898c3fc6a237851`.
- Retained bundle SHA256:
  `d1737541ff2dece5834656931fd1e5878896310a0697beb995fc9d6e4219a384`.

The exact prepared prompts were entered and compared with the displayed text
before each single Generate action. Infographic submission was recorded at
01:31:06Z (English, Landscape, Auto-select style, Standard detail), prompt SHA256
`e951754eabacbcf9625a65aca5aeb44d70623d42bfb6ebdcb1d4ff5595d1341c`.
Audio submission was recorded at 01:31:41Z (English, Deep Dive, Short), prompt
SHA256 `ca8d08ae3555dc9eed62e1a4da60affb454d23eb418039f7c83878532f5f482d`.
Both generating cards were observed at 01:32:34Z. No duplicate was submitted.

## Original audio review

The retained original audio SHA256 remains
`a3f642a3a5c0ebef1906c5a6efd38fde26a06b3551587fd0c4a6f172e81d7f1b`.
Existing faster-whisper 1.2.1 and cached medium weights transcribed the entire
1,393.197-second export locally. The process completed at 01:24:30Z, exit 0,
in 638 seconds, with 535 timestamped segments. Transcript SHA256:
`9870635eb2e00479dd82e71122344ca452e0b2e81460be0470b9a6179857b5fa`.
A cached base model separately corroborated the key wording in A1 and A2, exit 0
in 9.25 seconds. Both children had an allowlisted environment without provider
credentials and verified OS network denial. No installation, model download,
audio upload or model API spend occurred.

Source-grounding findings against the two approved documents:

| ID | Audio time | Finding |
|---|---|---|
| A1 | 03:41–03:52 | Unsupported claim that B1 captures keystroke-level facts. |
| A2 | 06:08–06:43 | Model fallback is presented as guaranteeing output, without the production canonical requirement for LLM narrative and Day at a Glance or the distinction from preserved legacy output. |
| A3 | 11:04–11:12 | A continuously scanning watcher is implied; the source describes a bounded scheduled enrichment pass. |
| A4 | 17:45–18:01 | Remirroring is framed as permission to overwrite the local file, omitting the content-match guard that preserves manually edited destinations. |

The basic source roles, proper-subset rule, partial badge, retained versions,
historical references and quiet-day limitation were supported. The correction
brief preserves them and explicitly includes lock/archive conditions and the
Obsidian content check. The audit is transcript-based, not word-perfect human
listening. LibreSSL compatibility and NumPy extraction warnings are retained
with the results; neither is hidden behind the successful process status.

## Corrected artifact results

Both additional generations completed and were exported once through their
browser Download controls. All four original/corrected cards remain in the
private notebook. Prompt/source attribution matched each prepared correction
brief and the same source. Visible card `aria-labelledby` identifiers supplied
the artifact IDs below; no hidden application state was used.

| Artifact | ID | Export SHA256 |
|---|---|---|
| Daily Journal Assembly Architecture Diagram | `b0eb3dc4-bbd4-4f37-8913-12406e27ac2c` | `a2687f759c6fb8ad5809a65f8816202d237f971e179a27b289d4929db8840d2f` |
| Strict logic for canonical journal pairs | `dd85394d-e870-4b36-8082-ecd64b539c94` | `a2c458ff8b5de6deb304cfb37beb0adcbbf5063190192593538bae1fd89d2d7b` |

The 2,752 × 1,536 infographic is 4,579,349 bytes. Full visual inspection found
the exact S3/B1/C014 labels, explicit incomplete-inventory caveat, separate
writing context, no-fresh-evidence stop, four outputs, JSON → C001 and Markdown
→ Obsidian paths, all five revision conditions, retained versions, unchanged
historical references, separate eligible weekly regeneration, manual-edit
protection and both document paths. It passes the bounded source-grounding
check. The small document icon has decorative `MW` lettering, while its adjacent
label and delivery arrow correctly say Markdown; no additional format is meant.

The 8,793,674-byte audio is stereo AAC, 44,100 Hz, 273.158 seconds (4:33).
The same network-denied local medium model transcribed all 109 segments in
107.59 seconds, exit 0 at 01:43:53Z. Transcript SHA256:
`98ba0c4a256441aae92aae6f6f7f3ad2272b2c0f4764369598ef16f35a063126`.
Full transcript review against the approved bundle found A1–A4 corrected:

- 00:29–01:04: exact evidence products and fresh-evidence test, no keystroke claim.
- 01:20–01:58: ranking fallback is distinguished from canonical publication;
  narrative and Day at a Glance require LLM output; no output guarantee.
- 01:59–03:18: hypothetical late arrival, scheduled enrichment, all revision
  conditions, complete versus locked, retained provenance and capped weeklies.
- 03:20–03:43: the zero-item quiet-day/seven-daily limitation needs an operator.
- 03:44–04:13: correct delivery formats and optional/off-default remirroring
  restricted to absent or known-version destinations; manual edits are skipped.

**Qualified editorial acceptance:** at 02:29–02:33 the host paraphrases the exact
preceding rule as “no new sources can sneak in at all.” That is too broad in
isolation: the rule concerns newly pending sources, not newly arriving evidence.
The exact sentence at 02:23–02:28 and the late-arrival example state the correct
behavior. A second cached base-model check corroborated the wording. Brief
compliments and closing rhetoric also depart from the requested style, and the
audio does not repeat the full revision identifier or explicit inventory caveat.
These are recorded limitations, not erased findings. The audio is accepted as
an explanation alongside the diagram and source documents, not an executable
runbook or current-deployment/feed-census claim. This is transcript-based
executor review, not word-perfect human listening or Jeremy's acceptance.

The existing `record_observation` path added exactly these two immutable
artifact entries to the active `publication-map.yaml`, after checking the
unchanged verified source hash and absence of pending writes. Before/after
comparison verified only the intended artifact entries changed; C021 and all
Docs/source associations were preserved. Each entry points to its local
assessment with the limitations above. The map operation made no cloud calls.

## Evidence and remaining work

Approval, exact prompt intents, private-access/source snapshots, generation
observations, both full review transcripts, corrected exports and process results remain under the
existing `~/LocalWork/Codex/c021-journal-pilot/` evidence directory. Media and
source bodies remain local/private; only this nonsecret receipt and changelog
enter Git. This receipt is based on reviewed PR25's merge
`7315a744820ac73aa595bf8cd2f94065f7ec28f3`.

The first scheduled Google Docs receipt and separate NotebookLM source freshness
remain WOR-189/191 observations. This artifact work does not execute or repair
the publisher, widen the five-file source selection, or enroll C001.
The exact one-additional-generation allowance is consumed for each artifact;
no further generation is implied by the remaining observations.
