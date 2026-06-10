# FBBP MCP Client Acceptance Matrix

This document is the human-readable acceptance layer for `fbbp-mcp-rag-server` across the four main client surfaces we care about: Codex, Claude Code, Cursor, and DeerFlow.

## Scope

- The goal here is not to pretend that every GUI runtime is always live on this machine.
- The goal is to prove that each client has a canonical config, transport choice, smoke path, and expected success signal.
- The generated machine-readable mirror lives under `reports/final_release/latest/client_acceptance_matrix.json`.
- The current checked-in matrix mixes `http` client configs with a DeerFlow `stdio` config, while deployment-side `streamable-http` remains the preferred browser-visible service mode.

## Matrix

| Client | Canonical config | Transport | Smoke path | Expected success signal |
|---|---|---|---|---|
| Codex | `examples/clients/codex.config.toml` | `http` | load config, call `tool_contract_version` | tool list contains `search_knowledge`, `list_sources`, `search_pubmed` |
| Claude Code | `examples/clients/claude-code.mcp.json` | `http` | register MCP file, call `server_status` | runtime details resolve without the legacy uppercase name |
| Cursor | `examples/clients/cursor.mcp.json` | `http` | import MCP JSON, run `health_status` | tool registration succeeds and health envelope uses contract `1.1` |
| DeerFlow | `examples/extensions_config.deerflow.json` | `stdio` | load extension config, run `search_knowledge` through DeerFlow | local extension resolves and FBBP naming stays consistent |

## Smoke Expectations

- Every client config should reference `fbbp-rag` or `fbbp-mcp-rag-server`, never the legacy uppercase project name.
- `stdio` clients should expose the same core tool list and the same response envelope.
- Codex / Claude Code / Cursor currently point at the HTTP MCP endpoint on `127.0.0.1:8000/mcp`.
- DeerFlow currently uses `stdio` with an explicit `server.py` launch plus env wiring in the extension config.
- Each smoke path should verify one lightweight tool first, then one retrieval tool.

## Recommended Smoke Order

1. `tool_contract_version`
2. `server_status`
3. `health_status`
4. `list_sources`
5. `search_knowledge`

## Boundary

- This matrix proves config readiness and smoke intent.
- Live GUI clicks are still environment-dependent and should be run separately when Codex, Claude Code, Cursor, or DeerFlow are attached to the local machine.
