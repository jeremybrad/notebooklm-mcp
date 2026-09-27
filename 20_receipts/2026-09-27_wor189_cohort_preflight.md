# WOR-189 explicit cohort preflight

## Authority and purpose

Jeremy approved the staged rollout in task `01a0d946-629f-7580-9cdb-972daf9c3ab6`
on September 27, 2026: “Let's roll it out as you planned.” Decision recorded on
WOR-189 in comment `850ef671-5d0e-431b-801b-9fcfa7e73172`.
This branch extends the existing publisher with explicit maintained repository
inputs. It does not replace the source selector, map, transport or scheduler.

## Known

- Base: `bb7413a4c60cf7d15febd9a06d95e456e87a578f` (merged PR #17).
- Existing batch publication already freezes immutable Git bundle inputs,
  checks revision-bound writes, records pending intent and verifies readback.
- Installed 02:00 launchd job invokes legacy `notebooklm-sync --all --apply
  --changed-only`; the new publication path is not activated there.
- Separate primer-mirror launchd job invokes rclone to a different account.
- Live read-only Cloud inspection found Codify3030 external OAuth still Testing;
  Publish app disabled pending Branding configuration. The project has seven
  clients. A change there is shared, not a C021-only setting.
- C014's two pilot documents are inspectable candidates. C021's three publisher
  documents are candidates after stale pilot-status text is corrected here.
  C001 candidates have contradictory architecture descriptions and a client-related
  reference; their upload remains held.

## Assumed

Approved local repository/configuration owners control Git configuration and
source publication policy. This implementation pins the literal/effective origin
and manifest bytes; it is not a sandbox against a malicious local owner.
The example configuration is intentionally incomplete and confers no authority.

## Needs verification before activation

Exact cohort sources and destinations, long-term unattended credential acceptance,
installed interpreter/environment and a single-writer cutover must be accepted.
Observed Google Docs publication and NotebookLM ingestion/citation checks are
separate. No new account consent, uploads, source enrollment, artifact generation,
Cloud setting change or job mutation is performed by this branch.

## Risks and controls

Moving branches are resolved once after explicit successful fetches. Every source
is validated before publication; all configured map/Doc bindings are preflighted
before provider access. Failed fetch or changed manifest hash refuses execution.
Publication can still partially succeed if a later live check fails; existing
receipts and pending reconciliation preserve that distinction. Recovery uses
original immutable inputs, never a newly resolved branch. Existing map locking
remains authoritative; no second state registry is added.

## Evidence and files

Implementation: `publication_cohort.py` and `publication_cli.py`. Synthetic
regressions: `test_publication_cohort.py` and `test_publication_cli.py`.
Operator documentation: `PUBLISHER.md`, `PUBLICATION_STATE.md` and the explicit
cohort example. Validation and independent review results are recorded on the PR;
this receipt alone supplies no review or runtime clearance.

Local validation: 678 passed, one existing case-sensitive-filesystem skip on
Python 3.13.11; wheel and sdist built offline. Offline candidate run selected
exactly C014's two and C021's three files; the C014 bundle hash matched the
prior pilot. No map binding was created and no remote content was inspected by
that offline run. Full independent review remains a PR record.
