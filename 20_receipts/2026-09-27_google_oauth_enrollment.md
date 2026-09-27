# WOR-188 — approved Google OAuth enrollment

## Authority and scope

Jeremy approved the prepared Codify3030 enrollment in Codex task
`01a0d946-629f-7580-9cdb-972daf9c3ab6`: "Approved - please continue".
Approval was recorded on WOR-188 at 2026-09-27T20:53:19Z, comment
`859c0527-70c5-464a-81c1-25e9d69d54f9`. It covers the dedicated Desktop client,
additive drive.file declaration, private setup files, supervised consent, exact
login-Keychain grant and one fresh-process refresh/identity check. It excludes
uploads, shared app publishing/branding changes, installation and scheduling.

Live inventory found the named C021 NotebookLM Docs Desktop client already
created on September 26. Jeremy confirmed he created it and supplied the exact
downloaded JSON path. Betty reused that explicit client; no duplicate was created.
The original proposed creation step is superseded by the operator-created client.

## Configuration and execution

- Project: Codify3030 (`codify3030`), number `716364204346`.
- Desktop client: `C021 NotebookLM Docs`, client ID
  `716364204346-1ino5oasubeqfsth927gulu8t65550qc.apps.googleusercontent.com`.
- Approved account: `jeremybradford1977@gmail.com`.
- Scope added to declarations: `https://www.googleapis.com/auth/drive.file`.
  Google displayed "Data access changes saved!"; the other four non-sensitive
  entries remained, sensitive count remained 26, restricted table remained empty.
  No other checkbox or existing declaration was changed.
- Consent app remained Codify, External, Testing, with the expected test user.
- Private directory: `~/Library/Application Support/C021_notebooklm-mcp/oauth/`,
  owner-only mode 0700. Its parent C021 directory was also created mode 0700.
- The explicitly supplied Downloads JSON was copied to `client.json` mode 0600,
  checked as a regular non-symlink bounded file, validated with the merged loader,
  and matched to the configured client ID. Its original was retained.
- `publisher.json` is mode 0600, with the exact login-Keychain path, client ID,
  expected email, verified permission ID and empty destinations. No tokens appear
  in this nonsecret file. Offline diagnosis returned configuration_valid with no
  credential access before enrollment.
- Store: `/Users/jeremybradford/Library/Keychains/login.keychain-db`.
- Service: `c021.notebooklm.google-data-oauth.v1`; account is the email above.
- Source: reviewed OAuth worktree at
  `e06b7ba6b5886ceefeeed2a2917322d2938f1a1a`, identical source to merged PR #13.
  PR #14 / origin main at preflight was
  `08aaa57249bba6e23aea89e17f68815bb3329b11`.
- Interpreter: existing f8ea worktree environment resolving to
  `~/.local/share/uv/python/cpython-3.13.11-macos-aarch64-none/bin/python3.13`.
  No package or canonical installation was changed.

One explicit google_oauth_setup enroll process used the merged PKCE/loopback
flow. The consent page showed only file-limited Drive access for the expected
account. During browser interaction its page advanced before the queued Continue
action, which returned a stale-element error; this receipt does not attribute
that final browser action to Betty. Chrome subsequently displayed
ERR_BLOCKED_BY_CLIENT on the loopback page. No browser protection was bypassed or
callback manually replayed. The enrollment process independently reported
consent_received_not_stored with the expected client/email and permission ID
`00142650280214084797`, demonstrating that it had received and exchanged the code
and verified Drive identity. Betty supplied the approved email confirmation to
the waiting CLI. Public KeychainStore creation succeeded; CLI reported grant_stored
and exited 0. No existing item was replaced.

## Fresh-process result

The observed permission ID was pinned in configuration. One separate Python
process loaded the config, read exactly the selected grant with
`interactive=False`, parsed it, checked configured identity, and called
OAuthClient.refresh once. That implementation re-verifies Drive identity and
rejects unexpected scope or refresh-token replacement. It exited 0 with:

```json
{
  "status": "fresh_process_refresh_verified",
  "keychain_interaction": false,
  "email": "jeremybradford1977@gmail.com",
  "permission_id": "00142650280214084797",
  "scopes": ["https://www.googleapis.com/auth/drive.file"],
  "access_expires_at": "2026-09-27T21:56:44.253375+00:00",
  "refresh_expires_at": "2026-10-04T20:55:53.995156+00:00",
  "doc_operations": 0
}
```

No secret/client JSON contents, access token or refresh token was printed or
committed. No Keychain search, deletion, unlock or access-control change occurred.
No Doc operation, repository upload, NotebookLM generation, shared cookie repair,
old-writer/mirror change, canonical pull or schedule activation occurred.

## Limits and next ownership

This establishes the public production-item enrollment and no-dialog fresh-process
read/refresh in this Mac user/interpreter context. It does not establish native
locked/denied behavior or launchd acceptance. The actual Testing refresh expiry
is October 4, 2026 at 20:55:53 UTC; this is not durable nightly operation. Absence
of a future error or a successful refresh does not waive that expiry.

WOR-188 remains open for remaining host and live-publication acceptance. Shared
publishing/branding changes require their separate bounded decision; renewal is
explicit and never automatic. WOR-191 owns real-source publication and artifact
acceptance, WOR-189 the old-writer/mirror/scheduler cutover, and WOR-192 operator
guidance. No source/runtime code changed in this receipt PR. Jeremy remains sole
merger and activation authority.
