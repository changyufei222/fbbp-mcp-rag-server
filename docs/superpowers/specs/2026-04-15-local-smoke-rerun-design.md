# Local Smoke Rerun Design

## Goal

Provide a repeatable one-command local smoke workflow for `fbtp-mcp-rag-server` that prefers Windows PostgreSQL first, automatically falls back to WSL PostgreSQL when Windows startup is blocked, launches the MCP HTTP server, runs the smoke checks, and then tears everything down.

## Constraints

- The current workspace path contains non-ASCII characters, which can break Windows `initdb` when PostgreSQL binaries live under the workspace path.
- The current Windows session can be elevated, and Windows `postgres.exe` refuses to run under administrative permissions.
- WSL PostgreSQL 16 and `pgvector` are already available and were proven to work when started with `-k /tmp`.
- The existing `start_http_server.ps1` script is broken because it uses a `Host` parameter name that collides with PowerShell's built-in `$Host`.

## Chosen Approach

Use a thin PowerShell orchestration layer:

1. Keep `start_http_server.ps1` as the leaf HTTP launcher, but rename the host parameter and preserve its current job as the direct MCP starter.
2. Improve `start_fresh_postgres_foreground.ps1` so it supports explicit PostgreSQL binary overrides and produces clear preflight failures for the two known Windows blockers:
   - non-ASCII binary root
   - elevated Windows session
3. Add a single orchestration script that:
   - plans the provider order as `windows -> wsl`
   - tries Windows PostgreSQL only when preflight says it is viable
   - records the reason for Windows skip/failure
   - falls back to WSL PostgreSQL automatically
   - starts MCP HTTP
   - runs the existing smoke checks plus an HTTP `/mcp` probe
   - always cleans up the temporary PostgreSQL/MCP processes

## Why This Approach

- It fixes the two broken leaf scripts instead of bypassing them forever.
- It keeps the successful WSL fallback path that was already validated end-to-end.
- It gives us one stable operator command without requiring large refactors or new dependencies.
- It stays aligned with the repo's existing PowerShell-first local workflow.

## Testing Strategy

- Add regression tests that assert:
  - `start_http_server.ps1` exposes `ListenHost` instead of `Host`
  - `start_fresh_postgres_foreground.ps1` supports an explicit PostgreSQL binary root override
  - the new one-command runner supports a `PlanOnly` mode that reports provider order as `windows` then `wsl`
- Re-run the existing unit suite.
- Run one fresh real smoke flow end-to-end and confirm:
  - PostgreSQL becomes reachable
  - `/mcp` returns a live HTTP response
  - smoke ingest/search/chunk checks succeed
  - no temporary listeners remain after teardown
