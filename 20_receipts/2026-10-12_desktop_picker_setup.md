# Same-app Desktop Picker setup — tested local source only

## Authority and inspected base

Jeremy approved the nine-file implementation, synthetic security tests,
documentation and receipt, stopping at tested source:
`Sentinel_dc9b0f9319748191baafd039b4dfa18c`, following the bounded design
`Sentinel_4208e147e11881918140c56ca60befb2`, relayed by parent
`01a103c6-ab37-730f-b6bd-88206f9b303d`.

A new isolated checkout at `desktop-picker-source`, branch
`codex/desktop-picker-select-file`, starts from verified PR38 merge
`c2a83d4b5781a02ba0d9c8e3d6a411a60f120688`, tree
`c6fde6339b1036b6da7e2cdbd4b6e340ddc54c29`. Canonical repositories and the
retained C017 operation checkout/caller were not advanced or changed.

Loaded instructions: C021 root AGENTS.md and CLAUDE.md; publisher/OAuth setup
operator guidance and current bounded design/approval. No nested AGENTS.md or
CLAUDE.md was found under src, docs or tests. The prior TDD workflow and approved
brainstormed design informed this bounded change; no additional source or live
permission was inferred.

## Resulting source behavior

Explicit `select-file --config PATH --file-id ID` operates only against an
existing grant and pinned account/permission/client. It forbids alternate client
configuration, discovery and missing/invalid file IDs. It reuses the stored
Desktop client, exact drive.file scope and existing PKCE/state/loopback protections.
Legacy diagnose/enroll/renew interfaces and consent behavior are unchanged.

The Picker URL's one-file filter is only a UI filter, not claimed as an OAuth
allowlist. The application receiver independently enforces an exact singleton
picked_file_ids result. Wrong/missing/repeated/multiple selections, matching-state
duplicate parameters, unexpected callback scope and mixed code/error results are
terminal before exchange, rather than replaceable by a later callback. Invalid
protocol or wrong-state frames remain bounded refusals. The listener closes on
success, denial, refusal or timeout; each new invocation has fresh state/PKCE.

The exchanged grant is strictly reparsed and checked against the existing client,
account/permission and exact scope. Only typed account/file confirmation permits
noninteractive expected-byte update of the existing selected Keychain item and
exact readback. No new item, automatic revoke/rollback/retry or provider/map change.
A competing update is refused; any other interrupted/failed update or uncertain
readback reports credential_persistence_unknown even when bytes changed. Google-side
consent is not falsely claimed rolled back after local failure or refusal.

No file metadata/ACL/raw media read or publication follows setup automatically.
Cloud API enablement, actual browser consent/code exchange, credential access/update,
installation, native existing-file verification and later publication remain
separately owner-controlled. The unrelated stopped MCP server was not restarted.

## Synthetic verification

Initial RED:27 Picker feature cases failed for absent URL/receiver/setup support.
A further RED found that a matching-state mixed code/error callback could be
replaced by a later valid callback; the new Picker branch now refuses it
terminally while legacy callback behavior remains unchanged.

Final guarded commands, using the already available C021 Python environment and
source on PYTHONPATH, ran an external verification-only wrapper which fails any
real socket/browser/HTTP/Security.framework/Keychain operation. HTTPX traffic is
allowed only with MockTransport; fake opener, socket listener, clock, OAuth and
credential-store fixtures handle the Picker cases. The guard and logs remain in
the task folder outside this nine-file repository diff.

- `desktop-picker-offline-guard.py tests/test_google_oauth.py tests/test_google_oauth_setup.py tests/test_publication_credentials.py -q --tb=short`:
  **137 passed in1.49s**.
- `desktop-picker-offline-guard.py tests/test_oauth_loopback.py -k 'picker or invalid_timeout or import_has_no_browser_or_listener_side_effect' -q --tb=short`:
  **36 passed in0.05s**,25 real-localhost legacy cases deliberately deselected.
- **63 new Picker cases** collected across the three corresponding test files.
  Guarded checks total173 distinct tests, including legacy OAuth/setup/provider
  regression and pure legacy receiver compatibility. The initial source-only phase did not run the full suite or native
  listener; live browser, real Keychain and Google acceptance remain unqualified.
- Changed source AST syntax and Git whitespace checks passed.

Cases include strict request flags and default compatibility; malformed selector
before credential/listener access; exact callback/nonce/Host/path checks, denial,
replay, fresh PKCE, timeout/closure and terminal selection mismatch; pre-consent
existing-grant and post-exchange client/account/permission/scope refusal; declined
confirmation; an actual fictional concurrent-byte change preserved on conflict;
post-write failure and mismatched/failed readback without retry; credential/code/
secret redaction. Unexpected real external/native access fails the tests rather
than providing a false negative-path pass.

