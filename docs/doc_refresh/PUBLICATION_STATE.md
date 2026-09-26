# Offline publication state and recovery

WOR-188 implements the approved next step after the synthetic live canary
([PR #10](https://github.com/jeremybrad/notebooklm-mcp/pull/10)). The new module
`doc_refresh/publication_state.py` is an opt-in library. It has **no default
state path, CLI, HTTP transport, OAuth, installed-runner or scheduler wiring**.
Tests use explicit temporary maps and fictional Docs. Existing jobs still use
their old code path and are not changed by this module.

The later [explicit publisher](PUBLISHER.md) supplies a separate HTTP adapter,
batch layer and command interface around this library. Its production credential
provider is unconfigured and no installed job is connected.

## Existing map, versioned extension

The intended eventual location remains the existing
`~/.config/notebooklm-mcp/notebook_map.yaml`. No second registry or lock file is
introduced. This implementation never opens that default implicitly. A caller
supplies a `MapStore(Path(...))`; writes require an already existing parent.
Reading an absent map returns an in-memory empty notebooks mapping only.

Each managed entry under `notebooks[repo]` retains its existing `notebook_id`
and legacy `docs`/other fields. It adds `drive_publication`:

```yaml
version: 1
document_id: explicitly-adopted-doc
tab_id: t1
verified:
  sha256: <full text SHA-256, including final newline>
  revision_id: <revision returned with the verified text>
pending: null
notebook: null
artifacts: {}
```

A pending operation contains an operation ID, base hash/revision, and target
hash. It stores no copy of source text. Notebook and artifact observations
contain the exact bundle hash, stable source ID, and a nonempty reference to
the caller's verification evidence. They are **caller attestations**, not
automated source or image inspections. A source attestation must precede an
artifact attestation. An existing source association cannot be silently
replaced; an artifact observation cannot be overwritten.

The whole map must be JSON-compatible YAML with string keys and a notebooks
mapping. Unknown compatible legacy fields are preserved. The versioned
extension has exact keys, validated IDs/hashes and pending-base consistency.
Unsupported versions/shapes, duplicate keys, aliases, nonfinite values, YAML
objects, non-string keys, multiple repo bindings to the same Doc, oversized
maps, symlink maps and nonregular map files are refused. YAML implicit dates
must be quoted strings; this library never silently rewrites incompatible
legacy data. Maximum serialized/read size is 4 MiB; nesting is bounded.

## Lifecycle

Use `build_bundle(repo, pinned_revision).bundle` from the accepted manifest/Git
selector as the publication input. `Bundle` itself is a trusted caller value,
not proof of source-selection authority. No alternate automatic gatherer is
introduced. Never provide real repository text until its upload is authorized.

1. `bind_empty` explicitly adopts a caller-supplied, complete native Docs
   response only when the text is exactly the blank final newline. The old
   notebook ID must agree; a binding cannot be replaced. This creates no cloud
   object. Nonempty Doc adoption remains an explicit future reconciliation
   decision. An edit after this supplied snapshot is caught by publication's
   fresh remote read and hash guard.
2. `prepare` reads the local map and the caller's supplied complete Docs
   response, then uses the reviewed `plan_update`. It neither creates state nor
   calls a transport. A pending operation blocks ordinary planning/publication.
3. `publish` holds the map directory lock throughout the operation, including
   transport calls. It validates state, reads the managed Doc, checks identity
   and prior verified hash, and constructs the reviewed revision-bound plan.
4. Before a changed write, it durably records pending intent. The injected
   transport must enforce `requiredRevisionId`; the library never weakens or
   substitutes it. An uncertain write is never retried automatically.
5. It parses a complete native `SUGGESTIONS_INLINE` readback and compares exact
   expected text, destination identity and hash. Only then does it atomically
   save verified hash/revision and clear pending intent. Any transport,
   readback, replacement or fsync error propagates as failure. A no-op sends no
   write but still validates current content and records its verified revision.

The separate publisher's concrete transport supplies the complete native shape.
The canary connector's flattened tab wrapper is not accepted here; no adapter
may discard unsupported fields to make a response pass this parser.

## Recovery after interruption

`reconcile` requires the original target bundle and performs remote reads only.
It never replays a write. Exact target content promotes verified success; exact
base content **and the original revision** clear an unexecuted pending intent.
Any other remote edit/revision, identity mismatch, missing response or incorrect
target bundle preserves pending evidence and raises an error. Never simply
reset the stored hash to an observed manual edit.

A directory fsync can fail after replacement has become visible. The caller
still receives failure; the file may show the old pending state or the verified
target. Explicit reconciliation handles both, returning `verified_target` or
`already_verified` after fresh exact remote verification. This is not a claim
that a failed fsync survives power loss. A missing/corrupt state after a real
storage failure requires operator recovery; no automatic blank-state adoption.

## Concurrent writes and filesystem assumptions

The library uses POSIX `flock` on the **existing parent directory**, held across
atomic file replacement. No lock file, heartbeat or parallel state store is
created. Competing cooperating callers fail promptly with `StateConflict`;
they do not wait indefinitely or overwrite another completed operation. Fresh
snapshot comparisons also reject changed bytes observed before replacement.
Temporary sibling files are mode 0600, flushed/fsynced, atomically replaced,
then the directory is fsynced. Ordinary errors clean temporary files; a process
crash can leave an ignored temporary sibling, never read as durable state.

This is a local POSIX-filesystem implementation, tested on macOS. There is no
unlocked fallback on unsupported systems. The containing directory must be
trusted/stable; other entries in that directory share its cooperating lock.
No advisory lock or check-then-replace can make an **uncooperative** writer safe.
The old installed writer and any process bypassing this protocol must be
quiesced before real activation. The current legacy map save remains unchanged;
this module is not deployed concurrently with it. Filesystem locking/rename
semantics must be validated on the eventual host before activation.

## Freshness is per layer and explicit set

`freshness(store, {repo: expected_bundle_hash, ...})` evaluates the caller's
explicit nonempty publication set. `all_docs_verified` is true only when every
requested repo has that exact verified hash and no pending operation. Missing
repos and mixed-success batches remain partial. No generic “all current” flag
is returned: NotebookLM source and generated artifact attestations are separate.
Old observations remain bound to their old hashes when Docs advances. This
matches the live canary: new citations used B while the initial overview still
described A. Generation, current citations and unattended refresh are different
observations; no nightly guarantees follow from an interactive canary.

## Remaining operational decisions

Future activation still requires reviewed Google data OAuth provisioning and
live account/scopes/transport acceptance, a nonempty-adoption decision if needed,
real-source authorization, host/filesystem acceptance and existing writer/mirror
cutover. Credentials, installed jobs and the actual user map were not touched to
develop or test this module. Jeremy remains sole merger.
