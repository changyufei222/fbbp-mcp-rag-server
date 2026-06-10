# Final Result Summary

Frozen on `2026-04-18`.

This file is the official portfolio summary for `FBBP MCP RAG Server` (repo path: `fbbp-mcp-rag-server`). Use it instead of mixing contract docs, smoke transcripts, and temporary notes.

## Positioning

`FBBP MCP RAG Server` is a formal MCP server that exposes FBBP private-knowledge retrieval plus public scientific lookup tools through a contract-stable interface for agent clients such as Codex and DeerFlow.

## Official Status

- Status: formal acceptance package frozen for the real local FBBP runtime, with the downstream DeerFlow full-data atlas package now wired to the same FBBP contract
- Frozen acceptance bundle: `docs/formal_acceptance_evidence.md`
- Client connection proof: `examples/clients/codex.config.toml` and `examples/extensions_config.deerflow.json`
- Downstream official results package: `../fbbp-research-workbench/final_results/fbbp_formal_atlas_v2026_04/atlas_overview.md`

## Resume Evidence Chain

### One-line Positioning

Formal MCP gateway for private FBBP retrieval and scientific lookup tools.

### Reproduction Command

`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_formal_acceptance.ps1`

### Formal Report

`../fbbp-research-workbench/final_results/fbbp_formal_atlas_v2026_04/atlas_overview.md`

### Key Number

`34` registered formal FBBP sources exposed to downstream formal consumers.

### Screenshot

`../fbbp-research-workbench/artifacts/20260418_155831_fbbp_formal_console_v2/screenshots/gateway_docs.png`

### Resume Bullet

Built a contract-stable MCP server for the real FBBP data line with private retrieval, structured provenance-rich outputs, source-registry-backed evidence metadata, and public lookup tools; it now feeds the official downstream full-data atlas package used for GitHub, demo, and paper-facing presentation.

## Canonical Artifacts

- `docs/formal_acceptance_evidence.md`
- `docs/formal_acceptance_output.json`
- `docs/formal_tool_contract.md`
- `../fbbp-research-workbench/final_results/fbbp_formal_atlas_v2026_04/atlas_overview.md`
- `../fbbp-research-workbench/final_results/fbbp_formal_atlas_v2026_04/source_registry_snapshot.json`

## Notes

- The MCP repo remains the formal service and contract layer; the canonical research-facing output now lives downstream in the DeerFlow atlas package.
- The localhost `5432` path is still self-healed for local operations by removing stale Windows `portproxy` state and validating real SQL readiness before formal acceptance.
- The current formal line exposes `34` source-registry entries and feeds the deterministic downstream atlas package for the same `fbbp_private_v2026_04` dataset version.
- Full rebuild is now separated into `scripts/rebuild_fbbp_formal_db.ps1`, which resets the retrieval table and re-ingests only the repo-local formal snapshot allowlist under `formal_snapshots/fbbp_private_v2026_04/`.
- Snapshot refresh is separated into `scripts/sync_formal_snapshot.ps1`, which copies the canonical JSONL exports from `llm-rag-knowledge-base` into the checked-in MCP snapshot tree and writes `MANIFEST.json`.

