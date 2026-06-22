# Receipt: Claudit Audit + Fork Push Guardrails

- **Date**: 2026-06-21
- **Machine**: Mac-mini-2
- **Agent**: Atlas (Claude Code)
- **Branch**: main (work landed on PR branch + global config)

## What was accomplished

1. **Claudit comprehensive audit** (score 90 → 93, Grade A). Project-scoped fixes
   landed on **PR #2** (`claudit/improvements-2026-06-21-2110`, OPEN, awaiting review):
   - New committed `.claude/settings.json` (shared contract: non-destructive MCP tool
     allow list + project Bash execs + `enabledMcpjsonServers`).
   - `.gitignore`: `.claude/*` + `!.claude/settings.json` (track shared, ignore local).
   - `.mcp.json`: `alwaysLoad: true` + `timeout: 60`.
   - `CLAUDE.md`: removed drift-prone "31 tools" counts.
   - Local-only (gitignored): `settings.local.json` colon-pattern fix + safe/destructive
     scope split; `claudit-decisions.json` updated.

2. **Fork push guardrails** (root-cause fix for repeated mis-targeted PRs to upstream):
   - `gh repo set-default jeremybrad/notebooklm-mcp` (`.git/config`, active now).
   - Global PreToolUse(Bash) hook `~/.claude/hooks/fork_push_guard.py` — hard-blocks
     gh/git writes to a fork's upstream owner. Tested 6 block / 8 pass. **Activates on
     Claude Code restart** (settings.json cached at startup).
   - Project memory `fork-never-touch-upstream.md` written.

## Incident (handled)

A `gh pr create` without `--repo` opened PR on upstream `jacob-bd/notebooklm-mcp-cli#242`
by mistake (fork-default resolution). Caught immediately, **closed with apology**,
recreated correctly as jeremybrad/notebooklm-mcp#2. Guardrails above prevent recurrence.

## Key files changed

- This repo (PR #2): `.claude/settings.json`, `.gitignore`, `.mcp.json`, `CLAUDE.md`
- Global: `~/.claude/hooks/fork_push_guard.py`, `~/.claude/settings.json` (hook wiring)
- Memory: `~/.claude/projects/.../memory/{fork-never-touch-upstream,MEMORY}.md`

## TODOs / next steps

- [ ] **Restart Claude Code** to activate `fork_push_guard.py`.
- [ ] Review + merge **PR #2** (jeremybrad/notebooklm-mcp#2).
- [ ] Deferred: decompose global `~/.claude/CLAUDE.md` upstream in C010 builder
      (Context Efficiency lever; auto-generated file — do not hand-edit deployed copy).
