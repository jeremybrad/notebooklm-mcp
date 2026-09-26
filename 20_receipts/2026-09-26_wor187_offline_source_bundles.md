# WOR-187 offline source-bundle integration

Authorized successor implementation of the approved stable-Docs direction.
Betty exclusively owns `codex/wor187-offline-bundles` in the app's isolated f8ea
worktree. Initial base: `6317b5db57f82a9df0e1302cacb05fb80ccb2011`.

The accepted manifest, schema, selector and renderer are reused. The new input
boundary resolves a Git commit once, builds a temporary path-only inventory with
the original root basename, reads selected regular blobs only, verifies each
blob object ID against captured bytes, and renders immutable blob provenance.
No volatile timestamp or whole-repo commit is embedded in bundle text. Receipts
retain the capture commit and raw-byte hashes. Local IDs never stand in for Drive
or NotebookLM publication IDs. Dirty/untracked source bytes are not consumed.

Files: `doc_refresh/source_bundle.py`, its synthetic tests, `pyproject.toml` CLI
entry, `docs/CLI.md`, `docs/doc_refresh/SOURCE_BUNDLES.md`, and changelog.
Synthetic RED: new integration tests failed to import the absent implementation.
Initial GREEN: 12 tests passed; expanded regression and acceptance evidence is
recorded on the PR at its exact head before readiness.

No canonical checkout pull, source upload, auth change, live canary, scheduler,
runtime or model-backed publication operation occurred. PR #8 remains a separate
input-contract prerequisite; its code/history is not duplicated by this change.
GitHub acquisition is explicit caller prework; this CLI consumes already-local
GitHub refs/objects and never fetches. Rollback is to stop invoking the new CLI;
existing refresh entrypoints are unchanged and no runtime was installed.
