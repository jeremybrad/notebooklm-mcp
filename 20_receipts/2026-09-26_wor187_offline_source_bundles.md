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
Initial GREEN: 12 tests passed. Expanded provenance/privacy/CLI coverage: 19
tests. After integrating PR #8, the full suite passed 287 tests with one
filesystem-dependent skip on Python 3.11.14 and 3.13.11. Python 3.13 coverage:
36% whole package, 93% new bundle module. Wheel and sdist builds passed.

Local acceptance used Git 2.54.0 and a schema-valid tightening of the packaged
manifest, excluding receipt/generated-primer trees and bounding C010 to root
technical docs. C021 at `429581da0afa1fe2f372d97366079f2a54a10055` selected 13
sources; bundle SHA-256
`36aa55978e1ac374f0e0dc151fd3e0056b2975590502aac91fb1dbf98d1fbd59`.
C010 at `1f6c2e0e1ec9b5e4231bc99ec56e4fddef471965` selected README, CHANGELOG,
META and RELATIONS; bundle SHA-256
`d5d34b60559b994150ddb71032433afb2c6e1713a2e66d04b88689416d2f9ba2`.
Two actual batch CLI runs returned byte-identical artifacts and summaries.
Synthetic committed-source changes changed the hash; unrelated commits did not.
Local artifacts and exact manifests are in the initiating task's
`outputs/wor187/` (outside Git). No private primer, journal or runtime payload
was read. Hosted CI remains `disabled_inactivity`; local checks are not claimed
as hosted CI passes. Live branch protection reports no required status checks.

No canonical checkout pull, source upload, auth change, live canary, scheduler,
runtime or model-backed publication operation occurred. PR #8 merged as
`429581da0afa1fe2f372d97366079f2a54a10055`; its tree was verified identical to
reviewed head `bbd6206f169e842eef61015f4f83c2ed6155bbdf` and integrated into this
branch before independent review. Its existing history remains separate.
GitHub acquisition is explicit caller prework; this CLI consumes already-local
GitHub refs/objects and never fetches. Rollback is to stop invoking the new CLI;
existing refresh entrypoints are unchanged and no runtime was installed.

Independent review R1 covered all seven changed paths and proposed BUNDLE-F1
(original P2): `--output repo.parent` passed the initial root check but derived
artifacts inside the source root. A real synthetic CLI regression reproduced
RED (exit 0 and generated files under the fixture repo). The repair checks every
derived destination against every input repository before any batch write. The
new regression requires failure and unchanged Git status; existing inside-root
and symlink refusals remain. Full history and re-review are retained on PR #9.
Repair validation: 288 passed / one filesystem-dependent skip on Python
3.11.14 and 3.13.11; 36% package / 94% bundle-module coverage; wheel/sdist
builds and diff checks pass. The repaired implementation has 20 new tests.
