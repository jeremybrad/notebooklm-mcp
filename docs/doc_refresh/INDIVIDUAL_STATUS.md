# Offline original-document status (WOR-855 bounded slice)

Read explicit local bindings and publication receipts without creating a new
registry, receipt, lock, cloud request or credential access:

```sh
PYTHONPATH=/absolute/worktree/src python -m notebooklm_mcp.doc_refresh.individual_status \
  --repo /absolute/source/repo FULL_COMMIT_SHA \
  --manifest /explicit/accepted-manifest.yaml \
  --map /explicit/notebook_map.yaml \
  --receipts /explicit/existing/receipt-directory \
  --now 2026-10-03T00:00:00Z
```

The source selection uses the existing immutable Git bundle builder. Bound paths
absent from that selection remain visible. Output includes each original's Git
identity/hash, file and notebook/source identities, verified version, pending
intent, local receipt timestamps, affected path and operator action. An empty
view stays unknown. The aggregate reports attention if any original has a problem;
a successful original cannot hide a failed or missing sibling.

| Local evidence | Report |
| --- | --- |
| Verified publication binding, no observation | recorded_verified publication; unknown NotebookLM observation |
| Target differs from verified hash | changed publication; publication_needed |
| Observation differs from target hash | stale NotebookLM observation, even after publication |
| Observation matches target hash | recorded_hash_match; timestamp remains null |
| Pending operation | preserve original inputs; inspect intent before retry |
| Newer failed or partial receipt | latest_run_failed_or_partial; earlier success remains historical |
| Bound original absent from selection | original_missing_from_selection |
| No matching receipt | receipt_missing |
| Failed preflight with no items | run-level unattributed_preflight_failure, including an empty view; no invented affected source |

`--stale-after-seconds POSITIVE_INTEGER` is an explicit caller-selected comparison
bound, with no active default. It compares the last per-item remote publication
success to `--now`; without it receipt freshness is unknown. Retry limits and
reminder intervals remain unresolved under WOR-849 and are not implemented.
Plan/status success receipts never count as publication success. Failed plan/status
receipts remain failure evidence even though they cannot establish publication. Reconciliation
that verifies the old base does not advance publication success or its age.
Equal receipt timestamps preserve any failure at that timestamp. A partial batch
retains successful item history but still surfaces the batch failure.

Existing individual observations contain a hash, source ID and evidence reference,
but no structured evidence timestamp or opening/manual-sync mode. This view does
not infer either from prose, file modification times or publication timestamps.
It cannot claim observed-current-on-opening, citation verification, continuous
background ingestion or manual-refresh-required from this schema. Binding
verification is a recorded successful readback, never a fresh Google read.

Scheduled success, missed jobs, host availability, canonical-document review and
older artifact state are unknown: these existing receipts do not attest scheduler
invocation or host exits before a receipt. Generic operation failures cannot
reliably distinguish permission, credential or external-edit causes. Invalid,
unreadable or oversized receipt inputs return exit 2 with a fixed message;
a missing map returns exit 2, while an existing empty map exposes missing bindings.
Receipt reads open nonblocking before regular-file validation, are bounded, and
reject symlinks and special files. Per-source failures refer only to receipts
actually mentioning that original; a same-repo failure is not attributed to an
unmentioned sibling. Known individual
receipt families with unsupported versions or modes are refused. Other existing
receipt families are outside this view and do not count as publication evidence;
missing matching evidence remains visible in otherwise valid output. Errors go
to stderr, separate from JSON output. Status
attention is data, not a live monitor exit code. Identical explicit inputs produce
identical output; no alert delivery or transition storage is introduced.

Recovery: keep immutable source revisions, accepted manifest and pending intent;
inspect the exact affected original before separately authorized reconciliation.
Do not widen selection, repair credentials, restart the old writer, recreate
sources or retry a pending write through this view. Notifications, deduplication,
bounded reminders, host monitoring and installation require a later bounded
release, agreed WOR-849 limits and chosen private destination. Live publication
and independent review remain separate prerequisites; this slice does not close
WOR-855.

Historical failed preflights with no affected items remain in `run_problems`,
with their recorded run identity and timestamp. They are not attributed to every
source, and a later source success cannot establish which absent preflight inputs
recovered. No unresolved failure is hidden simply because the view has no rows.
A missing selected target leaves its NotebookLM observation unknown even if an
older observation exists; staleness requires an actual target-hash comparison.
