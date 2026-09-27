# WOR-189 — one-shot launchd fictional Keychain read

Jeremy approved the prepared test with “Approved - No homepage - none” in task
`01a0d946-629f-7580-9cdb-972daf9c3ab6`. The decision was recorded on WOR-189
comment `27009d15-6253-4fa1-9aaa-b2585132c1f7` before execution at
2026-09-27T23:22:08Z. This extended the earlier two-process fictional experiment
only for one bounded background read and its temporary-job cleanup.

PR19 was verified merged as `44f28c55349b9910bfa9757cd5d5979e9bfc9641`, full
assessed tree unchanged. The native bridge used here remains byte-identical to
the PR14 acceptance bridge; no runtime implementation changed.

## Execution and evidence

The prepared temporary `com.notebooklm-mcp.fixture-host-acceptance` agent was
bootstrapped from local scratch into `gui/501`, with RunAtLoad=true,
KeepAlive=false and no interval/calendar/watch trigger. Nothing was installed
in Library/LaunchAgents. One supervisor launched one child capped at 30 seconds,
with an exclusive reservation preventing replay; no retry occurred.

Interpreter: canonical C021 `.venv/bin/python`, Python 3.13.11, executable SHA-256
`15ed8b98c16a73bef4cb3071d20059c15c972630c6008847a42d5d2c756b18c5`.
It used `-I -S` and the separately pinned merged native bridge SHA-256
`98701d43057cc7e27e835dd72b8ff477ff2b1cee052953f7ea88b807cccec1d4`.
The canonical repository was not pulled or installed.

Read only the retained PR14 fictional item from the exact login Keychain:
service `c021.notebooklm.google-data-oauth.canary.01a0d946-629f-7580-9cdb-972daf9c3ab6`,
account `fictional-native-canary`. The pinned canary verify phase disabled and
checked interaction, compared literal version B, released the reference and
restored/checked the prior process setting.

Observed result: bootstrap 0; child 0; `ok: true`, `created: false`,
`completed: [read_B]`, `interaction_restored: true`; child and supervisor stderr
both zero bytes. Elapsed supervisor experiment approximately 1.034 seconds.
Bootout returned 0; subsequent launchctl inspection confirmed the temporary
label absent. Before/after legacy-job state was identical. No Keychain item was
created, changed, deleted or unlocked; no ACL or real grant was accessed.

Local evidence is retained in
`~/LocalWork/Codex/c021-rollout/host-acceptance/`: authorization, bootstrap,
started/result, terminal-job state, bootout/absence, legacy before/after and
host-summary JSON. Prepared script and plist hashes remain in PROPOSAL.md.
Five fake-child supervisor checks and eight existing canary checks passed before
execution; syntax, plist and input pins passed. Those synthetic checks are not
native locked/denied evidence.

## Limits and remaining work

This establishes the fictional read through the intended interpreter in the
observed GUI launchd context. It does not establish the production item's access
policy, locked/denied native behavior, Google refresh lifetime, full publisher
acceptance or first recurring run. No Google request, Doc/NotebookLM publication,
Cloud setting, credential renewal, canonical pull or recurring job change occurred.

Jeremy confirmed no homepage/privacy pages exist. The next OAuth preparation is
truthful C021 page text and a hosting decision; shared Codify3030 publishing is
still blocked on Branding. Seven clients share the project, so C021-only draft
text is not yet a complete statement about that shared app. No page is published.
Nightly cutover, automatic NotebookLM freshness, prior infographic correction
and spoken-audio accuracy remain open. This receipt adds no runtime authority.
