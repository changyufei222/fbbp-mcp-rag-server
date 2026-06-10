# FBBP MCP Tool API Reference

This document is the job-ready API reference for `fbbp-mcp-rag-server`. It describes the public MCP tool surface, response contract, error shape, and deployment boundary for Codex, Claude Code, Cursor, and DeerFlow consumers.

## Response Contract

Every tool returns the same top-level envelope:

```json
{
  "ok": true,
  "tool": "tool_name",
  "contract_version": "1.1",
  "request": {},
  "result": {},
  "provenance": {},
  "diagnostics": {
    "latency_ms": 12.3
  },
  "error": null
}
```

Error responses keep the same envelope and set `ok=false`:

```json
{
  "ok": false,
  "tool": "tool_name",
  "contract_version": "1.1",
  "request": {},
  "result": {},
  "provenance": {},
  "diagnostics": {},
  "error": {
    "code": "INVALID_REQUEST",
    "message": "human-readable error",
    "details": {}
  }
}
```

Common error codes:

- `INVALID_REQUEST`
- `IMPORT_ERROR`
- `TIMEOUT_ERROR`
- `UNKNOWN_ERROR`

Error-code intent:

| Code | Typical meaning | Client action |
|---|---|---|
| `INVALID_REQUEST` | required field missing, unsupported value, or malformed payload | fix the request locally before retrying |
| `IMPORT_ERROR` | backend dependency or optional module failed to load | inspect environment / package state |
| `TIMEOUT_ERROR` | upstream lookup or long-running task timed out | retry with backoff or reduce request scope |
| `UNKNOWN_ERROR` | unexpected server-side failure | inspect logs and server health before retrying |

## Boundary Behavior Matrix

| Situation | Expected behavior | Client action |
|---|---|---|
| unknown tool name | MCP framework rejects the request before business logic runs | update the client config or tool name |
| malformed arguments | tool returns `ok=false` with `INVALID_REQUEST` | fix the request payload locally |
| formal gateway unavailable | `search_knowledge` returns `FORMAL_QUERY_GATEWAY_ERROR` | check gateway health before retry |
| nonexistent ingest path | `preview_ingest` / `ingest_sources` return `INGEST_INPUT_ERROR` | correct the local path, do not retry unchanged |
| public API timeout | lookup tool returns timeout-shaped error envelope | retry with backoff |
| loopback-only deployment assumptions broken | non-loopback HTTP bind intentionally relaxes loopback host validation | put the service behind a reverse proxy |

## Runtime Tools

### `server_status`

Purpose: returns runtime status and shared `ragkb` configuration details.

Input:

```json
{}
```

Output highlights:

- `result.runtime`
- `result.ragkb`
- `provenance.dataset_version`
- `diagnostics.latency_ms`

### `health_status`

Purpose: reports runtime, database, and public lookup health.

Input:

```json
{}
```

Output highlights:

- `result.runtime`
- `result.database`
- `result.public_lookups`

### `tool_contract_version`

Purpose: returns the active MCP contract version.

Input:

```json
{}
```

Expected contract:

```json
{
  "result": {
    "contract_version": "1.1"
  }
}
```

## Private Knowledge Tools

### `list_sources`

Purpose: lists indexed FBBP sources and source-registry metadata.

Input:

```json
{
  "record_type": null,
  "limit": 100
}
```

Output highlights:

- `result.sources`
- `result.sources[].source`
- `result.sources[].source_category`
- `result.sources[].source_description`
- `result.sources[].owner_table`

### `list_record_types`

Purpose: lists available record types from the shared knowledge base.

Input:

```json
{
  "limit": 1000
}
```

### `get_source_summary`

Purpose: returns source-level provenance and record/chunk counts.

Input:

```json
{
  "source": "interaction_cards_v2.jsonl",
  "limit": 1000
}
```

Boundary: source must exist in the FBBP registry or database result set. Missing sources should return a normal error envelope.

### `get_document_chunk`

Purpose: fetches one chunk by `source + chunk_id`.

Input:

```json
{
  "source": "interaction_cards_v2.jsonl",
  "chunk_id": "chunk-0001"
}
```

### `search_knowledge`

Purpose: searches the private FBBP knowledge base through the formal gateway.

Input:

```json
{
  "query": "knottin scaffold landscape",
  "top_k": 5,
  "record_type": null,
  "filters": [],
  "include_answer": true,
  "include_evidence": true,
  "answer_mode": "formal"
}
```

Output highlights:

- `result.answer_text`
- `result.structured_output.claims`
- `result.structured_output.evidence_rows`
- `result.structured_output.limitations`
- `diagnostics.query_transport`
- `diagnostics.gateway_url`

### `explain_search`

Purpose: returns normalized search parameters and retrieval summary without pretending to be a final answer.

Input:

```json
{
  "query": "knottin scaffold landscape",
  "top_k": 5,
  "record_type": null,
  "filters": [],
  "answer_mode": "extractive"
}
```

### `preview_ingest`

Purpose: previews a local ingest path without mutating the knowledge base.

Input:

```json
{
  "input_path": "data/schema_tables_rag_ready"
}
```

### `ingest_sources`

Purpose: ingests local files into the shared FBBP knowledge base.

Input:

```json
{
  "input_path": "data/schema_tables_rag_ready",
  "limit": null,
  "chunk_size": 800,
  "chunk_overlap": 120,
  "batch_size": 64
}
```

Boundary: production ingest should use explicit dataset versions and manifests. Ad hoc ingest is useful for local development but should not replace the canonical FBBP snapshot.

## Public Scientific Lookup Tools

### `search_pubmed`

Input:

```json
{
  "query": "knottin peptide inhibitor",
  "retmax": 5
}
```

Boundary: depends on public NCBI availability and rate limits.

### `get_uniprot_entry`

Input:

```json
{
  "accession": "P69905"
}
```

Boundary: depends on UniProt public API availability.

### `get_pdb_entry`

Input:

```json
{
  "pdb_id": "1CRN"
}
```

Boundary: depends on RCSB PDB public API availability.

## Client Matrix

| Client | Config file | Status |
|---|---|---|
| Codex | `examples/clients/codex.config.toml` | config-ready |
| Claude Code | `examples/clients/claude-code.mcp.json` | config-ready |
| Cursor | `examples/clients/cursor.mcp.json` | config-ready |
| DeerFlow | `examples/extensions_config.deerflow.json` | config-ready |

The final release check validates the presence and FBBP naming of these files. Live end-to-end client UI verification is intentionally separate because Codex, Claude Code, Cursor, and DeerFlow have different local runtime states.

See also:

- `docs/client_acceptance_matrix.md`
- `reports/final_release/latest/client_acceptance_matrix.md`
- `reports/final_release/latest/live_client_acceptance.md`

## Deployment Modes

- `stdio`: best for local MCP clients.
- `streamable-http`: best for DeerFlow, browser-visible gateway testing, and Docker.
- Docker Compose: `docker compose up -d`.
- systemd: use `configs/fbbp-mcp-rag-server.service.example`.

Operational runbook:

- `docs/production_service_runbook.md`
- `.github/workflows/fbbp-mcp-release-gate.yml`

## Security Boundary

Loopback HTTP enables DNS rebinding protection. Non-loopback binding disables loopback host lock so WSL and container networking can work. Production deployments should place the server behind a reverse proxy with API key, OIDC, or service-network ACLs.
