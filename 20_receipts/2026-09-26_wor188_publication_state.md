# WOR-188 offline publication state and recovery

## Authority and scope

Jeremy approved `outputs/canary/next-offline-integration-plan.md` in Codex task
`01a0d946-629f-7580-9cdb-972daf9c3ab6`, saying “I approve - please proceed!”
after PR #10 merge verification. Approval was observed before
2026-09-26T04:56:24Z, not asserted as the message timestamp. Recorded on WOR-188,
referenced by WOR-183/189. Implementation starts at merged
`8c472136f147bf9c1c84cadca6e5221e9acdd124` in an isolated owned worktree.

## What and why

Add an opt-in state/recovery library extending the existing notebook map, with
versioned stable Docs bindings, side-effect-free local planning, pending intent
before writes, exact readback before promotion, atomic/conflict-aware persistence,
explicit read-only reconciliation, and separate source/artifact attestations.
No second registry, transport, credentials, installed runner, CLI or schedule.
No change to legacy writers; they must be quiesced before future activation.

The local code inspection of legacy map persistence was not a reproduced
production incident; this change adds a bounded new opt-in path, not a claim
that an observed live incident is fixed. No user state was opened or mutated.
Tests use temporary maps and fictional Docs through an injected fake transport.

## Evidence and limitations

The first test invocation failed collection because the new module did not
exist. After implementation, focused lifecycle/failure tests pass: actual
UTF-16 request interpretation, A/B/no-op, stale/invalid readback, lost response,
save failure before/after replacement, pending reconciliation, malformed maps,
symlink refusal, cooperating writer collision, observed external edit, separate
freshness and partial multi-repo completion. A pinned synthetic Git source-bundle
test connects the existing selector to this state machine. Final suite/build
results and independent-review accounting are recorded on the PR at its exact
head; no test count in this receipt substitutes for those results.

Independent review R1 identified PSTATE-F1 (P2): retained artifacts could lose
their source association through an inconsistent persisted map. Two regression
cases reproduced acceptance before repair, then passed after whole-map validation
required each artifact to retain the notebook's stable source ID. Historical
artifact hashes may still differ from the current source hash. Review history
and the repair re-review remain append-only on the PR.

POSIX directory flock serializes cooperating callers without a new lock file.
Atomic replace and before-commit byte checks detect observed conflicts; arbitrary
noncooperating writes cannot be made safe by advisory locking. Activation must
quiesce the old writer and validate host filesystem semantics. A post-replacement
fsync failure is reported as failure even if new bytes are visible; explicit
reconciliation verifies the remote target again. No power-loss durability is
claimed after a failed fsync. Temporary crash residue is not read as state.

Full contract: `docs/doc_refresh/PUBLICATION_STATE.md`. Files changed: new module,
synthetic tests, contract documentation, this receipt and changelog fragment.
No public receipt includes private cloud IDs, account names, runtime text or
credentials. No metered model API, live cloud write, installed auth repair,
canonical pull, worker activation or scheduling action is included.

WOR-188 owns transport/OAuth and remaining integration; WOR-189 owns the future
writer/mirror cutover. Jeremy retains merge and activation authority.
