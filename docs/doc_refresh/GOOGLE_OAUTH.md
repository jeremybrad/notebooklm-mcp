# Google data OAuth for the documentation publisher

This provider fills the existing publisher's credential-factory seam. Code and
synthetic tests exist; no live grant, native host acceptance or scheduler activation
is implied. Google data OAuth is separate from NotebookLM cookies and Gemini model
authentication. No model inference or metered model fallback is part of this path.

## Configuration and offline diagnosis

An operator supplies one nonsecret JSON file, outside the selected source trees:

```json
{
  "version": 1,
  "keychain_path": "/operator/confirmed/path/login.keychain-db",
  "client_id": "registered-desktop-client.apps.googleusercontent.com",
  "email": "jeremybradford1977@gmail.com",
  "permission_id": null,
  "destinations": {}
}
```

All fields are required. `permission_id: null` is setup-only; live publication
requires the observed, approved Drive permission ID. Each destination uses a
repository basename as its key and exactly `document_id` and `parent_id` as its
values. The destination ID must match the existing publication-map binding; neither
the configuration nor this provider creates a Doc or binding. The private parent
must be outside the existing primer mirror.

Run `repo-doc-auth diagnose --config /explicit/config.json` to validate structure
without reading Keychain, a client secret, browser state or Google. The entry point
does not install itself; an existing environment can run the source module
`notebooklm_mcp.doc_refresh.google_oauth_setup`. Never replace explicit paths with
ambient credential discovery. Unknown/duplicate configuration keys are refused.

`repo-doc-publish publish` and `reconcile` accept `--credentials-config` alongside
their existing explicit repo/full-commit/map/receipt/manifest arguments. They check
all source bundles and map bindings before accessing credentials. `plan` and `status`
remain offline and reject this argument. Input/configuration errors occur before a
run and return 2 without a receipt; credential failures after execution starts appear
as fixed codes in failed terminal receipts.

## Storage and runtime

The only store is an explicitly selected file-based macOS login Keychain, using
generic-password service `c021.notebooklm.google-data-oauth.v1` and account
`jeremybradford1977@gmail.com`. No search/default-keychain resolution, new keychain,
unlock, ACL edit, credential listing, environment/file/vault fallback or deletion
exists. Other operating systems refuse native operations. This Mac-only provider
does not change support of other package commands.

One versioned JSON secret stores the Desktop client (and required client secret),
refresh token, exact `drive.file` scope, email/Drive permission ID and issuance/known
refresh-expiry metadata. Access tokens stay in process memory. Do not print,
export, upload or commit the stored JSON. Python objects are not a secure-memory
allocator: no memory-zeroization or protection from a privileged process is claimed.

The dependency-free Security.framework bridge opens the selected file and limits
queries/updates with `kSecMatchSearchList`; adds use `kSecUseKeychain`. Runtime turns
off automatic Keychain interaction, restores the prior process setting and fails
closed if restoration fails. A process-wide lock coordinates this adapter's calls;
it cannot coordinate unrelated libraries modifying that global setting. Use a
dedicated publisher process. No-prompt behavior must still be tested on the actual
host/interpreter before unattended use.

Creation refuses an existing item. Explicit renewal checks existing version, client
and account before consent, then compares expected stored bytes before native update.
It never deletes/re-adds the item. This is **not cross-process compare-and-swap**;
enrollment/renewal requires an exclusive writer. Concurrent operators must not renew
the same grant. An update error can be ambiguous; inspect through the approved setup
procedure instead of automatically retrying. There is no rollback-to-old-secret
command or automatic grant migration.

Before each job, the provider validates configured destination and stored identity,
refreshes through the fixed Google token endpoint, verifies the returned bearer's
Drive identity, then passes an immutable lease to the existing transport. Explicit
scope responses must be exactly `drive.file`; an omitted refresh-response scope
inherits the stored grant, as allowed by OAuth. An explicit null scope is refused.
Unexpected refresh-token replacement stops for controlled renewal. There is no
automatic consent, account change, grant repair or Docs write retry.

