# WOR-189 — approved C021 information-site implementation

Jeremy approved the concrete GitHub Pages plan in task
`01a0d946-629f-7580-9cdb-972daf9c3ab6`: two static pages in the existing public
repository, manual deployment, required review, and publication after Jeremy
merges the reviewed PR. Owning decision: WOR-189 comment
`3d6c6413-b690-48f4-86c4-c7256f0dd954`. He separately confirmed the six older
Codify3030 clients are retired experiments and that the description should focus
on C021; none is removed or modified.

This branch adds `site/index.html`, `site/privacy.html` and a manual Pages
workflow. The site explains the scoped publisher/NotebookLM workflow and its
Google data use, local storage, retention and owner controls. It discloses
GitHub Pages visitor-IP logging. It contains no credentials, private destination
IDs, analytics, forms or external scripts. Existing runtime code is unchanged.

Only workflow_dispatch on main can deploy. A required full SHA must match the
run's main commit before checkout. Actions are pinned to commit IDs resolved
from official action release tags. Checkout does not persist credentials.
The package job has contents/read and pages/read; the dependent deployment job
has pages/write and id-token/write. Configuration enablement is disabled inside
the workflow. Packaging accepts only two regular non-symlink source files and
copies them into a fresh staging directory; upload never targets the checkout.
No Google secret or model provider is used. Deployment is serialized.

This source change does not enable Pages, run a workflow, publish a site, change
OAuth Branding/audience, renew credentials, or activate a nightly job. Betty owns
the separately approved postmerge Pages setup/dispatch and HTTPS/artifact checks.
Jeremy remains sole merger. Google acceptance/domain verification is unproven;
stop rather than invent a verified domain or automatically change hosts if it
fails. Shared OAuth publishing/access-duration changes still need the required
confirmation at the action. Native production-grant/locked-denied/full-publisher
acceptance and the recurring rollout remain open.

Validation and independent exact-head review are recorded in the PR's triage
and Current status, not asserted from this implementation receipt alone.
