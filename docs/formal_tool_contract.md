# Formal Tool Contract

## Purpose

`fbbp-mcp-rag-server` exposes a formal MCP contract for the real `FBBP` database so that DeerFlow and other agent clients can treat the server as a stable scientific knowledge connector rather than an ad hoc wrapper.

## Response Shape

All tools return the same top-level structure:

```json
{
  "ok": true,
  "tool": "search_knowledge",
  "contract_version": "1.1",
  "request": {},
  "result": {},
  "provenance": {},
  "diagnostics": {},
  "error": null
}
```

## Tool Groups

### Runtime and Contract
- `server_status`
- `health_status`
- `tool_contract_version`

### Private Knowledge
- `list_sources`
- `list_record_types`
- `get_source_summary`
- `get_document_chunk`
- `search_knowledge`
- `explain_search`
- `preview_ingest`
- `ingest_sources`

### Public Scientific Lookups
- `search_pubmed`
- `get_uniprot_entry`
- `get_pdb_entry`

## DeerFlow Usage Order

For domain research flows, the recommended source order is:

1. `search_knowledge`
2. `get_document_chunk`
3. `search_pubmed`
4. `get_uniprot_entry`
5. `get_pdb_entry`

## Diagnostics Expectations

Whenever possible, diagnostics should include:

- `latency_ms`
- worker action name for private knowledge calls
- cache-related hints for retrieval calls
- runtime and dependency health for `health_status`

For MCP `search_knowledge`, the formal single-path execution model should also expose:

- `query_transport`
- `gateway_url`
- `gateway_backend_transport`

## Formal Runtime Metadata

Formal operation expects the service to expose:

- `dataset_version`
- `runtime_profile`
- `formal_db_mode`
- `db_identity`
- `build_id`
- `source_registry_version`

These fields appear:

- in `health_status.result.runtime`
- in `server_status.result`
- in provenance for private-knowledge retrieval calls such as `search_knowledge` and `get_document_chunk`

## Formal Source Registry

`list_sources` and `get_source_summary` should expose source-registry metadata directly from the checked-in FBBP dataset descriptor rather than inferring meaning from filenames at report time.

Expected fields per registered source:

- `source_category`
- `source_description`
- `upstream_pipeline`
- `runtime_snapshot`
- `quality_notes`
- `owner_table`

For the three primary FBBP JSONL exports, formal runtime should read `runtime_snapshot` from this repo's checked-in `formal_snapshots/` tree. `upstream_pipeline` remains the canonical provenance pointer back to the originating export path.

## Structured Search Output

`search_knowledge.result` remains backward-compatible with `answer`, `result_count`, and `results`, but formal consumers should now prefer:

- `answer_text`
- `structured_output.claims`
- `structured_output.evidence_rows`
- `structured_output.limitations`
- `structured_output.provenance_caveats`

This is the canonical path for DeerFlow formal reports and UI panels.

The recommended sources for these fields are:

- `FBBP_FORMAL_DATASET_VERSION`
- `FBBP_FORMAL_RUNTIME_PROFILE`

Legacy compatibility is still accepted through:

Legacy lowercase `fbtp`-prefixed aliases are still accepted internally for older local scripts, but public deployment examples should use `FBBP_*`.

When available, `dataset_version` can be backed by checked-in descriptors under `configs/datasets/`.

## MCP Search Execution Path

On this machine, the official MCP execution model for `search_knowledge` is:

1. MCP client calls `fbbp-mcp-rag-server`
2. MCP server forwards the request to the DeerFlow formal HTTP gateway
3. the gateway executes `query_private_rag.py`
4. the Python query script uses the local formal search service against the prepared FBBP database

This keeps the MCP layer on one stable path and avoids relying on the older in-process HTTP MCP worker / PostgreSQL combination.