## Retained operational stop and remaining prerequisites

The frozen C017 caller, manifest, source pins, protected files and failed attempt
remain unchanged. Its earlier native attempt used one refresh, three Drive GETs
and one failed snapshot attempt, with zero admission/map creation/PUT or browser
question/selection mutation. The file metadata HTTP404 remains inaccessible-or-
nonexistent evidence, not a proven named app-authorization error. This source
work performs no retry and grants no access.

Initial source-only work stopped at tested local nine-file source. No dependency/
configuration change, installation, Cloud enablement, live credential read,
consent or Google provider call occurred for this feature. Review and
source publication are later governed work. A live owner must confirm Picker API
in the same existing Cloud project, obtain explicit consent/storage authority,
coordinate exclusive credential writers (the adapter is not cross-process CAS),
verify the live flow and only then obtain a separately bounded exact-file native
preflight/operational release. Offline fixtures do not establish those facts.

## Approved publication verification follow-through

Jeremy subsequently approved full synthetic localhost verification, offline
packaging, one draft PR, a guarded Codex subscription review plus conditional
repair review (one attempt/1800seconds each, $0 metered/no fallback), and one
nine-path repair cycle through governed readiness, stopping for Jeremy's merge.
Approval `Sentinel_2014e3e62bf48191a2634cb76afab4bf` replied to
`Sentinel_14ece112ca0c81919bb07ad293ff884a`, relayed by the same parent. No CI
activation/dispatch, real credentials/consent/API enablement, install or C017 retry.

The first full run passed830tests/1skip and failed25legacy cleanup probes because
the verification guard rejected their deliberately attempted connections to closed
test ports. This was a harness issue, not a source defect. The corrected guard
permits only127.0.0.1 ports allocated by that test process, including subsequent
closed-port probes; real HTTP must use MockTransport, real browser/native-framework
access is forbidden, and unexpected thread failures fail verification.

Final full guarded suite: **855 passed,1 skipped in48.05s**. All25 formerly excluded
localhost cases passed. The skip is the existing filesystem-case distinction test
on this Mac; no Picker case was skipped. No product repair was required. The full
suite command used the existing interpreter with source on PYTHONPATH and
`desktop-picker-loopback-guard.py desktop-picker-source/tests -q --tb=short`.
Logs/guard remain outside the nine-file diff. Offline uv build uses existing cache
only; wheel/sdist module bytes and unchanged console entrypoints are inspected
and recorded separately in the task's package evidence.

Fresh GitHub verification: base stillc2a83d4b5781a02ba0d9c8e3d6a411a60f120688,
no open PRs, main unprotected/rulesets empty, CI disabled_inactivity. No hosted
pass is claimed. Actual pinned WOR896 G1/G2 rules do not match the unchanged
C021 test/build/current Codex runner commands; no blanket Codex hold applies.
Isolated maintained C010 controls are4e1cb83102ea8af883a2a6c3391df5a227dfbd49;
protected canonical C010 remains5f2699386e807c7599815accf6c1982188493564.
PR review/status accounting will record actual committed head/base/results; this
receipt is not a review result, merge grant or operational setup release.

## One approved review repair

PR39 R1 reviewed head81d796f2b16263f5b9a66f54f21123ff8cef872c, full nine-file
scope,21:45:18–21:45:37UTC, guarded Codex gpt-6.1-sol, one attempt/1800seconds,
subscription only. DP-001 (medium) found duplicate current state was returned as
an untrusted frame before terminal duplicate-parameter handling. A later valid
callback could therefore replace it, contrary to the documented Picker contract.

Two fictional queued-callback regressions reproduced RED for repeated-current and
mixed wrong/current state values. The approved repair checks for any current nonce
among duplicate state fields in Picker mode and refuses terminally. All-wrong
states remain untrusted; legacy duplicate-state behavior is unchanged. Tests now
verify first-peer/listener closure and refusal before returning a code, so setup
cannot exchange that callback. Primary result/finding identity remains in the
append-only PR ledger; no reset or unrelated source change.

Repair checks:39guarded receiver cases passed0.07s; full guarded synthetic suite
**858 passed,1 existing filesystem-case skip in47.28s**, including all legacy
localhost checks. The patch is4source lines plus regression tests/expectation and
this receipt. Offline packaging is rebuilt for the actual repaired source/receipt;
byte/entrypoint verification and final review/triage live in task artifacts and
PR accounting. Only the conditional second review remains authorized; no third
review, second repair cycle, live setup, API/credential change or C017 retry.
