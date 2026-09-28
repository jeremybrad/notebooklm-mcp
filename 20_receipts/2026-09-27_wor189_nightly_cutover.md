# WOR-189 — controlled two-repository nightly cutover

Jeremy explicitly requested failure-handling verification, the full two-repo
publisher in the background, then controlled nightly cutover in Codex task
`01a0d946-629f-7580-9cdb-972daf9c3ab6`. Owning decision WOR-189 comment
`11dc978e-7421-4801-b842-589e421a98be`; WOR-188 crosslink
`8ede6f53-6b2e-4510-bb8b-3815bc14607b`. This is execution authority beyond the
PR23 merge; a source merge alone did not authorize activation.

Fresh fetch and live GitHub verified PR23 merged at 2026-09-28T00:20:01Z as
`ddc659f574355f9eae9c981ca7967485a0d4ede8`, full tree equal to assessed
`f84a53e50b659caddf215cb7bd3517680c1c3067`. Its Current status is MERGED.
The clean canonical C021 main was 18 commits behind, with no unique commits.
Registry entries retained the existing SyncedProjects roots; neither had a
CodeLocal canonical-root declaration. No root migration was performed.

## Failure handling

246 targeted tests passed in 13.35 seconds: Keychain/OAuth/provider, publication
state/batch/CLI and cohort. These cover credential refusal, identity/destination
mismatch, bad source/fetch preflight, cooperating-writer exclusion, uncertain
writes, pending-state recovery without replay, partial batches and receipt
persistence failure. These are synthetic tests, not claims of actual cloud faults.

Actual native locked-store refusal was separately observed with Python 3.13.11
and the unchanged production `_SecurityBackend`. An isolated owner-only local
fictional Keychain contained one dummy value. Its positive read passed; only its
verified non-null reference was locked. A fresh bounded process disabled
interaction and received `access_denied` when reading that locked fixture.
Both phases exited 0 with zero stderr and verified interaction restoration.
Default/search-list snapshots before/after were equal. The fixture remains
locked; production login Keychain, item ACLs and credentials were untouched by
negative testing. This establishes native locked-store failure through the
bridge, not production-item ACL-denial or the public selector's full path.
Wrapper propagation is covered by the synthetic tests; real production-item
positive background acceptance was already recorded in PR23.

The fictional filename deliberately excludes `/login.keychain`: Apple source
shows that special filename can enter the search list. No public selector was
weakened to admit the fixture; the same native bridge was called directly.
[Apple Keychain implementation](https://github.com/apple-oss-distributions/Security/blob/main/OSX/libsecurity_keychain/lib/StorageManager.cpp)
was used for preparation, not as proof of this host's behavior; native preference
snapshots establish the observed unchanged preferences.

## Promotion and full background publisher

Fresh cohort planning selected only the already approved five files. Manifest
SHA-256 `836481cb63fa9a8e27b977d5614ef8f2cbddae86789e7a216dd5b4bbd7bd7f1c`:

- C014: two approved journal architecture documents, source commit
  `00524380f7dffb74a21ea3c1b4a206071fa3d555`, bundle
  `d1737541ff2dece5834656931fd1e5878896310a0697beb995fc9d6e4219a384`.
- C021: three approved publisher documents, source commit
  `ddc659f574355f9eae9c981ca7967485a0d4ede8`, bundle
  `cf3e853b8ab1f7d6524e01c369bc57cde65305b0b5783aef575aa3c19178001c`.

Both bundle hashes matched the prior accepted publication. The two existing
Doc/parent bindings matched the existing map and pinned provider; no pending
operation existed. No new repository, source path, destination or notebook was
added. C001 remains excluded.

Exact old plist, legacy map and manual publication map were privately backed up.
The legacy job was loaded but not running; no competing writer was observed.
Only `gui/501/com.notebooklm-mcp.refresh` was unloaded. Canonical C021 was
fast-forwarded to the exact assessed merge above; no package/dependency install.
Approved source/cohort/provider/map files were promoted as 0600 files under
`~/.config/notebooklm-mcp/`, with a private publication-receipts directory.
The old manual map was renamed as an inactive backup so old manual scripts
cannot silently write a second copy. Legacy notebook_map.yaml is unchanged.

One temporary GUI-launchd job invoked the full merged publication CLI with the
promoted files, explicit fetch and the intended interpreter/source/cwd/environment.
Its supervisor capped the child at 600 seconds. The run completed in 7.814 seconds,
child/supervisor exit 0 and zero stderr. Both Docs were remotely verified as
`unchanged`; no content write or creation was required. No retry or prompt.
The terminal receipt is:

`~/.config/notebooklm-mcp/publication-receipts/publication-df3ea4841d39445eb264e06edf7ce4e5.json`

The receipt has status success, exit_code=0, remote_verified_count=2 and the
source/bundle hashes above. Both map entries have pending:null. The temporary
publisher-host-acceptance job was removed and verified absent before activation.

## Installed schedule and maintenance

The existing plist was atomically replaced only after acceptance and bootstrapped
under the same label. Loaded arguments, source environment and calendar were
checked: 02:00 local, RunAtLoad=false, KeepAlive=false. Runs was 0 at inspection,
so no calendar-triggered success is claimed. The new command uses the existing
Python 3.13.11 with explicit `PYTHONPATH`, cohort/map/receipts/provider paths and
`publication_cli publish --cohort ... --fetch`; there is no shell activation.

Active files: publication-sources.yaml, publication-cohort.json,
publication-provider.json, publication-map.yaml, publication-receipts/,
publication.log and publication-error.log under `~/.config/notebooklm-mcp/`.
The original legacy map and separate rclone primer-mirror plist are byte-identical
to their pre-cutover versions; the mirror was never unloaded or modified.

Local evidence: `~/LocalWork/Codex/c021-rollout/nightly-cutover/` contains the
execution plan, native fixture/results, fresh plan, staged hashes/configuration,
private backups, promotion result, background publisher results/terminal state,
and installed-job/activation evidence. It contains no exported production
credential or raw Google document response. No model inference participates in
publication. Independent PR review of this documentation is a separate lane.

A one-time Codex follow-up `verify-first-c021-nightly-publication` is scheduled
for 02:15 local to inspect the first calendar-triggered result and update WOR-189.
It is read-only with respect to runtime/credentials/publication, and is not a
second publishing scheduler or permanent failure-alert service. Missing/stale
receipts and process errors must remain visible; no automatic repair or replay.

Containment is unloading only the new job while retaining the active map,
pending intents and receipts. Do not overwrite current state with a backup or
restart the legacy writer automatically: it targets legacy destinations.
First calendar-run verification remains pending. NotebookLM source refresh,
citations and artifact accuracy are separate from Docs publication; this cutover
does not establish automatic NotebookLM ingestion or artifact regeneration.
