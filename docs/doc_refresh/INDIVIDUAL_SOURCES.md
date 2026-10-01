# Individual original Markdown publication

WOR-851 adds an explicit opt-in path alongside the existing five-repository
native Docs bundle publisher. It uses the accepted manifest selector and immutable
Git blobs, retains the original UTF-8 bytes (including CRLF), and identifies each
original by repository plus full relative Markdown path. Content gets no wrapper,
summary, time stamp or version bump. Provenance is separate in the existing map
and operational receipts. Agent guidance inside a source is reference text.

This source change does not install, enroll or schedule anything. The existing
bundle map/configuration and 02:00 writer remain operationally unchanged. Per-source
Drive/Notebook ingestion and conditional-write enforcement have not been tested
on the live account. Full C010 coverage and untracked primer inputs remain outside
this committed-document slice.

## Explicit offline plan

Use an inspected, narrow `c021.canonical_docs.v1` manifest selecting only approved
Markdown originals. The selector's exclusions do not replace human content/privacy
inspection. All selected originals must be Markdown; unsupported inputs refuse,
rather than disappearing from the output. Use the original canonical repo root
and a full fetched commit SHA. Dirty/untracked bytes are ignored.

```sh
PYTHONPATH=/absolute/reviewed/checkout/src python -m notebooklm_mcp.doc_refresh.publication_cli plan \
  --individual --repo /absolute/canonical/repo FULL_COMMIT_SHA \
  --manifest /explicit/inspected/sources.yaml \
  --map /explicit/existing/notebook-map.yaml \
  --receipts /explicit/existing/receipt-directory
```

Planning creates only a redacted terminal operational receipt, never a map or cloud
object. `status` is also offline. Neither is a fresh remote content observation.
Receipts use `c021.individual-publication-batch.v1` and the existing receipt sink.
All selected originals/bindings and pending inputs are checked before credential
access. A preflight failure may leave items not attempted; it is not partial success.

## Stable bindings and enrollment boundary

Per-path `drive_documents` entries reside inside the existing `notebooks` mapping.
Each has a version, stable file ID, verified hash/strong ETag/source provenance,
pending intent and optional separately observed notebook source attestation.
The existing native Docs entries remain separate within that same map. Whole-map
validation prevents a file being bound twice, including across both formats.

This implementation creates no Drive file or Notebook source, discovers no
folder membership and adopts no nonempty file. `bind_empty` is a library primitive
for explicit adoption of an inspected empty Markdown file, under the existing
map transaction. Calling it is a governed state write, not upload permission.
Live enrollment requires an exact reviewed account/parent/file/source scope.
Inspect existing individual sources before proposing new membership; titles alone
cannot identify them. A removed/renamed original or narrowed manifest that omits
an existing per-document binding refuses live preflight. No deletion or automatic
rename/move inference is implemented. Do not reset a pending map.

The existing explicit provider configuration is reusable with per-document keys:
SHA-256 of UTF-8 `repository + NUL + relative_path`, returned by `document_key`.
Each key pins the existing `document_id`/`parent_id` shape to that Markdown file.
This is configuration in the existing provider/map mechanism, not another registry.
Do not modify installed bundle config as a side effect of preparing a pilot.

## Live updates and recovery

The Markdown adapter reuses fixed `drive.file` OAuth leases, account, owner-only
permissions, parent and editability checks, time/size bounds and redacted failures.
Reads require a `text/markdown` file, complete media bytes and coherent strong ETags
before/after the read. Drive v2 supplies the file ETag; v3 supplies media readback.
There are no redirects, cookies, ambient credentials or automatic retries.

Changed publication records pending intent before one media PUT to the same
file ID, using the inspected ETag in `If-Match`, then verifies complete byte
readback before promoting state. A no-change run still checks remote bytes but
makes no upload or map update. Manual content edits refuse. Point-in-time
permission checks do not prevent a privileged party changing sharing afterward.

**Qualification before writes:** independently test a stale ETag against a
separately approved synthetic file and verify rejection plus intact bytes. Record
that evidence and have it assessed before real updates. Google's v2 ETag field and
media update method are documented, but those pages do not establish live
conditional enforcement on this account. `--conditional-write-evidence` names
that separately assessed evidence; it is an explicit trusted operator assertion,
not a file that this CLI reads or independently validates. Never substitute a unit
test or arbitrary string for live qualification. A missing reference refuses
individual publish before credentials. If enforcement is inadequate, stop and
assess faithful native Docs conversion instead of removing the guard.

Live mode additionally requires `--credentials-config`. The individual path accepts
explicit `--repo`/`--manifest`, not cohort scheduling or native Docs snapshots.
`reconcile` requires the original pinned commit, manifest, bytes and blob from the
pending operation. It reads the remote file, promotes an exact target or clears an
exact unchanged base; it never replays a write or adopts an unrelated edit.
A receipt persistence error remains failure even if cloud work completed. Abrupt
process death may leave pending map state without a terminal receipt.

Drive readback, actual Notebook source contents on normal opening, selected-source
answers, and generated artifacts remain separate evidence. This implementation
calls no model and creates no artifacts. A live proof should record actual format,
file/source IDs, latency and selected sources; manual Sync must be distinguished
from refresh on opening. Scheduling remains a separate explicit rollout after
manual acceptance; no second writer is supplied here.

References: [Drive uploads](https://developers.google.com/workspace/drive/api/guides/manage-uploads),
[v2 file ETag](https://developers.google.com/workspace/drive/api/reference/rest/v2/files),
[v2 update](https://developers.google.com/workspace/drive/api/reference/rest/v2/files/update),
[source behavior](https://support.google.com/gemininotebook/answer/16215270?hl=en).

The v2 media-update method is PUT, as specified by [files.update](https://developers.google.com/workspace/drive/api/reference/rest/v2/files/update). The October 1 synthetic PATCH attempt returned HTTP 404; live conditional enforcement remains unqualified until a separately cleared same-file test.
