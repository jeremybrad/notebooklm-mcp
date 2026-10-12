# Guarded existing-original admission — tested local source

## Trigger and authority

The next selected repository has an already populated original Markdown Drive
file and verified NotebookLM identity, but no inspected C021 managed publication
binding. Existing `bind_empty` correctly refuses nonempty files. Clearing,
duplicating or constructing unverified state would discard the truthful base.

Jeremy approved the existing owner's source-only addition on October12:
Sentinel_cb297b75991c81919e74137479f92858, relayed by parent
01a103c6-ab37-730f-b6bd-88206f9b303d. Scope: guarded adoption, synthetic tests,
documentation and receipt/changelog; stop at tested local source. No live
admission, credentials, uploads, imports, activation, publication or model calls.

## Isolation and ownership

Fresh-main isolated clone/branch `codex/nonempty-original-adoption`, base
`6aa89d09367a63568ca5b92796916bfeb04e2247`. Explicit remote fetch was performed
only in this clone after sandbox DNS failure; supported host fetch succeeded.
Canonical checkouts and prior worktrees/local changes were preserved. The fresh
open-PR lookup found none; retained worktree inventory showed no adoption branch.
Parent assigned the existing preparation owner. Unseen private sessions are not
certified absent. No worker/model reviewer was launched.

Instructions read before edits: root AGENTS.md and CLAUDE.md; publisher and OAuth
guidance; individual-source workflow, existing source/state/transport/test code;
test-driven-development skill. User scope overrides installation/auth-recovery
recipes. No dependency, configuration, workflow, installed runtime or C010 source
change is included.

## Resulting behavior

`bind_existing_original` is an explicit library operation, separate from unchanged
`bind_empty` and ordinary publication/reconciliation. It checks the approved old
SourceText/receipt against the supplied immutable commit and regular Git blob,
including cryptographic blob identity and exact UTF-8 bytes. Under the existing
map transaction it rejects existing/pending paths, wrong notebook and duplicate
cloud-file bindings across original/native-Docs entries. It calls only the supplied
read transport; the existing GoogleMarkdownTransport enforces account/destination,
parent, owner-only complete ACL, MIME/editability, full bytes and coherent ETag.
No arbitrary transport is independently qualified by this state API.

Only exact old remote bytes may become verified base state, with fresh ETag and
source provenance. Optional expected_etag must be strong and match the read.
Notebook attestation remains null; enrollment/citation evidence is separate.
Other map records survive unchanged; compare-before-save refuses concurrent edits.
No upload, emptying, enrollment, credentials or new CLI/scheduler path is added.

Existing private atomic operational receipt sink is reserved before remote access.
The admission-specific receipt records hashes/provenance and truthful map effect,
not raw content, cloud IDs or exception text. Ordinary refusal is failed; save
ambiguity records save_outcome_unknown. Receipt failure raises even after local
state was saved: no automatic replay, rollback or invented successful receipt.
Operators retain separate admission/publication receipt directories and inspect
state read-only after ambiguous persistence. Crash-complete auditing is not claimed.

## Synthetic verification

Existing dependency environment, source selected through explicit PYTHONPATH; no
install or credential access. All new source repos/maps/remotes are fictional
temporary fixtures; HTTP uses MockTransport and OAuth loopback tests use fictional
localhost callbacks without a real browser.

- RED: 23 admission cases failed for the missing API before production code.
- Additional RED: committed symlink with matching bytes was incorrectly admitted;
  regular-file Git-mode enforcement fixes that regression.
- Additional RED: a same-named nested directory was incorrectly accepted as the
  source root; actual Git-root validation and receipt-root exclusion fix it.
- Focused: `python -m pytest tests/test_individual_publication.py
  tests/test_publication_state.py tests/test_google_markdown_transport.py -q
  --tb=short` — final **93 passed** in9.70s.
- Full sandbox suite: `python -m pytest -q --tb=short` — **765 passed,1 skipped,
  25 failed** in46.48s, all OAuth loopback socket tests returned loopback_unavailable.
- Same full synthetic suite in tool-approved normal host context — **790 passed,
  1 skipped** in46.32s before the root-boundary fix; final rerun after that fix
  **791 passed,1 skipped** in46.71s. No guard was disabled and no production auth
  route ran.
- Changed Python AST syntax and Git whitespace inspection passed.

Tests cover exact base/provenance, mismatch/empty/weak-tag/read refusal, actual
synthetic HTTP account/permissions/coherent-read guards, original/native duplicate
binding, existing/pending/notebook refusal, concurrent map preservation, uncertain
save and receipt failures, zero upload admission, preserved sibling state and later
existing conditional changed/no-op behavior. bind_empty nonempty refusal remains.

Detailed test logs remain outside the proposed repository diff in the task folder:
nonempty-adoption-focused-tests.txt, nonempty-adoption-full-tests.txt,
nonempty-adoption-full-host-tests.txt and nonempty-adoption-full-host-final-tests.txt.
The existing filesystem case-sensitive
manifest test is skipped on this host; no skipped new admission case is claimed
passed.

## Stopping point and remaining gates

Tested local five-file source diff only. No commit, push, PR, independent model
review, merge, live binding, Google request, NotebookLM query/selection/import or
runtime change occurred for this implementation. Current-source independent review
and repository publication/merge remain separate governed steps. Later real
admission and same-file refresh require their exact operational release, fresh
account/ACL/ETag/raw-base and managed-state checks plus notebook mapping/selections.
Existing C010 acceptance remains completed and untouched.
