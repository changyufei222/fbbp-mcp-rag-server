from __future__ import annotations

import argparse
import asyncio

from fbbp_mcp_server.bootstrap import ensure_local_site_packages

ensure_local_site_packages()

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import uvicorn

from fbbp_mcp_server.service import (
    explain_search as run_explain_search,
    get_document_chunk_by_id,
    get_source_summary as run_get_source_summary,
    get_pdb_entry as run_get_pdb_entry,
    get_uniprot_entry as run_get_uniprot_entry,
    health_status as run_health_status,
    ingest_sources_into_knowledge,
    list_available_sources,
    list_record_types as run_list_record_types,
    preview_ingest as run_preview_ingest,
    search_pubmed_articles as run_search_pubmed_articles,
    search_knowledge_via_formal_http_gateway as run_search_knowledge_via_formal_http_gateway,
    server_status as get_server_status,
    tool_contract_version as run_tool_contract_version,
)


mcp = FastMCP("FBBP MCP RAG Server", json_response=True)


def _resolve_transport_security(host: str) -> TransportSecuritySettings:
    if host in ("127.0.0.1", "localhost", "::1"):
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
        )

    # Non-loopback bindings are used for local cross-boundary access such as WSL IPs.
    # In that mode, loopback-only Host validation breaks legitimate requests.
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


@mcp.tool()
async def server_status() -> dict:
    """Return basic runtime status and shared ragkb configuration details."""
    return await asyncio.to_thread(get_server_status)


@mcp.tool()
async def health_status() -> dict:
    """Return runtime, database, and public scientific lookup health diagnostics."""
    return await asyncio.to_thread(run_health_status)


@mcp.tool()
async def tool_contract_version() -> dict:
    """Return the current MCP tool contract version exposed by this server."""
    return await asyncio.to_thread(run_tool_contract_version)


@mcp.tool()
async def list_sources(record_type: str | None = None, limit: int = 100) -> dict:
    """List indexed sources currently available in the shared FBBP knowledge base."""
    return await asyncio.to_thread(list_available_sources, record_type, limit)


@mcp.tool()
async def list_record_types(limit: int = 1000) -> dict:
    """List available record types aggregated from the shared FBBP knowledge base."""
    return await asyncio.to_thread(run_list_record_types, limit)


@mcp.tool()
async def get_source_summary(source: str, limit: int = 1000) -> dict:
    """Summarize one indexed source across record types and chunk counts."""
    return await asyncio.to_thread(run_get_source_summary, source, limit)


@mcp.tool()
async def get_document_chunk(source: str, chunk_id: str) -> dict:
    """Fetch a specific indexed chunk by source and chunk_id."""
    return await asyncio.to_thread(get_document_chunk_by_id, source, chunk_id)


@mcp.tool()
async def search_knowledge(
    query: str,
    top_k: int = 5,
    record_type: str | None = None,
    filters: list[str] | None = None,
    include_answer: bool = True,
    include_evidence: bool = False,
    answer_mode: str | None = None,
) -> dict:
    """Search the private FBBP knowledge base through the formal HTTP gateway."""
    return await asyncio.to_thread(
        run_search_knowledge_via_formal_http_gateway,
        query=query,
        top_k=top_k,
        record_type=record_type,
        filters=filters,
        include_answer=include_answer,
        include_evidence=include_evidence,
        answer_mode=answer_mode,
    )


@mcp.tool()
async def explain_search(
    query: str,
    top_k: int = 5,
    record_type: str | None = None,
    filters: list[str] | None = None,
    answer_mode: str | None = None,
) -> dict:
    """Explain a search request by returning normalized parameters and retrieval summary."""
    return await asyncio.to_thread(
        run_explain_search,
        query,
        top_k,
        record_type,
        filters,
        answer_mode,
    )


@mcp.tool()
async def preview_ingest(input_path: str) -> dict:
    """Preview an ingest request without mutating the shared FBBP knowledge base."""
    return await asyncio.to_thread(run_preview_ingest, input_path)


@mcp.tool()
async def ingest_sources(
    input_path: str,
    limit: int | None = None,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    batch_size: int = 64,
) -> dict:
    """Ingest local files into the shared FBBP knowledge base."""
    return await asyncio.to_thread(
        ingest_sources_into_knowledge,
        input_path,
        limit,
        chunk_size,
        chunk_overlap,
        batch_size,
    )


@mcp.tool()
async def search_pubmed(query: str, retmax: int = 5) -> dict:
    """Search PubMed and return compact article summaries for a query."""
    return await asyncio.to_thread(run_search_pubmed_articles, query, retmax)


@mcp.tool()
async def get_uniprot_entry(accession: str) -> dict:
    """Fetch a compact UniProt entry summary by accession."""
    return await asyncio.to_thread(run_get_uniprot_entry, accession)


@mcp.tool()
async def get_pdb_entry(pdb_id: str) -> dict:
    """Fetch a compact RCSB PDB entry summary by PDB identifier."""
    return await asyncio.to_thread(run_get_pdb_entry, pdb_id)


def main() -> None:
    parser = argparse.ArgumentParser(prog="fbbp-mcp-rag-server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.transport_security = _resolve_transport_security(args.host)
        uvicorn.run(mcp.streamable_http_app(), host=args.host, port=args.port, log_level="info")
        return
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
