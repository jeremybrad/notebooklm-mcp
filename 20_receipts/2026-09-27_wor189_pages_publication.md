# WOR-189 — approved C021 public pages published

Jeremy approved the GitHub Pages plan, including publication after his reviewed
merge, in Codex task `01a0d946-629f-7580-9cdb-972daf9c3ab6`; owning decision
WOR-189 comment `3d6c6413-b690-48f4-86c4-c7256f0dd954`. He then reported PR21
merged and instructed continuation. Fresh fetch and GitHub verified merge
`c50fc2ab84638fd62016a4250306c618012e4642` at 2026-09-27T23:48:00Z, with the
complete tree equal to reviewed `4fcf6d714dedcd050d00b227f7c210ca89c2ca51`.
PR21 Current status was reconciled to MERGED.

The Pages endpoint initially returned 404. The approved create call set
`build_type=workflow`; returned hostname was the intended default, no custom
domain, public=true and HTTPS enforced. The new Pages workflow was already
active. Existing CI stayed disabled_inactivity; other workflows were untouched.
Exactly one manual dispatch named the merged SHA above:

https://github.com/jeremybrad/notebooklm-mcp/actions/runs/36359968466

Both package and deploy succeeded. The downloaded github-pages artifact archive
contained exactly two regular files, index.html and privacy.html. Both contents
matched the merged tree byte-for-byte. Live HTTPS requests returned 200 without
redirect, with exactly the same bytes:

- https://jeremybrad.github.io/notebooklm-mcp/ — 2042 bytes;
  SHA-256 `e99a7ec88bd48b8e8d2efd3e5fa706b29425cae40b8f31ea7c8bb6d67b45ad19`.
- https://jeremybrad.github.io/notebooklm-mcp/privacy.html — 3503 bytes;
  SHA-256 `1cc321f3fe6cae84acd38b52850e3f9f31bdb372fe473714ae0c8881837d5ed3`.

Browser inspection showed the published homepage, and its Privacy link opened
the expected complete notice. No repository docs, receipts, runtime configuration
or credentials were in the Pages artifact. Operational evidence is retained at
`~/LocalWork/Codex/c021-public-pages/deployment/`: creation/final configuration,
workflow state, run status, downloaded artifact, byte-verification results and
homepage screenshot. This is actual publication evidence; Pages API status was
null, so success is grounded in the run and live content checks instead.

No Google Branding/audience/client/credential changes, canonical runtime pull,
new source upload or nightly activation occurred in this deployment. Google
acceptance of the hostname remains unverified. Durable grant and native
production-item/locked-denied/full-publisher acceptance, recurring cutover and
first scheduled receipt remain open. Website rollback is disabling the new Pages
site; it must not change the Google grant, Docs, notebooks or legacy job.
