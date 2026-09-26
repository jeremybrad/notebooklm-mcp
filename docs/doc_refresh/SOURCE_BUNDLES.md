# Offline repository documentation bundles

`repo-doc-bundle` prepares local Markdown and JSON receipts from the accepted
`canonical_docs.yaml` selection rules. It does not publish to Drive or NotebookLM,
read authentication, run models, modify notebook mappings, or activate scheduling.
Stable native Google Docs remain the separately authorized eventual transport.

## One repository or a batch

```sh
repo-doc-bundle --repo /path/to/C021_notebooklm-mcp origin/main --output /path/to/artifacts
repo-doc-bundle \
  --repo /path/to/C021_notebooklm-mcp FULL_COMMIT_SHA \
  --repo /path/to/C010_standards FULL_COMMIT_SHA \
  --output /path/to/artifacts
```

Each repeated `--repo` takes a local Git root and a revision. A GitHub revision
must already be fetched into that repository; this command does no network
acquisition or freshness check. Use an operator-approved revision. An existing
remote-tracking ref such as `origin/main` is resolved once to its full commit ID.
Receipt provenance records that ID, even if the ref moves during generation.
The directory basename must retain its canonical repo identity for overrides;
root symlinks, spelling aliases and subdirectories are refused. Batch basenames
must be unique. W001–W099 roots are refused under the workspace quarantine.

Dirty and untracked worktree content is **not an input**. The command constructs
an owned, temporary inventory of the pinned Git tree using empty file markers,
then calls the existing `discover_repo`. Only selected regular blobs are read.
Git symlinks/submodules are omitted with an unsupported-mode reason; excluded
and unselected blob contents are never read. Filesystem identity collisions fail
closed. Git replacement objects are disabled; fetched object IDs and independently
verified blob hashes bind provenance to the captured bytes. This is an immutable
snapshot, not a claim that a mutable checkout is clean.

A Git executable supporting `--no-lazy-fetch` is required. Older Git versions
fail before any object read; missing objects in partial clones cannot trigger
an implicit network fetch. Acceptance here used Git 2.54.0.

The packaged manifest is the default; `--manifest /path/to/canonical_docs.yaml`
accepts the same validated schema and exclusion precedence. No alternate registry
or selector is introduced. A valid manifest is not itself permission to export
private material: select only approved technical repository documentation. The
CLI cannot recognize all sensitive prose. Never target private primers, personal
journals, client data, runtime records or quarantined repositories.

## Content and receipts

The existing `render_bundle` creates stable repo/path headings, sorts sources,
normalizes line endings and final newlines, and preserves Markdown titles and
front matter as source text. It does not rewrite their meaning or invoke a model.
Its source revision is the full **Git blob ID**, not a best-effort file commit.
The renderer adds normalized-text SHA-256; the receipt additionally records each
path's raw-byte SHA-256, byte count and blob ID. Unsupported UTF-8/control text,
missing required documentation, and empty source sets fail before artifact writes.

Output is content-addressed:

```text
OUTPUT/REPO/BUNDLE_SHA256/bundle.md
OUTPUT/REPO/BUNDLE_SHA256/RECEIPT_SHA256.json
```

Receipts include the full capture commit, manifest version and captured manifest
hash prefix, selected source count and path records, omitted tracked paths with
reasons, missing optional paths, and `sha256:...` as the **local** artifact ID.
`drive_document_id` and `notebook_id` are null. No timestamp or absolute source
path enters the bundle. Identical reruns return identical files. A source change
changes the bundle; a code-only commit changes the receipt's capture commit but
leaves the bundle unchanged. A hash is not a publication or ingestion receipt.

Output must be outside source repositories. Identical existing artifacts are
reused; conflicting files and symlink output paths are refused. The entire batch
is built before any artifact write, so selection/content failure emits nothing.
Filesystem errors during writing may leave earlier complete or partial files;
the command exits nonzero and a conflicting rerun fails instead of claiming
success. Keep incomplete output for inspection or choose another output directory.
Exit 0 means local artifacts only; exit 1 means generation/write failure; argparse
usage errors exit 2. JSON stdout names completed artifact paths on success.

Generated primers stay owned by C010. An untracked `PROJECT_PRIMER.md` is absent
from a Git snapshot; this command does not regenerate or silently import it.
Live same-ID Docs updates, NotebookLM refresh/citation checks and the old nightly
writer/mirror cutover remain separate WOR-188/WOR-189 work.
