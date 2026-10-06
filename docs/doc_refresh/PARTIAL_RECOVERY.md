# Individual partial-batch reconciliation

WOR-854's local recovery slice supports an original immutable selection after an
individual publication stops partway through. This is synthetic proof, not proof
of scheduled reliability, live conditional-write qualification, or NotebookLM
content/citation observation.

For each repository, reconciliation requires at least one pending intent and the
existing complete-selection gate. All bindings and original pending bytes, commit,
blob and manifest provenance are preflighted before any transport is entered.
A selected sibling without pending intent is accepted only if its verified hash
and complete source provenance exactly match the input, or if its binding is still
an empty adoption with no source provenance. Other nonpending siblings are
ambiguous and cause the entire preflight to fail. In particular, an unchanged
publication with older provenance does not establish an exact recovery sibling.

An exact verified sibling receives a read-only remote byte/identity check and a
`verified_sibling` success item; its stored verified state is preserved. Pending
items use the existing read-only reconciliation: `verified_target` or
`verified_base`, never an upload. External content matching neither target nor
base fails and retains pending intent. An empty nonpending binding receives
`not_pending`, remains `not_attempted` with offline verification, and receives no
transport access or map update. A batch containing such an unattempted tail keeps
its failed status and exit code 1, even when the uncertain write is reconciled.
Recovery success is not completion of the original publication batch.

A subsequent explicit publication is a separate decision. Repeating reconciliation
after all intents clear refuses before transport access. This slice does not infer
a batch identity for previously published changed siblings, enroll destinations,
activate schedules, access credentials or retry writes. Those broader cases need
explicit original-run evidence and remain outside the supported narrow recovery.


Destination access stays pinned to each preflight binding, including when the map
changes during transport construction. A changed destination fails before the
underlying transport receives a read or write. Operation completion and successful
context finalization are both required for a remote-success receipt. Suppressing
an operation error cannot turn an incomplete verification into success; the batch
fails and leaves later items unattempted. A finalization failure after a completed
state transition still reports failure; it does not roll back verified state.
