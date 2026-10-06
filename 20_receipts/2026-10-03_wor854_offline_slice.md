# WOR-854 — local synthetic partial-batch recovery receipt

Recorded 2026-10-03. Baseline `9b852600d31346f51c2eb6c2eb486a5aba2b3ce0`. Evidence is synthetic/local only.

Reproduced original recovery failure with two and three synthetic originals:
first succeeded, second wrote but lost its response, third stayed unattempted.
The original batch reconciliation refused the completed first sibling. The repair
read-only verifies exact current bytes and full provenance of verified siblings,
reconciles only original pending inputs, and never replays an upload. Empty adopted
unattempted bindings receive no transport or map update and keep batch exit 1.
Nonempty/older-provenance unpending siblings remain ambiguous and refuse; changed
commit/blob/manifest/content and existing selection/configuration gates remain.
Verified-base recovery is not proof that target publication happened.

Eight new cases plus existing individual tests: 21 passed. Full existing hermetic
suite with synthetic local sockets enabled: 706 passed, one filesystem skip in
34.23s. Sandbox-only run had 25 loopback socket failures and 681 passes. Strict
new-test Ruff and diff checks passed; source modules retain baseline E701/E702/F401
exceptions. Existing C021 environment, bytecode/cache/plugin autoload disabled:
`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src
python -m pytest -p no:cacheprovider -q`.

Supplemental local review independently inspected the original four-file patch
SHA256 a93da6258404a2382b1485874dcb97fe7a0ea54620e311a5bcc6ecc0270635f4:
41 tests passed including 20 additional cases; no actionable finding reported.
That is local evidence, not an external governance approval. Save/receipt
uncertainty after promotion can leave no pending intent despite a failed receipt;
operator inspection is required, never a blind replay.

Actual single-writer scheduling/cutover, changed and unchanged calendar events,
bounded observation window, missed/failing invocation evidence, separately
approved live permission/conditional-write/fault acceptance, NotebookLM content
and citation observation remain unproved. Existing bundle-service receipts are
separate evidence. WOR-854 remains open.

## Input pins

- `src/notebooklm_mcp/doc_refresh/individual_batch.py`: `b607e373f92f4610625d0965af4f814de383ad40f82a39f44d7f3b564b1f08d8`
- `src/notebooklm_mcp/doc_refresh/individual_publication.py`: `4b044c1670030e213999553f0a2efacdef52136fa940fa12e8a367a4a4afed38`
- `docs/doc_refresh/PARTIAL_RECOVERY.md`: `4596b375e4c91db9a8daa7ca5aee39c307efc64d7e84484574f7e4aa13d5e65a`
- `tests/test_individual_batch_recovery.py`: `31d7c406f1c8893825122f8dfde7b71d8777a6667798c80c86a1cbfb821fdbef`

## Scope and authority

Loaded repository AGENTS.md and canonical CLAUDE.md, PUBLISHER.md, current pinned
C010 rules/review-accounting guidance and relevant source contracts. The local
handoff authorization permits this factual receipt and immutable local pin only.
No push, PR, model invocation, provider/credential call, live publication,
scheduler/configuration change, install, environment creation or canonical edit.
PR34 and the other independent candidate are preserved. This receipt adds no
mandatory per-session policy and asserts no broader issue acceptance.


## 2026-10-06 bounded PR36 repair

Original head `39b5082a5ef025ce1a464388470ef06cc25075a6` remains in ancestry.
Integrated pinned main `38812038b5f8ec31f6f9ce53fc8790c86b372faa` without
rewriting the original work. Incoming PR35 adds four independent review-reducer
files; it does not repair individual recovery or add a production caller.

WOR854-R01/P2: completion now requires an operation result and successful context
finalization. Suppressed operation errors fail the item rather than reporting
remote success. WOR854-R02/P2: a bound transport checks the preflight destination
before forwarding reads or writes, including a binding change during construction.
Source repair stays in individual_batch.py; individual_publication.py is unchanged.

Red-first evidence: six of eight new synthetic cases failed on the unmodified
implementation; two finalization-failure cases already passed. After repair,
106 focused tests passed and the full hermetic suite passed 760 tests with one
existing filesystem skip. Strict regression-file lint, source lint excluding
existing E701/E702/F401 style debt, and diff whitespace checks passed.

Durable logs: `/Users/jeremybradford/LocalWork/Codex/2026-10-06/task-4/repair-red.log`,
`repair-focused.log`, and `repair-full.log` in that same directory.
Wheel/sdist provenance and the one approved repair-review result are separate
exact-head evidence retained in task-4. This receipt records local synthetic
verification; it does not claim an independent clean review, hosted CI, live
publication or broader WOR854 acceptance. PR36 remains draft.
