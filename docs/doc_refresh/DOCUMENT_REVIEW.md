# Offline documentation attention (WOR-850 bounded preparation)

`document_review.reduce_review` is a pure decision function. It reuses the existing
canonical relative-path normalization and accepts explicit caller evidence; it
performs no discovery, Git command, provider/model call, publication, generation,
persistence, scheduling or integration with PR #34's status view.

Inputs are the last successfully reviewed immutable commit, candidate immutable
commit, a caller-attested complete base-to-candidate path/blob inventory, selected
document SHA-256 values, explicit topic bindings and optional existing pending
review state. The inventory must cover the successful baseline to the candidate,
not just changes since a failed attempt. This function checks evidence shape and
pins; it cannot establish Git ancestry, inventory completeness or semantic truth
without the caller's actual evidence. No path prefix, topic, source profile or
numerical threshold is guessed.

Profiles contain `topics` mapping each named topic to exact `implementation_paths`
and `document_paths`, plus exact `irrelevant_paths`. Selected document hashes must
cover exactly the topic-bound document set. Relevant code or document changes
produce `review_needed`, even if document hashes are unchanged. Explicitly
irrelevant fixture/log changes produce `no_change`. Unknown classifications,
missing inputs, inconsistent blobs, profile/pending mismatches, and deletion or
rename of a bound path produce `blocked`. Existing pending state is preserved on
blocked input; later relevant changes coalesce topics against the same reviewed
baseline, and irrelevant later changes cannot erase pending attention.

The output contains `reviewed_baseline`, `candidate`, `affected_topics`, `pending`,
`state` and fixed validation reasons. It never advances the successful baseline.
Pending output is an in-memory value for the caller's existing review state; no
second registry or serializer is introduced. Accepted `provider`/`model` injection
attempts block without invoking either function. Publication bindings are not part
of the API and remain untouched.

`successful_review_baseline` separately validates an explicit `status: success`
evidence value bound to the exact candidate, canonical profile SHA-256 and exact
selected document hashes. It returns a candidate eligible for the caller's later
baseline, without updating anything. This verifies the evidence contract, not
whether an independent review actually occurred or whether prose merged. Document
changes alone supply no successful review evidence; source publication still
requires approved committed/merged documents and its own existing workflow.

This implements only mechanical attention and coalescing, not agent judgment,
canonical corrections, primer generation, source-profile approval or publication
integration. The existing source-bundle/discovery/selection and publisher remain
in place. The old doc-refresh prompt's date churn, delete/rebuild and automatic
artifact rules are inspected as historical source, not executed or adopted.

WOR-847 source-profile acceptance and WOR-849 deferral, source-observation, retry
and manual-refresh decisions remain unresolved. Only caller profiles are accepted;
no operational defaults, maximum age or active monitoring policy is introduced.
The C010 on-demand primer remains optional, untracked and nonauthoritative; this
slice does not invoke or change its generator. Integration and independent review
are future prerequisites, and WOR-850 remains open.
