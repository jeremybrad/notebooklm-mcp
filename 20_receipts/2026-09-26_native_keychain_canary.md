# WOR-188 — approved fictional native Keychain experiment

## Authority and purpose

Jeremy approved "Approve this fictional Keychain test" in Codex task
`01a0d946-629f-7580-9cdb-972daf9c3ab6`, observed/recorded on 2026-09-26 at
10:07 UTC. Approval selected the exact login-Keychain path, existing Python
3.13.11 interpreter, one fictional item, two processes capped at 30 seconds each,
and retention of that item. It excluded real credentials, Google calls, deletion,
unlocking, access-control changes and scheduling. Betty executed it once.

PR #13 was first verified merged as
`963e1e706e3cb0c9e767b3337d4427ac905af817`, with complete tree
`e6f2b18e2df1dbcd68cc493ea7400f229875c5b6` identical to reviewed head
`e06b7ba6b5886ceefeeed2a2917322d2938f1a1a`. No runtime installation or canonical
checkout pull followed the merge.

## Exact experiment

- Store: `/Users/jeremybradford/Library/Keychains/login.keychain-db`.
- Generic-password service:
  `c021.notebooklm.google-data-oauth.canary.01a0d946-629f-7580-9cdb-972daf9c3ab6`.
- Account: `fictional-native-canary`.
- Interpreter:
  `/Users/jeremybradford/.local/share/uv/python/cpython-3.13.11-macos-aarch64-none/bin/python3.13`.
- Execution flags: `-I -S`; dedicated processes, no input required.
- Bridge: merged private `_SecurityBackend` from `google_keychain.py`, checked
  against SHA-256 `98701d43057cc7e27e835dd72b8ff477ff2b1cee052953f7ea88b807cccec1d4`.
- Values were literal fictional A/B strings containing no credential or repo data.

The first item operation was atomic creation. A collision would stop without
reading/updating that item. Interaction was disabled and its setting verified
before opening the exact store. The first process created A, read A, verified
duplicate creation refused and preserved A, updated to B and read B. Only after
its success did a second process read B. Both released their store reference and
restored/verified the prior interaction setting. No selector translation,
production service/account, store search or public-provider invocation was used.

## Result and evidence

The single execution at 10:07 UTC exited **0**, with **zero stderr bytes**.

| Phase | Result | Completed operations | Interaction restored |
| --- | --- | --- | --- |
| First process | Success; item created | create A, read A, duplicate refused, update B, read B | true |
| Fresh process | Success | read B | true |

The actual fictional item remains with version B, as approved. No retry or cleanup
ran. Its creation and readback are the only live data changes in this experiment.

Task-local evidence, under
`/Users/jeremybradford/Documents/Codex/2026-09-25/hey-betty-as-you-know-i/outputs/`:

- `keychain-native-canary-result.json`: redacted execution result.
- `keychain-native-canary.py`, SHA-256
  `3f409d21de94a2c3015172c5d15751ad66924059f3b137826143b81e95b4acb6`.
- `test_keychain_native_canary.py`, SHA-256
  `e5383ac5c32762fd5131303837028010174acd9382c90b6fbd110a8454487196`.
- Pre-execution `native-keychain-acceptance-plan.md`, SHA-256
  `e70ee3ef59383b4a14d8c3e77cb509aa4d39d8813a9b90e6d62b6afc23e66c6c`.

Eight fictional-backend/supervisor checks passed before execution. A preparation
assessment caught a worker-phase CLI shortcut bypassing supervision. It reproduced
without native access, was removed, and the refusal/failure-gating/timeout checks
passed; the assessor verified that specific repair. This was preparation of an
operational harness, not a further review round of merged PR #13.

## Limits and remaining work

This establishes the private native bridge's selected-store operations and access
across two processes in the tested Mac context. It does **not** establish native
locked/denied behavior, the public production-item lifecycle/access policy,
Google OAuth, or launchd readiness. Those conditions remain pending before
unattended activation. Fake denial tests are not real locked-Keychain evidence.

No real grant, client file, token or production Keychain item was accessed; no
Google request, consent, upload, lock/unlock, access-control edit, deletion,
canonical installation/pull or schedule change occurred. The harmless fixture
remains intentionally; removal would be a separately authorized exact-item action.

WOR-188 remains In Progress. Jeremy identified the intended Google Cloud project
as **Codify3030**; its project ID, Desktop client and consent settings have not yet
been verified. Betty owns the setup assessment and separately approved enrollment.
WOR-191 owns the real-source pilot, WOR-189 the old-writer/
mirror/scheduler transition. This receipt and its changelog entry are the only
repository changes; neither changes runtime behavior or grants new authority.
