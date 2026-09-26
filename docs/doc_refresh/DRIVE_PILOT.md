# Stable Drive documentation: approved design and offline pilot

Status: offline implementation; live publication is not enabled.
Decision: Jeremy approved this direction on 2026-09-25 in Codex task
`01a0d946-629f-7580-9cdb-972daf9c3ab6` (“Yes, I approve, thank you!”).
Approval was observed at 21:23 UTC, not asserted as the message timestamp.
Work: WOR-183, preparatory portions of WOR-187 / WOR-188.

## Decision and ownership

C021 will prepare approved repository documentation and publish derived copies to
stable native Google Docs. NotebookLM links to those sources; podcasts and other
artifacts are generated on demand initially. C010 remains the primer generator.
Git/repository documentation remains authoritative. A freshly generated primer
does not prove that the underlying prose matches deployed runtime behavior.

This decision supersedes the MCP-first recommendation in the September 12
WOR-185 audit **for the planned nightly publication path** and the older default
of creating/replacing notebooks. That audit remains historical evidence; the
MCP server stays available for separately authorized interactive operations.
No installed service, auth configuration or existing notebook changes here.

Google documents automatic refresh of Drive-linked sources, including on opening
a notebook. We still need an account-specific live canary; this is not an
unattended overnight ingestion SLA. Native Google Docs are the selected initial
format; existing Markdown files mirrored to Drive are not assumed equivalent.

