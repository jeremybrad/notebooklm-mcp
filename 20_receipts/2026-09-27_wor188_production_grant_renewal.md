# WOR-188 — production-app grant renewal and fresh refresh acceptance

Jeremy reported PR22 merged and instructed continuation in Codex task
`01a0d946-629f-7580-9cdb-972daf9c3ab6`, following the prepared single-renewal
proposal. The bounded continuation decision is recorded on WOR-188 comment
`3644da73-c451-4170-993c-717be978f8b9`, with WOR-189 crosslink
`e532ee0a-8b8e-4a11-a0d8-1208f80ed659`.

Fresh fetch and live GitHub verified PR22 merge
`a558970286085778520e051f710ff322ae8c761e` at 2026-09-28T00:03:22Z. Its full
tree equals assessed `5a25fd800db0ba726d1da4ab68f4f0ad690f8886`; Current status
was reconciled to MERGED. The owned execution checkout started clean at that
merge, using the already-pinned Python 3.13.11 interpreter and explicit source
path. Private client/publisher files were regular owner-owned 0600 files;
preflight found no competing renewal process. No canonical runtime update ran.

## Approved operation and observed result

Exactly one existing `repo-doc-auth renew` invocation ran with a 600-second
supervisor cap and the implementation's 180-second consent callback deadline.
It used the same Desktop client, pinned account, permission ID, drive.file scope
and exact existing login-Keychain item. The previous grant remained in memory
only; no secret backup/export, deletion, unlock or ACL change was performed.

The Google consent screen identified the expected account and showed one
existing permission: access only to specific Drive files used with the app.
After consent, the CLI's nonsecret output matched the pinned email, permission
ID and client ID. Betty entered the exact displayed email to confirm the
in-place update. The CLI returned `grant_stored`, exit 0, after 58.446 seconds.
Chrome showed ERR_BLOCKED_BY_CLIENT on the localhost result page after the
callback had already reached the CLI. No reload or browser-warning bypass was
performed; successful callback/exchange/storage is established by the CLI and
the independent acceptance below, not that browser page.

One fresh process then read the exact item with Keychain interaction disabled,
validated the pinned grant, performed one OAuth refresh and the implementation's
Drive account-identity read. It returned success, exit 0, in 0.597 seconds,
within its 60-second cap. There were no retries.

Safe metadata from that process:

- Issued at: `2026-09-28T00:08:52.090430+00:00`.
- Refresh expiry: `null` (unspecified by Google, not a permanent-life guarantee).
- Refreshed access expiry: `2026-09-28T01:09:05.673050+00:00`.
- Scope: exactly `https://www.googleapis.com/auth/drive.file`.
- Account identity: verified against the existing pinned account and permission ID.
- Shared provider destinations: zero, unchanged.

The earlier grant's recorded October 4 expiry is historical evidence. The new
grant has no reported refresh expiry. This resolves the measured seven-day
Testing-grant condition for this replacement; future revocation/expiry and
unattended-context access remain possible and must fail visibly.

## Evidence and remaining boundary

Local operation files are in
`~/LocalWork/Codex/c021-public-pages/renewal/`: PLAN.md, supervise.py,
refresh-check.py, single-use start markers, renew-result.json,
check-result.json, acceptance.json and consent-scope/result screenshots.
They retain only safe outcomes and metadata, never tokens, callback parameters,
client secrets or raw Google response bodies. Browser screenshots contain page
content only, not the callback address bar. The two supervisor results and
acceptance metadata substantiate the timing, exit and refresh claims above.

No Doc create/update/upload, NotebookLM operation, model inference, canonical
pull/install, recurring scheduler change or runtime cutover occurred. This
interactive-host fresh process is not production-item GUI-launchd acceptance,
locked/denied native acceptance or full-publisher host acceptance. Those and
single-writer promotion/cutover/first scheduled receipt remain on WOR-188/189.
An ambiguous update would have stopped without automatic rollback; none was
observed. No earlier grant was exported for restoration.

## Separate approved production-item GUI-launchd acceptance

Jeremy explicitly approved one background credential check after the foreground
result. Owning decision: WOR-188 comment
`700dd255-571a-4268-8f79-487e69097c9b` at 2026-09-28T00:15:06Z; WOR-189 crosslink
`d9727147-589e-4284-8040-18ba15eaa280`.

The prepared input hashes, private configuration modes and absence of competing
renewal were rechecked. The existing legacy job was loaded but not running.
One local, non-installed plist bootstrapped label
`com.notebooklm-mcp.production-host-acceptance` into `gui/501`, with RunAtLoad,
no KeepAlive/calendar/interval/watch trigger, and an exclusive single-use marker.
Its child ran the same successful fresh-process check using the pinned Python
and merged source. It read the actual existing grant with prompts disabled,
refreshed once and verified the same identity with exactly drive.file.

The worker passed in 0.659 seconds, exit 0 and zero stderr; launchd reported
supervisor exit 0 with zero stderr. Access expiry was
`2026-09-28T01:15:38.422565+00:00`; the stored issuance and unspecified refresh
expiry were unchanged. No grant write, Doc operation or retry occurred.

The exact temporary job was booted out successfully and verified absent. The
legacy job's before/after launchctl output was byte-identical; its existing
02:00 schedule and command remain unchanged. Evidence is retained in
`~/LocalWork/Codex/c021-rollout/production-host-acceptance/`: proposal, prepared
hashes/scripts/plist, approval/single-use records, bootstrap/terminal/bootout
states, worker/acceptance outputs and host-summary.json. No file was installed
under Library/LaunchAgents.

This supersedes the preceding pending production-item GUI-launchd positive
check only. Native locked/denied negative-path and full-publisher host acceptance,
canonical/config promotion, single-writer cutover and first scheduled receipt
remain open. Production login Keychain was never locked or modified to force
failure; no recurring activation is implied by a one-shot success.
