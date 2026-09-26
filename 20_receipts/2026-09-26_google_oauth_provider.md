# WOR-188 — explicit Google OAuth and macOS Keychain provider

## Authority and outcome

Jeremy approved the C021-only Google OAuth and explicit macOS Keychain provider
plan in Codex task `01a0d946-629f-7580-9cdb-972daf9c3ab6`, observed and recorded on
WOR-188 on 2026-09-26. Base is merged PR #12
`4bb71742f4204738e42934cd458360aaeae2d68c`. Approval covers isolated code, synthetic
tests, documentation and independent subscription review through readiness. It
does not authorize live credential reads/provisioning, Cloud changes, consent,
real uploads, canonical installation or scheduling.

The change fills the existing publisher factory seam: explicit nonsecret config,
Desktop OAuth enrollment/refresh, exact native Keychain item, setup CLI and
publication CLI integration. No second vault/service, new dependency, alternate
source selector or model inference route is introduced. Existing bindings and
revision/readback recovery remain authoritative.

## Consequences and files

New `google_oauth.py`, `google_keychain.py`, `oauth_loopback.py`,
`publication_credentials.py` and `google_oauth_setup.py` implement the boundary.
`publication_cli.py` accepts explicit configuration for live modes;
`publication_batch.py` records allowlisted provider error codes. `pyproject.toml`
adds `repo-doc-auth`. Corresponding synthetic tests and `GOOGLE_OAUTH.md` document
behavior and limits; README/CLAUDE/publisher guide and changelog are reconciled.

Only the proposed exact service/account in an operator-selected login Keychain is
supported. No native store was accessed during implementation. Test doubles cover
Security.framework calls and CF ownership. The real no-dialog/ACL/interpreter
behavior remains unverified and requires authorized host acceptance. Global UI
state is restored; failure poisons later adapter operations until process restart.
Renewal uses native update with an expected-byte check, not delete/add; it is not
cross-process CAS and requires an exclusive setup writer.

Consent uses a bounded localhost callback, state and PKCE. Runtime uses only stored
approved refresh grants and pins client/email/Drive permission ID; a changed refresh
token stops. Access tokens are memory-only and never printed. Diagnostic/offline
commands perform no credential or Google I/O. No memory-zeroization claim is made.

## Evidence and remaining acceptance

Full suites passed **651 tests, one filesystem-dependent skip** on Python 3.11.14
and 3.13.11. Coverage: OAuth and native Keychain modules 91%, provider integration
92%, callback 87%, setup CLI 80%; whole package 49%. Offline wheel and source
distribution builds passed. Focused integration passed 69 tests; component agents
verified OAuth, callback and fake-native storage behavior. The OAuth agent reproduced explicit
`scope:null` incorrectly inheriting stored scope, then corrected it with a passing
regression; only absent refresh scope may inherit. Logs/builds are retained in the
parent task's `work/oauth/`. Exact-head independent review and triage will be
recorded on the PR before readiness. Synthetic validation does not establish
native-host access policy or Google production acceptance.

There is no deployed result: the old installed writer, shared canonical checkout,
primer mirror, cookies, Google objects, real-source pilot and schedules were not
changed. Source merge is not credential provisioning or runtime activation.