- [Current consumer source guidance](https://support.google.com/gemininotebook/answer/16215270)
- [Automatic Drive sync announcement](https://workspaceupdates.googleblog.com/2026/05/keep-your-sources-up-to-date-with-automatic-Drive-syncing-in-NotebookLM.html)
- [Docs batchUpdate and revision write control](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate)
- [UTF-16 locations, final newline and stripped characters](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request)

## Runnable offline pilot

From an owned checkout with the project's dependencies installed:

```sh
python -m notebooklm_mcp.doc_refresh.drive_pilot
python -m notebooklm_mcp.doc_refresh.drive_pilot --format markdown
python -m pytest tests/test_drive_publication.py -q
```

The module prints a built-in **synthetic** two-source journal example. JSON shows
the proposed Google Docs request, a constructed synthetic readback and an
unchanged repeat plan. It accepts no input file, real destination, account or
`--apply` option. It never reads a repository, opens a network connection, changes
the notebook map, obtains credentials or runs inference. Output goes only to
stdout; ordinary shell redirection can retain the example outside the repo.
The synthetic readback is not evidence of an upload. Tests separately interpret
the request's UTF-16 delete/insert operations to verify the expected text.

## Implemented boundary

`drive_publication.py` contains pure functions:

1. `render_bundle(title, sources)` takes in-memory `SourceText` records and
   produces a `Bundle`. It sorts by repo/path, rejects duplicate identities,
   normalizes line endings/trailing newlines, retains Markdown/front matter,
   and includes full source revisions and normalized-content SHA-256 digests.
   Its overall SHA-256 binds the rendered text; there is no wall-clock field.
2. `parse_document(raw)` accepts a complete Docs response requested with
   `includeTabsContent=true` and `suggestionsViewMode=SUGGESTIONS_INLINE`.
   The response must explicitly report that same mode, including on readback;
   missing, default, unknown and preview modes refuse. It requires one tab, a revision ID and
   contiguous plain-text paragraphs. It checks UTF-16 ranges, refusing missing
   fields, additional tabs, child tabs, suggested changes and unsupported
   structures rather than silently omitting content.
3. `plan_update(bundle, remote, binding)` compares the expected destination ID,
   tab ID and last-verified text hash. Unexpected remote text refuses rather
   than overwriting manual edits. Changed text produces one batch containing
   deletion (when needed), insertion and `requiredRevisionId`. It preserves the
   final undeletable newline and stable destination ID. Identical text is a
   no-op. Every bundle requires a positive integer source count and non-whitespace
   publication text, including for no-ops; clear-to-empty is unsupported. An empty
   selected source is allowed because rendering still emits title/provenance.
   Unsupported controls/private-use characters refuse without normalization.
4. `verify_readback(plan, snapshot)` checks destination and exact expected text.
   It returns the verified digest; it does not mark NotebookLM current or
   persist/advance any mapping. The future caller owns verified state updates.

These are text preparation helpers, **not source selection or privacy checks**.
`SourceText` is not a new manifest and cannot attest authorization. No path in
this implementation resolves source metadata as a filesystem path. Real file
selection must continue through the existing `canonical_docs.yaml` contract and
accepted WOR-186 implementation. This PR does not touch or replace that work.

The parser deliberately supports a narrow text-only destination. Rich formatting
is not reconciled or fingerprinted; existing manual/multi-tab/structured Docs
must not be adopted as managed destinations. A future transport must request a
complete response, preserve destination ownership, reject unexpected revisions,
and validate remote text before promoting publication state. This pilot contains
no transport, retry loop, auth state, mapping extension or installed command.

## Supported text and historical follow-ups

WOR-788 resolves DRIVE-F1 (original P3) by requiring an explicit inline-suggestions
response before parsing either the planning snapshot or readback. Nonempty
`suggested*` markers still refuse in inline mode. Future callers must route every
Google response through `parse_document`; constructing a `DocsSnapshot` directly
is only appropriate for trusted synthetic fixtures, not a transport shortcut.

WOR-789 resolves DRIVE-F2 (original P2) by retaining a deliberate narrow policy:
LF and TAB are the only supported C0 controls. U+000B soft breaks are valid Google
text but unsupported here, in both source text and remote snapshots. Google's
[InsertTextRequest reference](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request#InsertTextRequest)
excludes U+000B from the documented stripping ranges; this implementation must not
claim otherwise. Surrogates and BMP private-use characters also refuse. Source
CR/CRLF is normalized to LF before this check; remote content is not normalized.

DRIVE-F3 (original P3) is resolved by rejecting empty/whitespace-only or sourceless
bundles before planning, even against an already-empty destination. This avoids
empty insert requests without claiming that Google rejects them. There is no
clear-to-empty operation. A future deletion feature requires a separate contract.

These three findings and their original severities remain in the completed
[PR #7 review](https://github.com/jeremybrad/notebooklm-mcp/pull/7#issuecomment-5841635568).
The current follow-up adds and tests the input rules required before live adapter
integration; it does not re-review or erase that pilot's historical review rounds.

## Remaining acceptance and integration

WOR-186 / [PR #5](https://github.com/jeremybrad/notebooklm-mcp/pull/5) is merged
at `6317b5db57f82a9df0e1302cacb05fb80ccb2011`; its fourteen reviews and privacy
repairs remain recorded there. The accepted manifest must supply real-repository
selection; no alternate selector may be connected to these helpers. WOR-187's
C021-plus-core-repo acceptance is not satisfied by synthetic inputs.

Next, integrate selected text and C010-generated
publication copies from pinned approved revisions. Use source-specific immutable
revisions so unrelated repository commits do not cause content churn. Preserve
hash/manifest identity in the existing C021 map/receipt mechanism; do not create
a second durable registry. Define complete multi-document publication separately
from individual writes. Do not publish a partly updated set as fully current.

A separately authorized live canary must establish Google account/folder access,
Docs OAuth scope, create/link one synthetic Doc, verify version A then version B
under the same IDs, and measure NotebookLM readback/citation behavior after
opening. The implementation assumes none of those steps succeeded. Initial
adoption of a nonempty Doc and recovery after a write succeeds but state recording
fails require explicit reconciliation; do not reset the prior hash blindly.

The first useful collection should explain the C003+C014 journal system, including
upstream feeds, S3/B1 input products, processing, narrative context, partial days,
late enrichment and output/mirroring. Export only approved architecture docs,
not private journals or context payloads. A documented feed is not evidence of
its current deployment or coverage for a particular day.

Scheduler activation is a later approval: reconcile the existing 02:00 C021 job
and the independent primer mirror before cutover. The existing job still uses
obsolete single-root path assumptions and its auth initialization can bypass
failure receipts. This PR deliberately does not re-enable that runtime by fixing
auth. All failed runs need observable terminal outcomes in the final integration.

Future evidence must distinguish: selected source revision → locally rendered
bundle → verified Drive content → observed NotebookLM source → generated artifact.
Gemini may propose explanations using approved bundles once its guarded route
works, but deterministic publication has no model-inference dependency.
