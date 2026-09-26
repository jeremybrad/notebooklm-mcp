# WOR-188 publisher integration

## Authority and scope

Jeremy said “Approved!” in Codex task `01a0d946-629f-7580-9cdb-972daf9c3ab6`,
approving `outputs/next-publisher-integration-plan.md`. Approval was observed
before 2026-09-26T05:33:49Z, not asserted as its message timestamp. WOR-188 holds
the owning decision; WOR-183/189/190/192 link it. Implementation starts from
merged PR #11 `b28badcd0317761609b9821ae76e43e4cbbd6f69` in isolated worktrees,
with HTTP and batch modules assigned separately and Betty owning integration.

## What and why

Reuse the accepted manifest/Git bundle builder, strict Docs parser/update planner
and existing-map lifecycle. Add a fixed-endpoint Google data HTTP adapter,
explicit credential/account/destination checks, explicit-set batch execution,
terminal failure receipts and safe command interface. This extends the existing
publication path rather than adding another source selector, ledger or scheduler.
The credential provider stays unconfigured. This is new opt-in functionality,
not a claim that an observed production incident has been repaired.

No credential contents, real notebook map, private source payloads, Google objects,
installed packages, canonical runtime checkouts or schedulers are changed.
Tests use fictional Git repositories, temporary maps and mocked HTTP. The receipt
contains no private account/destination identifiers. Model API spend remains $0.

## Evidence and limitations

Initial command tests failed collection because the new implementation module was
absent. Focused tests exercise exact requests and full native responses; account,
scope, expiry, permissions and destination refusal; guarded single-write behavior;
redaction; changed/no-change and partial batches; receipt failures; and uncertain
write reconciliation. A full synthetic Git-to-HTTP integration connects the
existing source selector and state machine to the new transport. Final validation
counts and independent-review captures/triage are on the PR at the exact head.

Publication-state pending intent and readback remain authoritative for recovery.
Terminal-receipt persistence errors are failures, including errors after visible
replacement; abrupt process death can leave no terminal receipt. Receipt failure
does not roll back Google. Permission checks are point-in-time, not an atomic
lock on sharing. Directory/map locking assumes trusted stable local storage and
cooperating writers; old writers must be quiesced before activation.

The complete contract is `docs/doc_refresh/PUBLISHER.md`. Production OAuth
provisioning and live acceptance remain WOR-188; narrow real-source pilot/artifacts
WOR-191; writer/mirror cutover/scheduling WOR-189. No new real-source publication,
nonempty Doc adoption, installed CLI broker, hosted workflow activation or merge
authority follows. Jeremy remains sole merger and runtime authority.
