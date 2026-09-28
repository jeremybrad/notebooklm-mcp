# Explicit documentation publisher

WOR-188 connects the existing immutable Git bundle builder and publication-state
library to native Google Docs/Drive HTTP requests and explicit batch operations.
The explicit Google OAuth/Keychain provider and native HTTP path have passed a
bounded C014 live pilot (PR #17), including Docs readback and a NotebookLM source
citation. The approved C014/C021 cohort is connected to the installed 02:00 local job
after the 2026-09-28 UTC cutover. Production-app renewal, no-dialog background
credential access and a full two-repo background publication passed; see the
[cutover receipt](../../20_receipts/2026-09-27_wor189_nightly_cutover.md).
The first calendar-triggered publication passed on 2026-09-28 at 02:00
America/Denver; see the [dated first-run acceptance](../../20_receipts/2026-09-28_wor189_first_scheduled_publication.md).
C021 source content was separately verified after opening NotebookLM. This does
not establish unattended ingestion or indefinite credential validity.
NotebookLM cookies are not Google Docs OAuth credentials.

## Start with an offline plan

Read the accepted source manifest and inspect the selected documentation before
publication. Manifest selection is not permission to upload every selected file.
The default scans can include many documents; a narrow pilot needs its own
reviewed accepted selection. Never replace the selector with an ad-hoc gatherer.

Use an already available Python environment with repository source on its path:

```sh
PYTHONPATH=/absolute/path/to/checkout/src python -m notebooklm_mcp.doc_refresh.publication_cli plan \
  --repo /absolute/path/to/approved/repo FULL_COMMIT_SHA \
  --map /explicit/path/to/notebook_map.yaml \
  --receipts /explicit/existing/receipt/directory
```

The packaged command is `repo-doc-publish`, but adding the entry point does not
install it. There is no default map/receipt path, implicit repository discovery,
`--all`, implicit fetch, or scheduler registration. Each repeated `--repo` takes
an explicit root and full immutable commit SHA. The map and receipt destinations
must stay outside the selected source repositories. An absent map is read in
memory; planning does not create it. The receipt directory must already exist.

The default `plan` builds bundles and compares local recorded hashes. It can
report unbound, changed, unchanged or pending state without cloud requests.
This is a plan, not a fresh remote verification. `--snapshots /path/to/file.json`
can supply complete native Docs responses keyed by repository basename for
offline revision-bound planning. Input is bounded, duplicate keys are refused,
and snapshots are never stored in receipts. Command/input parsing errors return
2 before execution and produce no run receipt; accepted execution requests
produce terminal receipts or an explicit persistence error.

`status` uses the same explicit repo/commit set and reports local recorded
Docs/source/artifact state, not current Google content. `publish` and `reconcile`
require `--credentials-config /explicit/nonsecret/config.json`. Without it they
fail closed with a failed receipt. They accept no bearer token, provider import
path or token environment variable. [OAuth setup](GOOGLE_OAUTH.md) describes the
explicit account/client/destination pins and the separately authorized live
enrollment procedure. `plan` and `status` reject credential configuration and
never access Keychain or Google.

## Integration API and authentication boundary

`publication_batch.execute(mode, jobs, store, receipt_dir, ...)` accepts an
explicit set of `Job(repo, revision)` objects. `manifest_path` selects the
accepted manifest. A trusted `transport_factory(job, document_id)` supplies a
context manager yielding the existing `DocsTransport` interface for live modes.
No factory means no live execution. The batch implementation never fetches
credentials itself and never imports the old NotebookLM client.

The concrete adapter is `GoogleDocsTransport(lease, account, destination, ...)`.
Its immutable `CredentialLease` holds a non-printable bearer, aware expiry,
declared scopes, client ID and provenance. `AccountExpectation` names the approved
Drive permission ID and email; `DestinationExpectation` names the exact document
and parent IDs. These are explicit caller values, never guessed from browser
login. The provider's scope/provenance metadata are trusted assertions; the
adapter does not independently establish the token's issuance history.

Each HTTP operation checks that more than 30 seconds remain on the same lease.
There is no refresh during an operation, hidden credential swap or POST retry.
The intended OAuth scope is `drive.file`; a token must have access to this
particular file through its own app. Knowing a Doc ID or having opened it through
another connector does not establish that access. The provider reads one explicit
Keychain item, verifies its pinned grant, refreshes it and checks the same bearer's
Drive identity before constructing the lease. It stops on unavailable/revoked
consent. Synthetic implementation tests read no actual credential store.

Google endpoints are fixed. HTTP clients disable redirects and ambient proxy
configuration, use bounded timeouts and response sizes, and expose redacted
errors. Preflight checks the same bearer's Drive account, native Doc identity,
edit capability, non-trash state, approved parent, sole owner and complete
owner-only permissions. Permission pagination must finish. These checks describe
what Google reported at that time; they are not an atomic lock against someone
changing sharing after preflight. The operator must control the destination and
verify that its parent is outside the existing primer mirror before activation.

Reads explicitly request all tabs and `SUGGESTIONS_INLINE`, preserve the native
response and use the existing strict plain-text parser. Writes accept the
existing planner's replacement shape with `requiredRevisionId`; they never
substitute collaborator-merge `targetRevisionId`. Exact revision enforcement and
readback remain the existing publication-state library's responsibilities.
Unsupported content is refused, not flattened into apparently safe text.

## Batch completion and recovery

All requested source bundles are validated before cloud mutation begins. Existing
bindings are required; this path creates no Doc, notebook or binding and does not
adopt a nonempty document. Publishing compares current remote content with the
recorded base, persists pending intent, performs at most one guarded write, and
promotes only after exact readback. No-change publication still validates Google
content; local hash equality alone is not a live success.

The first failure stops later mutations. Receipts retain earlier verified
successes and mark later items not attempted; a partial batch never reports
overall success. A lost response can mean Google applied the write. Keep the
pending record and use `reconcile` with the same original repo commit/bundle.
Reconciliation reads Google and may update local state; it never replays a cloud
write or silently adopts a manual edit. See [state recovery](PUBLICATION_STATE.md).

Receipt records follow the existing operational JSON-receipt convention in an
explicit directory, with a new versioned format rather than a second state
registry. Each run has a unique ID and terminal outcome. Files are private,
flushed and atomically published; the output path is checked before cloud calls.
Metadata/hashes and stable error codes are recorded, not source text, bearer
tokens, response bodies or arbitrary exception messages. An unusable receipt
destination stops execution. Final receipt/fsync failure is a failed run even if
its bytes or a remote write became visible. It does not undo cloud work.

An abrupt process death can leave temporary receipt residue or no terminal
receipt. No crash-complete audit claim is made. The map's pending operation is
the recovery signal; never infer success from a missing receipt. Old receipt
formats are not rewritten. The output directory and map parent must be trusted,
stable local directories; no protection against an arbitrary privileged process
replacing directory components is claimed.

Docs verification, NotebookLM source attestations and artifact attestations stay
separate. A newly published Doc does not refresh a previously generated podcast
or prove current NotebookLM citations. State-derived observations are labeled as
such. The synthetic canary demonstrated why these layers matter: new source
citations used version B while an older overview still described version A.

## Ownership and authority

WOR-188 owns reviewed OAuth provisioning, approved account/client/scopes, secure
credential storage and refresh lifetime, live adapter acceptance, and explicit
empty-Doc adoption. WOR-191 owns the narrow real documentation pilot and learning
artifacts. WOR-189 owns host acceptance and cutover of the old writer/mirror and
nightly scheduling. WOR-190/192 track operational evidence and operator workflow.
Jeremy retains merge, live publication and runtime-activation authority.

The old cookie-based writer must be quiesced before any shared authentication
repair or new map writer is activated. Do not pull the old canonical runtime
checkout, install this package, repair its cookies or add another launchd job as
a side effect of using an offline plan. This change introduces no model inference
dependency or metered provider route.

Primary contracts: [Docs get](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get),
[Docs batchUpdate](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate),
[Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth),
[Drive account](https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get).

## Explicit multi-repository cohort

For a maintained nightly selection, use `--cohort /absolute/path/cohort.json`
instead of repeated `--repo` arguments. This opt-in configuration names exact
repository roots, names, origin URLs and `refs/heads/...` branches, plus the
SHA-256 of the inspected source manifest. See [the example](cohort.example.json).
Replace every placeholder; the example is not an executable enrollment.

`plan --cohort ...` is offline by default and labels remote-ref freshness
`unverified-local-ref`. Add `--fetch` to explicitly fetch the configured branches.
`publish --cohort ...` requires `--fetch`; all fetches must succeed. Fetch never
pulls or rewrites a checkout. Each branch is resolved once to a full commit and
that revision is used throughout the batch. The approved manifest bytes are
captured privately for the run; a changed manifest hash is refused. The full
manifest hash and ref-freshness label are CLI output metadata; batch receipts
retain their existing commit/source hashes and manifest hash prefix. Preflight
configuration/fetch refusals return exit 2 without a batch receipt, so host
monitoring must also capture command failure. Configured
GitHub origins must match the checkout's literal and effective origin URL.

The existing map and receipt arguments remain mandatory. No Doc or notebook is
created by cohort execution. Every source bundle and every configured map/Doc
binding is checked before credential access or cloud publication begins. Live
Google identity, permissions, content and revision checks still happen for each
Doc through the existing transport. A later live failure can leave a partial
batch; the receipt records what succeeded and what was not attempted.

Recover a pending operation with the original full commit using `--repo` and the
original approved manifest, never by resolving a moving branch. Cohort mode
refuses `reconcile`. Preserve those input revisions and the accepted manifest as
part of operational evidence; a later manifest approval does not change an
already pending operation's input.

## Rollout and ongoing maintenance

Enrollment is deliberate: inspect exact source files, approve their Google
account/Doc/notebook destinations, create and bind those destinations through the
existing enrollment procedure, then run an observed publication and verify the
NotebookLM source and citations. A file-selection rule alone is not an upload
approval. The active first wave is C014's two inspected journal documents and
C021's three publisher documents. C001 is held pending documentation corrections.

The installed `com.notebooklm-mcp.refresh` GUI LaunchAgent now invokes
`python -m notebooklm_mcp.doc_refresh.publication_cli publish --cohort ... --fetch`
at 02:00 local, with `RunAtLoad=false` and `KeepAlive=false`. Its interpreter,
source path, working directory and configuration paths are explicit; there is no
shell activation or dependency installation during a run. The previous plist
and legacy map are preserved. The separate rclone primer mirror uses a different
account and remains unchanged.

Active local files are under `~/.config/notebooklm-mcp/`: `publication-sources.yaml`,
`publication-cohort.json`, `publication-provider.json`, `publication-map.yaml`,
`publication-receipts/`, `publication.log` and `publication-error.log`. The original
manual pilot map was renamed as an inactive backup; use only the promoted map.
Do not revive old manual scripts or restore a backup over a pending operation.

At cutover, the separate background acceptance invocation verified both Docs
as unchanged. The first calendar-triggered run on 2026-09-28 began at
08:00:07Z and completed at 08:00:15Z (02:00 America/Denver), with exit 0,
two remote verifications, empty stderr and no pending operation. C014 needed
no write; C021 changed. WOR-189 records that scheduled result separately from
the earlier manual background test.

At 08:26 UTC, C021's source viewer matched the scheduled bundle's three document
revisions and complete text after whitespace normalization. Opening the source
displayed a freshness check; no manual Sync was clicked. This establishes
content current after opening, not independently unattended NotebookLM ingestion.
The local source observation was updated for that exact bundle only. C014 retains
its prior same-hash source observation and two corrected artifact observations;
the [artifact receipt](../../20_receipts/2026-09-27_wor191_artifact_corrections.md)
records the diagram's acceptance and the audio's qualified explanatory use.
These are dated observations, not perpetual freshness claims.

For later runs, inspect `launchctl print
"gui/$(id -u)/com.notebooklm-mcp.refresh"`, both logs and the latest terminal
receipt together. A preflight error can return 2 without producing a receipt;
a stale prior success must not hide that failure. The one-time first-run
follow-up completed; it is not a permanent failure-alert service.

A nightly run fetches and freezes revisions, validates the
approved selection, updates changed Docs under their existing IDs, verifies remote
readback and records success/failure. No-change runs still verify remote content.
Monitor terminal receipts and stale last-success times; a process exit alone
is not evidence that all Docs or NotebookLM sources are current. Credential
revocation, pending state or unexpected edits stop publication for investigation.
NotebookLM ingestion must be verified separately from a successful Docs write.

Repo owners maintain accurate source documentation through normal PRs. Adding a
repo, widening source selection or changing a destination requires inspection and
an updated approved configuration. The manifest hash deliberately makes unnoticed
selection changes fail closed. Audio and graphics remain on demand and retain
the source version they were generated from; updating a Doc does not regenerate
them. No model inference is needed for deterministic publication.

Contain a failed installed job by unloading only its exact label, preserving
the active map, pending intents and receipts. Do not automatically restore the
old cookie-based writer: it targets legacy destinations. Credential repair,
reconciliation, restoring an old job or changing scope requires its applicable
operator decision. The GUI agent depends on this Mac and user session being
available; inspect receipts instead of assuming a missed/sleeping event ran.
