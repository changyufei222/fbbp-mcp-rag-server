from __future__ import annotations

import json
import sys
from typing import Any

from fbbp_mcp_server.bootstrap import ensure_local_site_packages, ensure_ragkb_importable

ensure_local_site_packages()

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False

load_dotenv()
ensure_ragkb_importable()


def _compact_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    metadata = metadata or {}
    preferred_keys = [
        "record_type",
        "Scaffold_Category",
        "Targets_gene_name",
        "Targets_species_name",
        "Sources_title",
        "Sources_identifier",
        "Sources_publication_date",
        "File_Name",
        "Sequence_UniProt_ID",
        "Sequence_PDB_ID",
    ]
    compact: dict[str, Any] = {}
    for key in preferred_keys:
        value = metadata.get(key)
        if value not in (None, ""):
            compact[key] = value
    return compact


def _format_context(context: dict[str, Any]) -> dict[str, Any]:
    content = str(context.get("content", ""))
    return {
        "source": context.get("source"),
        "chunk_id": context.get("chunk_id"),
        "score": context.get("score"),
        "excerpt": content[:400],
        "metadata": _compact_metadata(context.get("metadata")),
    }


def _run(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    from ragkb.config import Settings
    from ragkb.wsl_pg import warm_wsl_postgres_route

    settings = Settings()
    warm_wsl_postgres_route(settings.pg_host)

    if action == "server_status":
        import psycopg

        db_probe: dict[str, Any]
        try:
            conn = psycopg.connect(
                host=settings.pg_host,
                port=settings.pg_port,
                dbname=settings.pg_db,
                user=settings.pg_user,
                password=settings.pg_password,
                connect_timeout=5,
            )
            cur = conn.cursor()
            cur.execute("select 1")
            db_probe = {"ok": True, "result": cur.fetchone()[0]}
            conn.close()
        except Exception as exc:
            db_probe = {"ok": False, "error": str(exc)}

        return {
            "status": "ok",
            "pg_host": settings.pg_host,
            "pg_port": settings.pg_port,
            "pg_db": settings.pg_db,
            "pg_table": settings.pg_table,
            "embedding_provider": settings.embedding_provider,
            "default_answer_mode": payload.get("default_answer_mode", settings.answer_mode),
            "db_probe": db_probe,
        }

    if action == "list_sources":
        from ragkb.storage.pgvector_store import list_sources

        sources = list_sources(
            settings=settings,
            record_type=payload.get("record_type"),
            limit=int(payload.get("limit", 100)),
        )
        return {
            "count": len(sources),
            "record_type": payload.get("record_type"),
            "sources": sources,
        }

    if action == "list_record_types":
        from ragkb.storage.pgvector_store import list_sources

        limit = int(payload.get("limit", 1000))
        sources = list_sources(settings=settings, limit=limit)
        grouped: dict[str, dict[str, Any]] = {}
        for item in sources:
            record_type = item.get("record_type") or "unknown"
            bucket = grouped.setdefault(
                record_type,
                {"record_type": record_type, "source_count": 0, "chunk_count": 0},
            )
            bucket["source_count"] += 1
            bucket["chunk_count"] += int(item.get("chunk_count", 0))

        return {
            "record_types": sorted(grouped.values(), key=lambda row: (-row["chunk_count"], row["record_type"])),
        }

    if action == "get_source_summary":
        from ragkb.storage.pgvector_store import list_sources

        source = payload["source"]
        limit = int(payload.get("limit", 1000))
        sources = list_sources(settings=settings, limit=limit)
        matched = [item for item in sources if item.get("source") == source]
        if not matched:
            return {"found": False, "source": source}
        return {
            "found": True,
            "source": source,
            "record_types": matched,
            "total_chunks": sum(int(item.get("chunk_count", 0)) for item in matched),
        }

    if action == "get_document_chunk":
        from ragkb.storage.pgvector_store import get_chunk

        row = get_chunk(settings=settings, source=payload["source"], chunk_id=payload["chunk_id"])
        if not row:
            return {"found": False, "source": payload["source"], "chunk_id": payload["chunk_id"]}
        return {
            "found": True,
            "source": row["source"],
            "chunk_id": row["chunk_id"],
            "content": row["content"],
            "metadata": _compact_metadata(row.get("metadata")),
        }

    if action == "search_knowledge":
        from ragkb.answer.generator import build_answer
        from ragkb.retrieval.filters import parse_filters
        from ragkb.retrieval.retriever import retrieve
        from ragkb.search_payloads import assemble_evidence_bundle, format_context

        parsed_filters = parse_filters(payload.get("filters") or [])
        contexts = retrieve(
            query=payload["query"],
            top_k=int(payload.get("top_k", 5)),
            settings=settings,
            record_type=payload.get("record_type"),
            filters=parsed_filters,
        )
        evidence_bundle = assemble_evidence_bundle(payload["query"], contexts, settings)

        answer = None
        if payload.get("include_answer", True):
            settings.answer_mode = payload.get("answer_mode") or settings.answer_mode
            settings.evidence_mode = "table" if payload.get("include_evidence", False) else "none"
            answer = build_answer(payload["query"], contexts, settings, evidence_bundle=evidence_bundle)

        response = {
            "query": payload["query"],
            "record_type": payload.get("record_type"),
            "filters": payload.get("filters") or [],
            "top_k": int(payload.get("top_k", 5)),
            "answer": answer,
            "result_count": len(contexts),
            "results": [format_context(context) for context in contexts],
        }
        if payload.get("include_evidence", False):
            response["evidence"] = evidence_bundle or {}
        return response

    if action == "explain_search":
        from ragkb.retrieval.filters import parse_filters
        from ragkb.retrieval.retriever import retrieve

        parsed_filters = parse_filters(payload.get("filters") or [])
        contexts = retrieve(
            query=payload["query"],
            top_k=int(payload.get("top_k", 5)),
            settings=settings,
            record_type=payload.get("record_type"),
            filters=parsed_filters,
        )
        return {
            "query": payload["query"],
            "pg_table": settings.pg_table,
            "record_type": payload.get("record_type"),
            "filters": payload.get("filters") or [],
            "top_k": int(payload.get("top_k", 5)),
            "answer_mode": payload.get("answer_mode") or payload.get("default_answer_mode"),
            "result_count": len(contexts),
            "sources": [context.get("source") for context in contexts if context.get("source")],
        }

    if action == "ingest_sources":
        from ragkb.ingest.pipeline import run_ingest

        inserted = run_ingest(
            input_path=payload["input_path"],
            settings=settings,
            limit=payload.get("limit"),
            chunk_size=int(payload.get("chunk_size", 800)),
            chunk_overlap=int(payload.get("chunk_overlap", 120)),
            batch_size=int(payload.get("batch_size", 64)),
        )
        return {
            "ok": True,
            "input_path": payload["input_path"],
            "inserted": inserted,
            "pg_table": settings.pg_table,
        }

    raise ValueError(f"Unknown action: {action}")


def main() -> None:
    payload = json.loads(sys.stdin.read())
    try:
        result = _run(payload)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise


if __name__ == "__main__":
    main()
