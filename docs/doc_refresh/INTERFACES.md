# Doc Refresh Interfaces

**Version:** 1.0.0
**Last Updated:** 2026-09-12

## CLI Interface

### Command Syntax

```
/doc-refresh [--target PATH] [MODE] [OPTIONS]
```

### Safety Modes

| Flag | Default | Effect |
|------|---------|--------|
| `--dry-run` | ✅ Yes | Validate only, no writes |
| `--apply` | No | Execute changes |

### Operation Modes

| Flag | Phases Executed | Requires `--apply` |
|------|-----------------|-------------------|
| (none) | Discover + Validate | No |
| `--validate-only` | Discover + Validate | No |
| `--docs-only` | Discover + Validate + Update | Yes |
| `--sync-only` | Discover + Validate + NotebookLM Sync | Yes |
| `--full` | All 6 phases | Yes |

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--target` | PATH | cwd | Target repo path |
| `--force` | flag | false | Skip change threshold, always refresh |
| `--artifacts` | string | "all" | Comma-separated artifact IDs to refresh |
| `--skip-unchanged` | flag | true | Skip docs with matching hash |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (or dry-run complete) |
| 1 | Validation errors found |
| 2 | Sync failed |
| 3 | Artifact generation failed |

---

## Manifest Schema

### canonical_docs.yaml

Validated against `src/notebooklm_mcp/doc_refresh/canonical_docs.schema.json`
(JSON Schema draft 2020-12, schema id `c021.canonical_docs.v1`).
`load_manifest()` fails closed on malformed files.

Include/exclude precedence:

1. Candidate set = tier documents + `repo_overrides.<repo>.extra_docs`.
2. Drop any candidate that is not contained in the repo root (absolute path,
   parent escape, UNC/tilde, or symlink whose target leaves the repo).
3. Drop any candidate matching an exclusion glob (global list, then per-repo
   extra exclusions). Exclusions always win over includes/`extra_docs`.
   Existing literal components use filesystem directory-entry identity: alternate
   case/Unicode spellings of include paths are omitted, and existing literal
   exclusion prefixes resolve to their actual spelling. Wildcard matching remains
   case-sensitive. Identity lookup errors omit candidates; missing suffixes retain
   ordinary missing-required reporting.
4. Directory entries with `scan_pattern` expand to matching files, then the
   same containment and exclusion rules apply to each file.

```yaml
schema: "c021.canonical_docs.v1"
version: "1.0.0"
last_updated: "YYYY-MM-DD"

tier3_candidates:          # Paths to check for Tier 3 docs
  - "docs/{repo_name}/"    # Template with repo name
  - "docs/"                # Fallback

exclusions:
  - pattern: ".env*"       # Glob; also matches basename at any depth
    reason: "environment files"

tiers:
  tier1:                   # Required tier
    name: string
    description: string
    required: true
    documents:
      - path: string       # Relative path from repo root
        purpose: string
        must_exist: bool
        stub_allowed: bool
        validation: [rule_ids]

  tier2:                   # Extended tier
    # Same structure, required: false
    # Includes CLAUDE.md, AGENTS.md, PROJECT_PRIMER.md, glossary, 10_docs/, 20_receipts/

  tier3:                   # Kitted tier
    path_prefix: "{tier3_root}"  # Resolved from candidates
    documents:
      - path: string       # Relative to path_prefix
        alternate_names: [string]  # Optional variants
        # ... same fields

validation_rules:
  rule_id:
    description: string
    check: string          # Human-readable check description

artifacts:
  - id: string             # e.g., "mind_map"
    name: string
    tool: string           # NotebookLM MCP tool name
    tool_params: {}        # Tool-specific params
    default_trigger: string

change_detection:
  content_delta_threshold: float  # e.g., 0.15 for 15%
  triggers: [string]

repo_overrides:
  RepoName:
    tier3_root: string     # Override path resolution
    extra_docs: []         # Additional docs to include (still subject to exclusions)
    exclusions: []         # Extra privacy globs for this repo
```

Discovered `DocItem` freshness metadata (same 12-char SHA-256 prefix as
notebook-map hashes; no second hash scheme):

| Field | Source |
|-------|--------|
| `path` | Repo-relative path |
| `content_hash` | SHA-256 prefix of file bytes |
| `source_title` | `DOC: {repo} :: {path}` |
| `last_commit` | `git log -1` SHA when `.git` exists; otherwise null |
| `generated_bundle_id` | Reserved for the bundle generator; null here |


### notebook_map.yaml

```yaml
# Version header
workspace_root: string     # Base path for repos

notebooks:
  RepoName:
    notebook_id: string | null
    notebook_url: string | null
    last_sync: date | null
    tier: "simple" | "complex" | "kitted" | null
    doc_hashes:
      "path/to/doc.md": string  # 12-char SHA256 prefix
    artifacts:
      artifact_id: string | null  # NotebookLM artifact UUID

sync_log: []               # Last 10 sync entries

config:
  auto_create_notebook: bool
  notebook_title_template: string
  hash_algorithm: string
  hash_length: int
```

---

## Document Tiers

### Tier 1: Required (every repo)

| Document | Must Exist | Purpose |
|----------|------------|---------|
| `README.md` | Yes | Entry point |
| `CHANGELOG.md` | Yes | Change history |
| `META.yaml` | Yes | Project metadata |

### Tier 2: Extended (complex repos)

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | Claude Code guidance |
| `AGENTS.md` | Agent instruction routing |
| `PROJECT_PRIMER.md` | Repo primer |
| `glossary.yaml` | Domain terms |
| `10_docs/` | Working agreements / PRDs / governance |
| `20_receipts/` | Change receipts |

### Tier 3: Kitted (NotebookLM-ready)

| Document | Alternates | Purpose |
|----------|------------|---------|
| `OVERVIEW.md` | - | System overview |
| `QUICKSTART.md` | - | Install/run guide |
| `ARCHITECTURE.md` | - | Component diagram |
| `CODE_TOUR.md` | - | File map |
| `OPERATIONS.md` | - | Run modes |
| `SECURITY.md` | `SECURITY_AND_PRIVACY.md` | Security notes |
| `OPEN_QUESTIONS.md` | - | Unresolved decisions |

---

## NotebookLM Artifacts (Standard 7)

| ID | Tool | Default Trigger |
|----|------|-----------------|
| `mind_map` | `mind_map_create` | Any doc change |
| `briefing_doc` | `report_create(Briefing Doc)` | Any doc change |
| `study_guide` | `report_create(Study Guide)` | Content restructure |
| `audio_overview` | `audio_overview_create(deep_dive)` | Major changes |
| `infographic` | `infographic_create(landscape)` | Architecture changes |
| `flashcards` | `flashcards_create(medium)` | Content additions |
| `quiz` | `quiz_create(5, 2)` | Content additions |

---

## Change Detection

### Hash Computation

```
hash = sha256(file_content)[:12]
```

### Refresh Triggers

Artifacts are regenerated when ANY of:
1. `content_delta > 0.15` (15% of docs changed)
2. `META.yaml` major version bumped
3. `--force` flag provided

### Delta Calculation

```
changed_docs = docs where hash != stored_hash
delta = len(changed_docs) / len(all_docs)
```

---

## Validation Rules

| Rule ID | Check |
|---------|-------|
| `has_metadata_header` | YAML frontmatter OR `Version:`/`Last Updated:` header |
| `accurate_claims` | Manual verification flag |
| `code_refs_valid` | `file:line` patterns resolve to existing files |
| `working_links` | `[text](path)` links resolve |
| `valid_yaml` | Parses as YAML |
| `has_version` | Contains `version` key |
