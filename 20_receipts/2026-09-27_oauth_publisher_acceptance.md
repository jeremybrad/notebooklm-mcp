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
