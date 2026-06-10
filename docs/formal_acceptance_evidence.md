# Formal Acceptance Evidence

Frozen on `2026-04-18`.

This document is the official acceptance package for `fbtp-mcp-rag-server`.

The real production data identity for this package is `FBBP`.

## Contract

- Contract document: `docs/formal_tool_contract.md`
- Contract version: `1.1`
- Tool count: `14`

## Formal Acceptance

- Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_formal_acceptance.ps1
```

- Output log: `docs/formal_acceptance_output.json`
- Frozen result: acceptance suite passed
- Covered checks:
  - `health_status` exposes formal handshake fields
  - `get_document_chunk` provenance is sufficient for formal evidence collection
  - real smoke output already contains `contract_version`, `db_identity`, `build_id`, and `source_registry_version`

## Stable Fresh-Stack Smoke

- Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_smoke_once.ps1
```

- Output log: `docs/local_smoke_output.json`
- Frozen smoke behavior:
  - reuses the prepared full formal FBBP database by default
  - self-heals stale Windows `127.0.0.1:5432` `portproxy` state before starting WSL PostgreSQL
  - waits for a real SQL query on `localhost:5432` instead of treating a listening port as ready
  - emits one structured JSON payload containing `ensure_pg` and `smoke`
  - runs real `server_status`, `health_status`, `list_sources`, `get_source_summary`, and `search_knowledge`
  - returns `health_status.ok = true`
  - returns `search_knowledge.ok = true`
  - returns `formal_checks.result_count = 5` on the frozen stable query
  - returns `source_registry_count = 34` and formal runtime identity `fbbp_private_v2026_04 / local_formal / fbbp_formal_pgvector`
  - can resolve the top chunk through `-ResolveTopChunk`

## Explicit Rebuild

Only run a full rebuild when you intentionally want to recreate the formal retrieval table:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\rebuild_fbbp_formal_db.ps1
```

This command resets the active retrieval table and re-ingests only the explicit `source_allowlist` registered in `configs/datasets/fbbp_private_v2026_04.json`.

## Codex and DeerFlow Client Proof

- Codex config block: `examples/clients/codex.config.toml`
- DeerFlow extension config: `examples/extensions_config.deerflow.json`

The current Codex local endpoint is:

```toml
[mcp_servers.fbtp-rag]
url = "http://127.0.0.1:8000/mcp"
```

## Why This Package Is the Official One

- It links the formal contract, the acceptance tests, the stable smoke command, and the client configuration in one place.
- It avoids relying on ad hoc console history or temporary notes.
- It keeps smoke on the real FBBP runtime identity while separating expensive rebuild into an explicit maintenance command.
