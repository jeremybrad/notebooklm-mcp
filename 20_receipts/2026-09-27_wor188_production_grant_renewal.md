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
