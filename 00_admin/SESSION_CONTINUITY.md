# Session Continuity -- C021_notebooklm-mcp

<!-- Overwritten by /close-session. Do not edit manually. -->

## Last Session

- **Date**: 2026-06-21
- **Machine**: Mac-mini-2
- **Agent**: Atlas (Claude Code)
- **Branch**: main
- **Receipt**: 20_receipts/2026-06-21_claudit_audit_and_fork_guardrails.md
- **Commit**: 4b23c5d

## Summary

Ran a claudit comprehensive config audit (90 → 93, Grade A); project-scoped fixes landed
on PR #2 (shared `.claude/settings.json`, `.gitignore` negation, `.mcp.json` alwaysLoad/
timeout, CLAUDE.md tool-count trim). Then installed fork push guardrails after a
`gh pr create` mistakenly opened a PR on the upstream `jacob-bd` repo (closed; recreated
correctly as #2): `gh repo set-default` + a global PreToolUse hook `fork_push_guard.py`
that hard-blocks gh/git writes to a fork's upstream owner.

## Open Threads

- [ ] Review + merge **PR #2** (jeremybrad/notebooklm-mcp#2) — the claudit audit fixes.
- [ ] **Restart Claude Code** to activate the `fork_push_guard.py` hook (settings.json is
      cached at startup; `gh repo set-default` already protects in the meantime).
- [ ] Deferred: decompose the global `~/.claude/CLAUDE.md` upstream in the C010 builder
      (Context Efficiency lever; the deployed file is auto-generated — do not hand-edit).

## Known Hazards

- **This repo is a FORK.** `origin` = jeremybrad/notebooklm-mcp (only write target);
  `upstream` = jacob-bd/notebooklm-mcp (never push/PR to it). Always pass
  `--repo jeremybrad/notebooklm-mcp` on `gh` write commands. Guardrails enforce this once
  the hook is active.
- Auth is cookie-based and expires; on 401/403 run `notebooklm-mcp-auth` then restart.
