# WOR-188 — synthetic OAuth publisher acceptance

## Approved experiment

On 2026-09-27 Jeremy approved "Plan approved - please proceed!" in Codex task
`01a0d946-629f-7580-9cdb-972daf9c3ab6`. The concrete plan authorizes the existing
exact C021 grant, one private synthetic My Drive root Doc, isolated config/map,
publication A then B then unchanged B, four refreshes, one creation and at most
two content writes. Each phase is capped at two minutes; overall fifteen minutes.
Failures and uncertain results stop without automatic retry or repair. Real repo
uploads, NotebookLM operations, broader scope, consent, shared publishing changes,
installation, schedules and deletion are excluded. Doc/evidence are retained.

PR15 was verified merged as `0327809e518d538804555e67d55985af811eb3b3`, with full
tree equality to assessed `f08f79d79ea4a2a502b57e7a95e00e662e34939e`. The executed
source remains reviewed OAuth head `e06b7ba6b5886ceefeeed2a2917322d2938f1a1a`;
later commits are receipts only. Existing Python3.13.11 environment is retained.

## Prepared inputs

Entirely fictional four-file fixture, no remote or real repository content:
README.md, META.yaml, CHANGELOG.md and 10_docs/public.md. Packaged manifest
`bc0e879ef6d9`; existing selector/bundler used without exclusion changes.

| Version | Commit | Bundle SHA-256 | Bytes |
| --- | --- | --- | --- |
| A | df26e2a24f14bf40fa8cae4e855e05aeb1241824 | 6eff8605f93dc9fd46f696a3bd6620e96efbdc3101383f6afb2591c8ba2fbf8a | 1264 |
| B | 9ec7d590a697985e2640c626c9c47623508b5135 | 6ad375446233882a90cf8a6a048267fea93c818f311fedb6ddaaa33e380f5955 | 1281 |

Both existing publisher CLI offline plans passed as unbound/offline; no map or
credential access. Local inputs, operational scripts and evidence live under
`~/LocalWork/Codex/c021-oauth-enrollment/synthetic-publication/`.

## Attempt 1 — stopped before creation

The single-use supervisor executed bootstrap once. Exact Keychain read with
interaction disabled, grant/account checks and one OAuth refresh completed before
the next operation. `GET https://www.googleapis.com/drive/v3/files/root` with
`fields=id,mimeType` returned **HTTP404**. Bootstrap and supervisor exited **1**;
child stderr was empty. No retries ran.

The code reaches creation intent only after that lookup succeeds. Both
`creation-intent.json` and `created-document.json` are absent. The map, synthetic
config and all three publication-phase outputs are also absent. Therefore no
create POST, Doc content write or local binding was attempted. The executed
script and single-use reservation remain unchanged.

Evidence: `bootstrap-started.json`, `bootstrap-failure.json`,
`bootstrap-supervisor.json`, `execution-reservation.json`, plus `bootstrap.py`
and `run_once.py` in the local directory above. The fixed failure code is
`http_404`; no raw HTTP error body, bearer or secret was logged.

## Diagnosis and proposed continuation

Known: the explicit root metadata request was refused after successful refresh.
Unknown: exact reason for that404; it can mean inaccessible or nonexistent
resource. Google's [folder guide](https://developers.google.com/workspace/drive/api/guides/folder)
documents root as a valid alias. Broadening scopes or guessing another ID is not
justified by this evidence.

The root lookup was an unnecessary preparation assumption. The official
[File.parents contract](https://developers.google.com/workspace/drive/api/reference/rest/v3/files)
places a newly created file in My Drive if parents is omitted. A bounded second
attempt is prepared, **not executed**: omit parents in the one creation request,
record returned Doc/parent metadata, require exactly one valid parent, and perform
the same owner-only/empty-Doc checks before adoption. Pin the returned parent for
subsequent publication. No existing-file search, scope widening or permission
change is proposed.

`attempt-2/AMENDMENT.md` and separate scripts preserve attempt1. Both new scripts
compile and default to prepared_not_executed without credential access. The
proposed continuation needs four additional refreshes (five total across both
attempts); overall creation/content-write ceilings remain one/two. It retains
the same immutable fictional A/B inputs and all stop conditions.

Jeremy's bounded continuation decision is pending because attempt1 reached the
approved stop condition. This is neither a successful publisher test nor a code
fix. WOR-188 remains open; Betty owns continuation after that decision. All
unattended, real-source and scheduler conditions remain open.

## Attempt 2 — approved and successful

Jeremy replied "Approved" to the bounded continuation in the parent task. The
approval was recorded on WOR-188 before execution (comment
`b4c4b513-d01a-42d0-901b-8f5e2717a969`). This supersedes the pending decision above.
Exactly one revised supervisor invocation ran; its four phases exited 0 with
zero stderr bytes. No fallback or retry occurred.

Bootstrap created one native Doc using the documented default My Drive location,
recorded its returned ID/parent, and passed the merged transport's account, parent,
sole-owner/owner-only permissions and empty-Doc checks before binding:
[retained synthetic Doc](https://docs.google.com/document/d/1M43-BOcK2spshx8pMebbVBSQSaaaHgjK0Bzub5Kfgts/edit).
The Doc ID remained `1M43-BOcK2spshx8pMebbVBSQSaaaHgjK0Bzub5Kfgts`; parent
`0AK0ss4S7aAQfUk9PVA`, tab `t.0`.

| Phase | Completed UTC | Action | Remote verified | Run ID |
| --- | --- | --- | --- | --- |
| A | 2026-09-27T21:45:14.272068Z | replace_text | 1 | c479d13fb86d4a67b9d45b5397e5e0c8 |
| B | 2026-09-27T21:45:16.515907Z | replace_text | 1 | 855fad6396df409086634f4684ef3611 |
| B repeated | 2026-09-27T21:45:17.730715Z | unchanged | 1 | 6f1891a82a2b40d882fed9fc3d45e145 |

A/B hashes exactly match the prepared inputs above. The unchanged branch reads
remote content and verifies it without calling transport.write; source inspected
at the pinned executed head. Final map records B's verified hash/revision,
`pending: null`, no NotebookLM attestation and no artifact attestations. Local
verification confirms phase output equals its disk receipt after excluding the
CLI-added receipt_path field. An initial literal-equality assertion detected only
that expected wrapper field; no live operation was repeated. The shared account
config still has no destinations; this fixture uses only its separate config/map.
Four refreshes occurred in attempt 2, five across both attempts, with one Doc
creation and two content writes total.

Evidence remains under the original directory's `attempt-2/`: immutable approval
amendment/scripts, creation intent and metadata, bootstrap result, phase supervisor
results, three publication receipts, map/config and execution-result.json. No
secret, bearer, source text or raw HTTP error body is included in this git receipt.

This completes the bounded OAuth-backed synthetic publisher acceptance in the
current interactive host context. No new NotebookLM linkage, citation check or
artifact generation was performed by this test; the notebook ID in the fixture map
is an association only. Existing source/artifact evidence remains separate. No
real repository upload, canonical/runtime install, cookie repair, scheduling,
consent renewal, scope change or deletion occurred. Refresh-grant expiry remains
2026-10-04T20:55:53.995156Z; durable consent lifetime, locked/denied/scheduled host
acceptance, real-source/artifact pilot and writer/scheduler cutover remain open
under WOR-188/189/191. Betty owns preparation; Jeremy retains merge and activation.
