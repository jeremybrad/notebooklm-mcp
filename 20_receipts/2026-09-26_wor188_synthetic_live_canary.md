# WOR-188 synthetic live lifecycle canary

Executed 2026-09-26 UTC by Betty, after PR #9 merged as
`e621d6e7a0c247fdb65276c2aff2b03c2fa20fda` (tree equal to reviewed
`a04da226247b55b30438dad40e633e8d51389d43`). This receipt records a bounded
interactive test, not deployment of an unattended adapter.

## Authority and boundary

Jeremy answered **“Approve this synthetic live test”** to the concrete request
for one private Google Doc outside the primer mirror, one test NotebookLM
notebook, fictional A then B under the same Doc ID, citation checks, and one
synthetic infographic. Approval was observed before 04:29:22Z; that is not
asserted as the message timestamp. The owning work item is WOR-188.

No real repository content, private journal data, credential repair, deletion,
installed runtime change, scheduling change, or sharing expansion was included
or performed. Model inference used the signed-in NotebookLM ULTRA product;
no model API adapter or key was used. The Doc owner and browser account matched
the approved account. Drive metadata showed only owner access and a My Drive
root parent, outside `Repos/_project_primers/`. Notebook sharing showed one
owner and Restricted access. Account and private cloud-object identifiers are
retained in the task's local execution evidence and owning tracker, not this
public repository.

## What ran and observed evidence

1. Created one native Google Doc, one plain-text tab. Full reads explicitly
   returned `SUGGESTIONS_INLINE`. The connector flattens the native tab wrapper;
   the local request-preparation script restored that wrapper while preserving
   all returned tab content and requiring exactly one root tab. The unchanged
   reviewed parser/planner from the merged code produced the update requests.
   This one-off shape adaptation is not a reviewed production transport.
2. Published fictional version A using `requiredRevisionId`; full readback
   exactly matched the intended text, including its final newline, by 04:32:12Z.
   SHA-256: `bc198872627f716be07f7b07706d65420f84f4a8ae13e78304cc2353b4cd892b`.
3. Created one notebook and attached that Doc once through the Drive picker.
   The cited answer identified A, two sources Amber/Birch, and
   Collect → Normalize → Summarize. Opening the citation displayed the actual
   A text and `C021-CANARY-A-20260926` marker.
4. Re-read A, then replaced its content with B under the **same Doc ID** using
   its required revision. Exact full readback passed at 04:38:36Z.
   SHA-256: `cd3631ce10daeadf3e2a479dec75049a7e725da24846a62d9ce3c2e9f3d4e747`.
5. Reloaded the same notebook and opened its single linked source. It displayed
   B without clicking a manual refresh button. A new answer and its opened
   citation identified B, three sources Amber/Birch/Cedar, the order
   Collect → Normalize → Verify → Summarize, and `C021-CANARY-B-20260926`.
   No duplicate source, notebook replacement, or detach/re-add was performed.
   This observation includes reopening and opening the source; it does not
   establish background freshness without interaction or a refresh latency SLA.
6. Generated exactly one infographic from the one current source. The completed
   image, titled **Synthetic Test Process Diagram**, was visually inspected by
   04:44 UTC. It visibly includes SYNTHETIC TEST, FICTIONAL SYSTEM, VERSION B,
   all three source names, all four stages, and the exact B marker. The exported
   PNG is 3,152,437 bytes, SHA-256
   `5fd682df968b43073f8ecf75322f7e152f571b52ac2be4bb0e0f87caceda5353`.

## Result and limitations

| Layer | Observed result |
|---|---|
| Google Docs publication | PASS: revision-bound A then B, same ID, exact readback |
| NotebookLM current source and new citations | PASS after reopening/source inspection; no explicit manual refresh |
| New infographic freshness | PASS for B labels, sources, stages and marker |
| Historical overview | STALE: initial overview still described A; earlier answers remained historical |
| Unattended nightly execution | NOT TESTED or enabled |

The infographic groups the four stages into two pairs. It also adds explanatory
wording, including a claim that the marker confirms validation. That claim is
generated illustration, not independent evidence. Artifact acceptance here is
limited to the specified freshness/content checks; factual editorial review is
still necessary for real architecture graphics.

NotebookLM MCP's read-only preflight returned RPC Error 16 / authentication
expired. The existing browser session worked. No shared credentials were
repaired. The embedded Drive picker initially rejected element/coordinate
actions; selecting the visibly focused synthetic item with the documented
keyboard API and its Insert confirmation succeeded. No private RPC or alternate
authentication bridge was used.

The retained Doc, notebook, and infographic are the intended outputs. Cleanup
was not authorized and was not attempted. The existing 02:00 legacy writer and
60-second primer mirror were left unchanged; fixing shared authentication must
not inadvertently revive the old writer. The canonical runtime checkout was
not pulled.

## Files, validation, and next owner

This branch adds only this receipt and its changelog fragment. No application
code, schema, auth, schedule, or instruction surface changes. The full diff
qualifies for the receipt-lane adversarial-review skip under C010 rules_v2,
Physics #1 and Agents #2; no new inference review is represented as completed.
Hosted CI was observed `disabled_inactivity`; no hosted test pass is claimed.
Live operations and exact readback above validate the canary, not runtime code.

Local task evidence includes version texts, planned structured requests, trusted
full-read files, verification JSON, exported PNG, and the result report under
`outputs/canary/`. The sole narrative session log and WOR-188 hold continuity.

WOR-188 remains the owner for transport/state integration and unattended OAuth
assessment. WOR-189 owns old-writer/mirror cutover planning; production activation
requires its separate decision. Real C003/C014 documentation uploads and learning
artifacts remain outside this synthetic approval. No new persistent registry or
scheduler was introduced.