Network calls disable redirects, cookies and ambient proxies, with 64 KiB response
limits, fixed endpoints and bounded inactivity timeouts. The 60-second elapsed
budget is checked between chunks; a blocking read can additionally take its
20-second inactivity timeout. Errors contain fixed codes, never token/response text.
The existing Docs transport separately repeats account/destination/privacy checks
and enforces its lease margin and revision-bound write/readback rules.

## Later live setup: separately authorized

1. Identify or explicitly provision a suitable Google Cloud project and Desktop
   client, enable the Google Docs/Drive data APIs, and inspect the actual consent
   audience/publishing status. External apps in Testing may receive seven-day
   refresh grants for Drive scopes; absence of an expiry field is not a durability
   guarantee. Revocation remains possible in Production.
2. Perform a separately authorized fictional native Keychain acceptance test for
   the chosen interpreter, exact store, access policy and no-dialog failure paths.
   Synthetic/fake-native unit tests do not replace this test. Do not loosen ACLs or
   unlock a store to make unattended execution pass.
3. After real enrollment approval, retain the downloaded Desktop client JSON in an
   explicit owner-only regular file (0600); never paste secrets into chat or pass
   them in command arguments. Run `repo-doc-auth enroll --config ... --client-config ...`.
   This explicit setup opens the system browser and a bounded localhost callback
   with random state and PKCE S256. Wrong state/path/Host, duplicates, denial and
   timeout fail safely. At most 32 connections and 16 KiB headers are accepted;
   each accepted connection gets a two-second deadline within the total 180 seconds.
4. The same bearer verifies the configured email with Drive. Setup displays only
   nonsecret account/client identity and requires the typed email before storing.
   Record the permission ID in the nonsecret configuration. Future `renew` uses the
   same explicit client file and operator confirmation and preserves account/client
   identity. No setup mode deletes the downloaded client file automatically.
5. Verify refresh from the intended user/process context without scheduling. Then
   perform separately approved synthetic publication against an empty Doc accessible
   to this exact app. `drive.file` cannot access a different connector's Doc merely
   because its ID is known. Do not broaden scope to bypass this boundary.
6. Complete the approved real-source pilot, independent NotebookLM citation/source
   freshness checks and artifact checks before old-writer cutover and scheduling.

A stalled operating-system browser opener can outlive setup's timeout as a daemon
thread. It never receives the authorization code/result; the listener is closed on
every exit. A fresh consent attempt requires a new explicit setup invocation.

## Failures and ownership

| Fixed receipt code | Required action |
| --- | --- |
| `credential_keychain_not_found` | Complete approved enrollment; no automatic search |
| `credential_keychain_interaction_required` / `access_denied` | Reassess host access policy; do not unlock or change ACL automatically |
| `credential_keychain_interaction_restore_failed` | Stop the dedicated process; investigate before retrying |
| `credential_grant_mismatch` | Reconcile the explicit account/client pins; do not replace them automatically |
| `credential_oauth_invalid_grant` / `invalid_client` | Operator-controlled consent/client repair |
| `credential_oauth_refresh_token_changed` | Controlled renewal; no silent persistence |
| `credential_destination_mismatch` / `destination_unconfigured` | Reconcile approved destination with the map |

Setup errors omit the receipt's leading `credential_`. Generic failures remain
redacted; never enable sensitive HTTP logging to investigate them. Existing pending
publication recovery rules still apply after a possibly applied Docs write.

WOR-188 owns provider and live acceptance; WOR-191 owns real source/artifact approval;
WOR-189 owns old-writer/mirror cutover and scheduling; WOR-192 owns operator guidance.
No canonical pull, package installation, cookie repair or scheduled activation is a
side effect of this implementation. Jeremy remains merger and runtime authority.

Sources: [Google Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app),
[Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth),
[Drive identity](https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get),
[OAuth lifetimes](https://developers.google.com/identity/protocols/oauth2),
[Apple macOS Keychains](https://developer.apple.com/documentation/technotes/tn3137-on-mac-keychains),
[Apple interaction control](https://developer.apple.com/documentation/security/seckeychainsetuserinteractionallowed(_:)).
