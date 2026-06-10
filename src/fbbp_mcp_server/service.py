from __future__ import annotations

from collections import Counter
import json
import os
import re
import subprocess
import sys
import time
from importlib import import_module
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from fbbp_mcp_server.bootstrap import ensure_local_site_packages, ensure_ragkb_importable
from fbbp_mcp_server.errors import map_exception
from fbbp_mcp_server.formal_runtime import formal_runtime_snapshot, get_source_registry_entry
from fbbp_mcp_server.health import build_health_snapshot
from fbbp_mcp_server.schemas import CONTRACT_VERSION, build_error_response, build_tool_response
from fbbp_mcp_server.scientific_lookups import (
    get_pdb_entry as fetch_pdb_entry,
    get_uniprot_entry as fetch_uniprot_entry,
    search_pubmed as run_search_pubmed,
)

ensure_local_site_packages()

from dotenv import load_dotenv

load_dotenv()
ensure_ragkb_importable()
_SEARCH_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_FORMAL_GATEWAY_SEARCH_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CORPUS_PROFILE_CACHE: dict[str, dict[str, Any]] = {}
_SCAFFOLD_TERMS = (
    "adnectin",
    "cyclotide",
    "knottin",
    "obody",
    "kunitz",
    "centyrin",
    "affimer",
    "evh1domain",
    "betarolldomain",
    "phdfingerdomain",
    "avimer",
    "ibody",
)
_TARGET_QUERY_TERMS = (
    "target",
    "targets",
    "gene",
    "genes",
    "receptor",
    "affinity",
    "binding",
    "靶点",
    "受体",
)
_SOURCE_QUERY_TERMS = (
    "source",
    "sources",
    "evidence",
    "provenance",
    "identifier",
    "citation",
    "assay",
    "来源",
    "证据",
    "溯源",
)
_ALL_CLASS_TERMS = (
    "12 类",
    "12类",
    "all 12",
    "all classes",
    "all scaffold",
    "all scaffolds",
    "class distribution",
    "scaffold distribution",
    "scaffold landscape",
    "类别分布",
    "全量",
    "全库",
    "全量数据",
)


def _first_env_value(*keys: str, default: str | None = None) -> str | None:
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return default


def _default_top_k() -> int:
    return int(_first_env_value("FBBP_MCP_DEFAULT_TOP_K", "FBTP_MCP_DEFAULT_TOP_K", default="5") or "5")


def _default_answer_mode() -> str:
    return _first_env_value(
        "FBBP_MCP_DEFAULT_ANSWER_MODE",
        "FBTP_MCP_DEFAULT_ANSWER_MODE",
        "ANSWER_MODE",
        default="extractive",
    ) or "extractive"


def _effective_answer_mode(answer_mode: str | None, include_answer: bool) -> str:
    normalized = str(answer_mode or "").strip().lower()
    if normalized:
        return normalized
    if include_answer:
        return os.getenv(
            "FBBP_FORMAL_DEFAULT_ANSWER_MODE",
            os.getenv("FBTP_FORMAL_DEFAULT_ANSWER_MODE", "formal"),
        )
    return _default_answer_mode()


def _repo_src_path() -> Path:
    return Path(__file__).resolve().parents[1]


def _project_root_path() -> Path:
    for key in ("FBBP_PROJECT_ROOT", "FBTP_PROJECT_ROOT"):
        value = os.environ.get(key, "").strip()
        if value:
            return Path(value)
    return _repo_src_path().parent


def _worker_python_executable(repo_root: Path | None = None, fallback_python: str | None = None) -> str:
    repo_root = repo_root or _repo_src_path().parent
    candidates = [
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "bin" / "python",
        repo_root.parent / "_runtime_venv" / "Scripts" / "python.exe",
        repo_root.parent / "_runtime_venv" / "bin" / "python",
        repo_root / ".venv_wsl" / "bin" / "python",
        repo_root / ".venv_wsl" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists() and _python_executable_usable(candidate):
            return str(candidate)
    return fallback_python or sys.executable


def _python_executable_usable(path: Path | str) -> bool:
    candidate = str(path)
    try:
        proc = subprocess.run(
            [candidate, "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception:
        return False
    return proc.returncode == 0


def _search_cache_ttl_seconds() -> float:
    return float(
        _first_env_value(
            "FBBP_MCP_SEARCH_CACHE_TTL_SECONDS",
            "FBTP_MCP_SEARCH_CACHE_TTL_SECONDS",
            default="120",
        )
        or "120"
    )


def _formal_query_gateway_url() -> str:
    for key in ("FBBP_FORMAL_QUERY_GATEWAY_URL", "FBTP_FORMAL_QUERY_GATEWAY_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return "http://127.0.0.1:8001/api/fbbp/formal-search"


def _formal_query_gateway_timeout_seconds() -> float:
    return float(
        _first_env_value(
            "FBBP_FORMAL_QUERY_GATEWAY_TIMEOUT_SECONDS",
            "FBTP_FORMAL_QUERY_GATEWAY_TIMEOUT_SECONDS",
            default="300",
        )
        or "300"
    )


def _child_pythonpath() -> str:
    repo_root = _repo_src_path().parent
    parts = [
        str(_repo_src_path()),
        str(repo_root.parent / "llm-rag-knowledge-base" / "src"),
    ]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        parts.extend(part for part in existing.split(os.pathsep) if part)
    return os.pathsep.join(dict.fromkeys(parts))


def _worker_payload(action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return {"action": action, **payload, "default_answer_mode": _default_answer_mode()}


def _use_subprocess_worker_only() -> bool:
    return (
        _first_env_value("FBBP_MCP_USE_SUBPROCESS_WORKER", "FBTP_MCP_USE_SUBPROCESS_WORKER", default="")
        or ""
    ).lower() in {"1", "true", "yes", "on"}


def _run_db_worker_direct(action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    worker_payload = _worker_payload(action, payload)
    worker_module = import_module("fbbp_mcp_server.db_worker")
    return worker_module._run(worker_payload)


def _run_db_worker_subprocess(action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    worker_payload = _worker_payload(action, payload)
    worker_module = "fbbp_mcp_server.db_worker"
    env = os.environ.copy()
    env["PYTHONPATH"] = _child_pythonpath()
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.pop("PYTHONHOME", None)
    worker_python = _worker_python_executable(fallback_python=sys.executable)
    worker_cmd = [worker_python]
    if worker_python == sys.executable:
        worker_cmd.append("-S")
    proc = subprocess.run(
        [*worker_cmd, "-m", worker_module],
        input=json.dumps(worker_payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    stdout = proc.stdout.strip()
    if not stdout:
        stderr = proc.stderr.strip()
        raise RuntimeError(stderr or f"db worker failed with exit code {proc.returncode}")

    data = json.loads(stdout)
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "db worker failed"))
    return data["result"]


def _run_db_worker(action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    direct_error: Exception | None = None
    if not _use_subprocess_worker_only():
        try:
            return _run_db_worker_direct(action, payload)
        except Exception as exc:
            direct_error = exc

    try:
        return _run_db_worker_subprocess(action, payload)
    except Exception:
        if direct_error is not None:
            raise direct_error
        raise


def _result_sources(result: dict[str, Any]) -> list[str]:
    rows = result.get("results") or []
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        source = str((row or {}).get("source") or "").strip()
        if not source or source in seen:
            continue
        seen.add(source)
        ordered.append(source)
    return ordered


def _tool_call(
    *,
    tool: str,
    request: dict[str, Any],
    runner,
    provenance: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = runner()
        final_diagnostics = {"latency_ms": round((time.perf_counter() - started) * 1000, 2)}
        if diagnostics:
            final_diagnostics.update(diagnostics)
        return build_tool_response(
            tool=tool,
            request=request,
            result=result,
            provenance=provenance or {},
            diagnostics=final_diagnostics,
        )
    except Exception as exc:
        final_diagnostics = {"latency_ms": round((time.perf_counter() - started) * 1000, 2)}
        if diagnostics:
            final_diagnostics.update(diagnostics)
        return build_error_response(
            tool=tool,
            request=request,
            diagnostics=final_diagnostics,
            error=map_exception(exc),
        )


def _formal_runtime() -> dict[str, Any]:
    return formal_runtime_snapshot(_repo_src_path().parent)


def _runtime_provenance(runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime = runtime or _formal_runtime()
    return {
        "dataset_version": runtime.get("dataset_version", "unknown"),
        "runtime_profile": runtime.get("runtime_profile", "unknown"),
        "formal_db_mode": runtime.get("formal_db_mode", "unknown"),
        "db_identity": runtime.get("db_identity", "unknown"),
        "build_id": runtime.get("build_id", "unknown"),
        "source_registry_version": runtime.get("source_registry_version", "unknown"),
    }


def _source_registry_entry(source: str | None, runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime = runtime or _formal_runtime()
    descriptor = runtime.get("dataset_descriptor") or {}
    entry = get_source_registry_entry(descriptor, source)
    return dict(entry or {})


def _enrich_source_row(row: dict[str, Any] | None, runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    enriched = dict(row or {})
    registry = _source_registry_entry(enriched.get("source"), runtime)
    for key in (
        "source_category",
        "source_description",
        "upstream_pipeline",
        "quality_notes",
        "owner_table",
    ):
        if registry.get(key) not in (None, "") and enriched.get(key) in (None, ""):
            enriched[key] = registry[key]
    enriched["registry_status"] = "registered" if registry else "missing"
    return enriched


def _enrich_source_listing_result(result: dict[str, Any], runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    enriched = dict(result or {})
    if isinstance(enriched.get("sources"), list):
        enriched["sources"] = [_enrich_source_row(row, runtime) for row in enriched.get("sources", [])]
    if enriched.get("source"):
        registry = _source_registry_entry(str(enriched.get("source")), runtime)
        if registry:
            enriched["source_registry"] = registry
    return enriched


def _answer_text(answer: Any) -> str | None:
    if answer in (None, ""):
        return None
    if isinstance(answer, str):
        normalized = answer.strip()
        return normalized or None
    if isinstance(answer, dict):
        for key in ("text", "answer", "value"):
            value = answer.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return json.dumps(answer, ensure_ascii=False)
    return str(answer).strip() or None


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def _contains_cjk(text: str | None) -> bool:
    return bool(text and re.search(r"[\u4e00-\u9fff]", text))


def _mentions_all_scaffold_classes(query: str) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in _ALL_CLASS_TERMS)


def _extract_excerpt_field(excerpt: str | None, pattern: str) -> str | None:
    if not excerpt:
        return None
    match = re.search(pattern, excerpt, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _normalize_counter(counter: Counter[str], limit: int = 3) -> list[tuple[str, int]]:
    return [(value, count) for value, count in counter.most_common(limit) if value]


def _format_counter_items(counter: Counter[str], language: str, limit: int = 3) -> str:
    items = [f"{value} ({count})" for value, count in _normalize_counter(counter, limit=limit)]
    if not items:
        return ""
    if language == "zh":
        return "、".join(items)
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _extract_filter_value(filters: list[str] | None, field_name: str) -> str | None:
    prefix = f"{field_name.lower()}="
    for raw_filter in filters or []:
        text = str(raw_filter or "").strip()
        if text.lower().startswith(prefix):
            _, _, value = text.partition("=")
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def _interaction_cards_source_path(runtime: dict[str, Any] | None = None) -> Path | None:
    runtime = runtime or _formal_runtime()
    descriptor = runtime.get("dataset_descriptor") or {}
    registry = (descriptor.get("source_registry") or {}).get("interaction_cards_v2.jsonl") or {}
    runtime_snapshot = str(registry.get("runtime_snapshot") or "").strip()
    if runtime_snapshot:
        snapshot_candidate = Path(runtime_snapshot)
        return snapshot_candidate if snapshot_candidate.is_absolute() else (_project_root_path() / snapshot_candidate)

    pipeline = str(registry.get("upstream_pipeline") or "").strip()
    if not pipeline:
        rebuild = descriptor.get("rebuild") or {}
        for item in rebuild.get("source_allowlist") or []:
            candidate = str(item or "").strip()
            if candidate.endswith("interaction_cards_v2.jsonl"):
                pipeline = candidate
                break
    if not pipeline:
        return None
    candidate = Path(pipeline)
    return candidate if candidate.is_absolute() else (_project_root_path() / candidate)


def _get_corpus_scaffold_profile(runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime = runtime or _formal_runtime()
    cache_key = "|".join(
        [
            str(runtime.get("dataset_version") or "unknown"),
            str(runtime.get("build_id") or "unknown"),
            str(runtime.get("source_registry_version") or "unknown"),
        ]
    )
    cached = _CORPUS_PROFILE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    source_path = _interaction_cards_source_path(runtime)
    if not source_path or not source_path.exists():
        empty_profile = {"class_count": 0, "classes": [], "by_scaffold": {}}
        _CORPUS_PROFILE_CACHE[cache_key] = empty_profile
        return empty_profile

    by_scaffold_raw: dict[str, dict[str, Any]] = {}
    with source_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            content = str(row.get("content") or row.get("excerpt") or "")
            scaffold = _extract_excerpt_field(content, r"- Scaffold Typ<local_path_removed>")
            if not scaffold:
                continue
            scaffold_key = scaffold.lower()
            bucket = by_scaffold_raw.setdefault(
                scaffold_key,
                {
                    "scaffold": scaffold,
                    "count": 0,
                    "target_rows": 0,
                    "top_targets": Counter(),
                    "interaction_classes": Counter(),
                    "evidence_tables": Counter(),
                },
            )
            bucket["count"] += 1

            target_name = _first_non_empty(
                _extract_excerpt_field(content, r"- Gene Name Specie<local_path_removed>"),
                _extract_excerpt_field(content, r"- Gene Nam<local_path_removed>"),
            )
            if target_name:
                bucket["target_rows"] += 1
                bucket["top_targets"][target_name] += 1

            interaction_class = _extract_excerpt_field(content, r"- Interaction Clas<local_path_removed>")
            if interaction_class:
                bucket["interaction_classes"][interaction_class] += 1

            evidence_tables = _extract_excerpt_field(content, r"- Table<local_path_removed>")
            if evidence_tables:
                for table_name in [item.strip() for item in evidence_tables.split(",") if item.strip()]:
                    bucket["evidence_tables"][table_name] += 1

    classes: list[dict[str, Any]] = []
    by_scaffold: dict[str, dict[str, Any]] = {}
    for scaffold_key, bucket in sorted(by_scaffold_raw.items(), key=lambda item: (-item[1]["count"], item[1]["scaffold"])):
        rendered = {
            "scaffold": bucket["scaffold"],
            "count": bucket["count"],
            "target_rows": bucket["target_rows"],
            "top_targets": _normalize_counter(bucket["top_targets"], limit=10),
            "interaction_classes": _normalize_counter(bucket["interaction_classes"], limit=5),
            "evidence_tables": _normalize_counter(bucket["evidence_tables"], limit=8),
        }
        classes.append(rendered)
        by_scaffold[scaffold_key] = rendered

    profile = {
        "class_count": len(classes),
        "classes": classes,
        "by_scaffold": by_scaffold,
    }
    _CORPUS_PROFILE_CACHE[cache_key] = profile
    return profile


def _known_scaffold_terms(runtime: dict[str, Any] | None = None) -> list[str]:
    runtime = runtime or _formal_runtime()
    profile = _get_corpus_scaffold_profile(runtime)
    dynamic_terms = [str(item.get("scaffold") or "").strip().lower() for item in profile.get("classes", [])]
    return list(dict.fromkeys([*dynamic_terms, *_SCAFFOLD_TERMS]))


def _extract_scaffold_terms(query: str, filters: list[str] | None, runtime: dict[str, Any] | None = None) -> list[str]:
    scaffold_filter = _extract_filter_value(filters, "Scaffold_Category")
    if scaffold_filter:
        return [scaffold_filter.lower()]

    lowered = query.lower()
    return [term for term in _known_scaffold_terms(runtime) if term in lowered]


def _query_mentions(query: str, terms: tuple[str, ...]) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in terms)


def _build_formal_query_plan(
    *,
    query: str,
    top_k: int,
    record_type: str | None,
    filters: list[str] | None,
    runtime: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    normalized_filters = [str(item).strip() for item in (filters or []) if str(item).strip()]
    scaffold_terms = _extract_scaffold_terms(query, normalized_filters, runtime)
    scaffold_filter = _extract_filter_value(normalized_filters, "Scaffold_Category")
    focus_scaffold = scaffold_filter or (scaffold_terms[0] if scaffold_terms else None)
    seen: set[str] = set()
    query_plan: list[dict[str, Any]] = []
    per_query_top_k = max(top_k, 6)

    def add_plan(
        label: str,
        query_text: str,
        extra_filters: list[str] | None = None,
        *,
        use_base_filters: bool = True,
        record_type_override: str | None = None,
    ) -> None:
        merged_filters = list(
            dict.fromkeys([*(normalized_filters if use_base_filters else []), *(extra_filters or [])])
        )
        normalized_query = query_text.strip()
        if not normalized_query:
            return
        signature = json.dumps(
            {
                "label": label,
                "query": normalized_query.lower(),
                "filters": merged_filters,
                "record_type": record_type_override or record_type,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if signature in seen:
            return
        seen.add(signature)
        query_plan.append(
            {
                "label": label,
                "query": normalized_query,
                "top_k": per_query_top_k,
                "record_type": record_type_override or record_type,
                "filters": merged_filters,
            }
        )

    add_plan("primary", query)
    if focus_scaffold:
        extra_filters = [] if scaffold_filter else [f"Scaffold_Category={focus_scaffold}"]
        add_plan("scaffold_focus", f"{focus_scaffold} scaffold structure domain motif disulfide", extra_filters)
        add_plan("target_focus", f"{focus_scaffold} target gene interaction affinity binding receptor", extra_filters)
        if normalized_filters:
            add_plan(
                "semantic_fallback",
                f"{focus_scaffold} scaffold domain motif evidence provenance source",
                use_base_filters=False,
                record_type_override="csv",
            )
        else:
            add_plan("source_focus", f"{focus_scaffold} evidence provenance identifier source assay", extra_filters)
    else:
        if _query_mentions(query, _TARGET_QUERY_TERMS):
            add_plan("target_focus", f"{query} target gene interaction affinity binding")
        if _query_mentions(query, _SOURCE_QUERY_TERMS):
            add_plan("source_focus", f"{query} evidence provenance identifier source assay")

    return query_plan[:4]


def _merge_formal_query_results(
    query_plan: list[dict[str, Any]],
    runtime: dict[str, Any] | None,
    top_k: int,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    fused_rows: dict[tuple[str, str], dict[str, Any]] = {}
    errors: list[dict[str, str]] = []

    for plan in query_plan:
        request = {
            "query": plan["query"],
            "top_k": plan["top_k"],
            "record_type": plan["record_type"],
            "filters": plan["filters"],
            "include_answer": False,
            "include_evidence": True,
            "answer_mode": "extractive",
        }
        try:
            result = _run_db_worker("search_knowledge", request)
        except Exception as exc:
            errors.append({"label": plan["label"], "message": str(exc)})
            continue

        for rank, row in enumerate(result.get("results") or [], start=1):
            enriched = _enrich_source_row(row, runtime)
            identity = (str(enriched.get("source") or ""), str(enriched.get("chunk_id") or ""))
            if not identity[0] or not identity[1]:
                continue
            bucket = fused_rows.setdefault(
                identity,
                {
                    **enriched,
                    "_fusion_score": 0.0,
                    "_retrieval_labels": [],
                },
            )
            bucket["_fusion_score"] += 1.0 / (60 + rank)
            bucket["_retrieval_labels"].append(plan["label"])
            current_score = bucket.get("score")
            candidate_score = enriched.get("score")
            if isinstance(candidate_score, (int, float)) and (
                not isinstance(current_score, (int, float)) or float(candidate_score) > float(current_score)
            ):
                bucket["score"] = float(candidate_score)
                bucket["excerpt"] = enriched.get("excerpt")
                bucket["metadata"] = enriched.get("metadata") or {}

    if not fused_rows:
        return [], errors

    ordered_candidates = list(fused_rows.values())
    for row in ordered_candidates:
        row["fusion_score"] = round(float(row.pop("_fusion_score", 0.0)), 6)
        row["retrieval_labels"] = list(dict.fromkeys(row.pop("_retrieval_labels", [])))

    ordered_candidates.sort(
        key=lambda row: (
            float(row.get("fusion_score") or 0.0),
            float(row.get("score") or 0.0),
        ),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    seen_owner_tables: set[str] = set()
    for row in ordered_candidates:
        owner_table = str(row.get("owner_table") or "").strip()
        if owner_table and owner_table in seen_owner_tables:
            continue
        if owner_table:
            seen_owner_tables.add(owner_table)
        selected.append(row)
        if len(selected) >= top_k:
            break

    if len(selected) < top_k:
        selected_identities = {
            (str(row.get("source") or ""), str(row.get("chunk_id") or ""))
            for row in selected
        }
        for row in ordered_candidates:
            identity = (str(row.get("source") or ""), str(row.get("chunk_id") or ""))
            if identity in selected_identities:
                continue
            selected.append(row)
            selected_identities.add(identity)
            if len(selected) >= top_k:
                break

    return selected[:top_k], errors


def _source_registry_used(enriched_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    registry_rows: list[dict[str, Any]] = []
    for row in enriched_rows:
        source = str(row.get("source") or "").strip()
        owner_table = str(row.get("owner_table") or "").strip()
        key = (source, owner_table)
        if not source or key in seen:
            continue
        seen.add(key)
        registry_rows.append(
            {
                "source": source,
                "source_category": row.get("source_category"),
                "source_description": row.get("source_description"),
                "upstream_pipeline": row.get("upstream_pipeline"),
                "quality_notes": row.get("quality_notes"),
                "owner_table": row.get("owner_table"),
            }
        )
    return registry_rows


def _derive_evidence_table(enriched_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_table: list[dict[str, Any]] = []
    for index, row in enumerate(enriched_rows[:10], start=1):
        metadata = row.get("metadata") or {}
        excerpt = str(row.get("excerpt") or "")
        scaffold = _first_non_empty(
            metadata.get("Scaffold_Category"),
            _extract_excerpt_field(excerpt, r"Scaffold Typ<local_path_removed>"),
        )
        target = _first_non_empty(
            metadata.get("Targets_gene_name"),
            _extract_excerpt_field(excerpt, r"Target(?: Gene Name)?:\s*([^\n]+)"),
        )
        organism = _first_non_empty(
            metadata.get("Targets_species_name"),
            _extract_excerpt_field(excerpt, r"Organis<local_path_removed>"),
        )
        identifier = _first_non_empty(
            metadata.get("Sources_identifier"),
            metadata.get("interaction_id"),
            metadata.get("protein_id"),
            _extract_excerpt_field(excerpt, r"Interaction I<local_path_removed>"),
            _extract_excerpt_field(excerpt, r"Domain I<local_path_removed>"),
        )
        publication_date = _first_non_empty(
            metadata.get("Sources_publication_date"),
            _extract_excerpt_field(excerpt, r"Dat<local_path_removed>"),
        )
        evidence_table.append(
            {
                "row_index": index,
                "score": row.get("score"),
                "scaffold": scaffold,
                "target": target,
                "organism": organism,
                "source": row.get("source"),
                "identifier": identifier,
                "publication_date": publication_date,
                "owner_table": row.get("owner_table"),
            }
        )
    return evidence_table


def _profile_focus_scaffold(query: str, evidence_table: list[dict[str, Any]], runtime: dict[str, Any] | None = None) -> str | None:
    explicit = _extract_scaffold_terms(query, None, runtime)
    if explicit:
        return explicit[0]
    scaffold_counter = Counter(str(row.get("scaffold") or "").strip().lower() for row in evidence_table if row.get("scaffold"))
    if scaffold_counter:
        return scaffold_counter.most_common(1)[0][0]
    return None


def _format_profile_class_list(profile: dict[str, Any], language: str, limit: int = 6) -> str:
    items = [
        f"{item.get('scaffold')} ({item.get('count')})"
        for item in (profile.get("classes") or [])[:limit]
        if item.get("scaffold")
    ]
    if not items:
        return ""
    return "、".join(items) if language == "zh" else ", ".join(items)


def _derive_formal_summary(
    query: str,
    evidence_table: list[dict[str, Any]],
    source_registry_used: list[dict[str, Any]],
    language: str,
    runtime: dict[str, Any] | None = None,
) -> str | None:
    corpus_profile = _get_corpus_scaffold_profile(runtime)
    focus_scaffold = _profile_focus_scaffold(query, evidence_table, runtime)
    focus_profile = (corpus_profile.get("by_scaffold") or {}).get(str(focus_scaffold or "").lower())

    scaffold_counter = Counter(str(row.get("scaffold") or "").strip() for row in evidence_table if row.get("scaffold"))
    target_counter = Counter(str(row.get("target") or "").strip() for row in evidence_table if row.get("target"))
    source_counter = Counter(
        str(row.get("owner_table") or row.get("source") or "").strip()
        for row in evidence_table
        if row.get("owner_table") or row.get("source")
    )

    summary_parts: list[str] = []
    if language == "zh":
        if _mentions_all_scaffold_classes(query) and corpus_profile.get("class_count"):
            summary_parts.append(
                f"当前 FBBP 正式全量库覆盖 {corpus_profile['class_count']} 类 scaffold，主要包括 {_format_profile_class_list(corpus_profile, language)}。"
            )
        elif focus_profile:
            summary_parts.append(
                f"当前 FBBP 正式全量库中，{focus_profile['scaffold']} scaffold 相关 interaction 卡片共有 {focus_profile['count']} 条。"
            )
            if focus_profile.get("target_rows"):
                targets_text = "、".join(
                    f"{name} ({count})" for name, count in (focus_profile.get("top_targets") or [])[:5]
                )
                if targets_text:
                    summary_parts.append(
                        f"其中带显式 target 注释的记录有 {focus_profile['target_rows']} 条，当前可见代表性靶点包括 {targets_text}。"
                    )
        scaffold_text = _format_counter_items(scaffold_counter, language)
        target_text = _format_counter_items(target_counter, language)
        source_text = _format_counter_items(source_counter, language)
        if scaffold_text:
            summary_parts.append(f"当前命中的真实 FBBP 证据主要集中在 {scaffold_text} scaffold。")
        if target_text:
            summary_parts.append(f"高频出现的靶点包括 {target_text}。")
        if source_text:
            summary_parts.append(f"主要证据来源于 {source_text}。")
        if not summary_parts:
            return f"已为该问题检索到 {len(evidence_table)} 条真实证据。"
        return " ".join(summary_parts)

    if _mentions_all_scaffold_classes(query) and corpus_profile.get("class_count"):
        summary_parts.append(
            f"The full formal FBBP corpus currently covers {corpus_profile['class_count']} scaffold classes, led by {_format_profile_class_list(corpus_profile, language)}."
        )
    elif focus_profile:
        summary_parts.append(
            f"The full formal FBBP corpus contains {focus_profile['count']} interaction cards for the {focus_profile['scaffold']} scaffold."
        )
        if focus_profile.get("target_rows"):
            targets_text = ", ".join(
                f"{name} ({count})" for name, count in (focus_profile.get("top_targets") or [])[:5]
            )
            if targets_text:
                summary_parts.append(
                    f"{focus_profile['target_rows']} of those rows include explicit target annotations, with representative targets such as {targets_text}."
                )
    scaffold_text = _format_counter_items(scaffold_counter, language)
    target_text = _format_counter_items(target_counter, language)
    source_text = _format_counter_items(source_counter, language)
    if scaffold_text:
        summary_parts.append(f"Top grounded evidence is centered on {scaffold_text}.")
    if target_text:
        summary_parts.append(f"Most frequently surfaced targets are {target_text}.")
    if source_text:
        summary_parts.append(f"Representative evidence sources are {source_text}.")
    if not summary_parts:
        return f"Retrieved {len(evidence_table)} grounded evidence rows for {query}."
    return " ".join(summary_parts)


def _derive_key_findings(
    query: str,
    answer_text: str | None,
    evidence_table: list[dict[str, Any]],
    source_registry_used: list[dict[str, Any]],
    runtime: dict[str, Any] | None = None,
) -> list[str]:
    language = "zh" if _contains_cjk(query) else "en"
    corpus_profile = _get_corpus_scaffold_profile(runtime)
    focus_scaffold = _profile_focus_scaffold(query, evidence_table, runtime)
    focus_profile = (corpus_profile.get("by_scaffold") or {}).get(str(focus_scaffold or "").lower())
    scaffold_counter = Counter(str(row.get("scaffold") or "").strip() for row in evidence_table if row.get("scaffold"))
    target_counter = Counter(str(row.get("target") or "").strip() for row in evidence_table if row.get("target"))
    owner_counter = Counter(
        str(item.get("owner_table") or item.get("source") or "").strip()
        for item in source_registry_used
        if item.get("owner_table") or item.get("source")
    )
    findings: list[str] = []

    if _mentions_all_scaffold_classes(query) and corpus_profile.get("class_count"):
        if language == "zh":
            findings.append(
                f"正式全量库当前覆盖 {corpus_profile['class_count']} 类 scaffold，头部类别包括 {_format_profile_class_list(corpus_profile, language)}。"
            )
            representative_targets = []
            for item in (corpus_profile.get("classes") or [])[:6]:
                top_targets = item.get("top_targets") or []
                if top_targets:
                    representative_targets.append(f"{item.get('scaffold')}: {top_targets[0][0]} ({top_targets[0][1]})")
            if representative_targets:
                findings.append(f"按全量显式 target 注释看，代表性类别-靶点组合包括 {'；'.join(representative_targets[:5])}。")
        else:
            findings.append(
                f"The full formal corpus currently covers {corpus_profile['class_count']} scaffold classes, led by {_format_profile_class_list(corpus_profile, language)}."
            )
            representative_targets = []
            for item in (corpus_profile.get("classes") or [])[:6]:
                top_targets = item.get("top_targets") or []
                if top_targets:
                    representative_targets.append(f"{item.get('scaffold')}: {top_targets[0][0]} ({top_targets[0][1]})")
            if representative_targets:
                findings.append(
                    f"Representative class-target pairs from explicit annotations include {'; '.join(representative_targets[:5])}."
                )
    elif focus_profile:
        top_targets = focus_profile.get("top_targets") or []
        if top_targets:
            target_text = "、".join(f"{name} ({count})" for name, count in top_targets[:5]) if language == "zh" else ", ".join(
                f"{name} ({count})" for name, count in top_targets[:5]
            )
            findings.append(
                f"{focus_profile['scaffold']} scaffold 在全量库中最常见的显式 target 包括 {target_text}。"
                if language == "zh"
                else f"In the full corpus, the {focus_profile['scaffold']} scaffold most often maps to explicit targets such as {target_text}."
            )
        else:
            findings.append(
                f"{focus_profile['scaffold']} scaffold 在全量库中共有 {focus_profile['count']} 条 interaction 卡片，但显式 target 覆盖仍然有限。"
                if language == "zh"
                else f"The full corpus contains {focus_profile['count']} interaction cards for the {focus_profile['scaffold']} scaffold, but explicit target coverage is still sparse."
            )

    if scaffold_counter:
        scaffold_text = _format_counter_items(scaffold_counter, language)
        findings.append(
            f"Scaffold evidence is dominated by {scaffold_text}."
            if language == "en"
            else f"Scaffold 证据主要由 {scaffold_text} 构成。"
        )
    if target_counter:
        target_text = _format_counter_items(target_counter, language)
        findings.append(
            f"Target-focused evidence repeatedly surfaced {target_text}."
            if language == "en"
            else f"与靶点相关的证据反复指向 {target_text}。"
        )
    if owner_counter:
        owner_text = _format_counter_items(owner_counter, language)
        findings.append(
            f"Cross-table evidence came from {owner_text}."
            if language == "en"
            else f"跨表证据主要来自 {owner_text}。"
        )
    if answer_text and not findings:
        summary_line = answer_text.splitlines()[0].strip()
        if summary_line:
            findings.append(summary_line)

    if not findings:
        for row in evidence_table[:3]:
            source = row.get("source") or "unknown source"
            scaffold = row.get("scaffold") or "unspecified scaffold"
            findings.append(f"{source} surfaced evidence for {scaffold}.")
    return findings[:5]


def _derive_known_unknowns(
    limitations: list[str],
    provenance_caveats: list[str],
    evidence_table: list[dict[str, Any]],
) -> list[str]:
    unknowns: list[str] = list(limitations)
    if not any(row.get("target") for row in evidence_table):
        unknowns.append("No explicit target entity was resolved from the retrieved evidence rows.")
    if not any(row.get("organism") for row in evidence_table):
        unknowns.append("No organism field was resolved from the retrieved evidence rows.")
    if not any(row.get("publication_date") for row in evidence_table):
        unknowns.append("No publication date surfaced in the current top evidence rows.")
    unknowns.extend(provenance_caveats)
    return list(dict.fromkeys(item for item in unknowns if item))


def _build_structured_output(result: dict[str, Any], runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    enriched_rows = [_enrich_source_row(row, runtime) for row in result.get("results") or []]
    answer_text = _answer_text(result.get("answer"))
    query = str(result.get("query") or "")

    limitations: list[str] = []
    if result.get("answer_generation_failed"):
        limitations.append("Answer generation failed; formal result is retrieval-only.")
    if not answer_text and not result.get("formal_synthesized"):
        limitations.append("No grounded answer text was returned by the knowledge layer.")
    if not enriched_rows:
        limitations.append("No retrieval evidence rows were returned.")

    provenance_caveats: list[str] = []
    if any(row.get("registry_status") != "registered" for row in enriched_rows):
        provenance_caveats.append("Some evidence rows are not yet covered by the formal source registry.")

    evidence_rows = [
        {
            "source": row.get("source"),
            "chunk_id": row.get("chunk_id"),
            "score": row.get("score"),
            "excerpt": row.get("excerpt"),
            "metadata": row.get("metadata") or {},
            "source_category": row.get("source_category"),
            "source_description": row.get("source_description"),
            "upstream_pipeline": row.get("upstream_pipeline"),
            "quality_notes": row.get("quality_notes"),
            "owner_table": row.get("owner_table"),
        }
        for row in enriched_rows[:10]
    ]
    evidence_table = _derive_evidence_table(enriched_rows)
    source_registry_used = _source_registry_used(enriched_rows)
    language = "zh" if _contains_cjk(query or answer_text or "") else "en"
    corpus_profile = _get_corpus_scaffold_profile(runtime)
    summary = answer_text or _derive_formal_summary(query, evidence_table, source_registry_used, language, runtime)
    claims: list[dict[str, Any]] = []
    if summary:
        claims.append(
            {
                "claim_id": "claim_1",
                "text": summary,
                "support": "retrieved_evidence",
                "evidence_count": len(enriched_rows),
            }
        )
    key_findings = _derive_key_findings(query, answer_text, evidence_table, source_registry_used, runtime)
    known_unknowns = _derive_known_unknowns(limitations, provenance_caveats, evidence_table)
    return {
        "summary": summary,
        "claims": claims,
        "key_findings": key_findings,
        "known_unknowns": known_unknowns,
        "evidence_rows": evidence_rows,
        "evidence_table": evidence_table,
        "source_registry_used": source_registry_used,
        "dataset_profile": corpus_profile,
        "limitations": limitations,
        "provenance_caveats": provenance_caveats,
    }


def _enrich_search_result(result: dict[str, Any], runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    enriched = dict(result or {})
    enriched["results"] = [_enrich_source_row(row, runtime) for row in enriched.get("results") or []]
    enriched["answer_text"] = _answer_text(enriched.get("answer"))
    enriched["structured_output"] = _build_structured_output(enriched, runtime)
    return enriched


def _render_formal_answer_text(query: str, structured_output: dict[str, Any]) -> str:
    language = "zh" if _contains_cjk(query) else "en"
    lines: list[str] = []
    summary = _first_non_empty(structured_output.get("summary"))
    key_findings = [str(item).strip() for item in structured_output.get("key_findings") or [] if str(item).strip()]
    known_unknowns = [
        str(item).strip() for item in structured_output.get("known_unknowns") or [] if str(item).strip()
    ]
    source_registry_used = structured_output.get("source_registry_used") or []
    evidence_table = structured_output.get("evidence_table") or []

    if language == "zh":
        lines.append("摘要")
        lines.append(summary or "当前没有足够的正式证据可生成摘要。")
        if key_findings:
            lines.extend(["", "关键发现"])
            lines.extend([f"- {item}" for item in key_findings[:5]])
        if known_unknowns:
            lines.extend(["", "已知缺口"])
            lines.extend([f"- {item}" for item in known_unknowns[:5]])
        if source_registry_used:
            lines.extend(["", "来源登记"])
            for item in source_registry_used[:5]:
                source_name = item.get("owner_table") or item.get("source") or "unknown"
                description = item.get("source_description") or item.get("source_category") or ""
                lines.append(f"- {source_name}: {description}".rstrip(": "))
    else:
        lines.append("Summary")
        lines.append(summary or "No grounded formal summary is currently available.")
        if key_findings:
            lines.extend(["", "Key findings"])
            lines.extend([f"- {item}" for item in key_findings[:5]])
        if known_unknowns:
            lines.extend(["", "Known unknowns"])
            lines.extend([f"- {item}" for item in known_unknowns[:5]])
        if source_registry_used:
            lines.extend(["", "Source registry used"])
            for item in source_registry_used[:5]:
                source_name = item.get("owner_table") or item.get("source") or "unknown"
                description = item.get("source_description") or item.get("source_category") or ""
                lines.append(f"- {source_name}: {description}".rstrip(": "))

    if evidence_table:
        lines.extend(
            [
                "",
                "Evidence table" if language == "en" else "证据表",
                "| # | Score | Scaffold | Target | Organism | Source | Identifier | Date |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for row in evidence_table[:5]:
            score = row.get("score")
            rendered_score = f"{float(score):.3f}" if isinstance(score, (int, float)) else ""
            lines.append(
                f"| {row.get('row_index', '')} | {rendered_score} | {row.get('scaffold') or ''} | "
                f"{row.get('target') or ''} | {row.get('organism') or ''} | {row.get('source') or ''} | "
                f"{row.get('identifier') or ''} | {row.get('publication_date') or ''} |"
            )

    return "\n".join(lines).strip()


def server_status() -> dict[str, Any]:
    request: dict[str, Any] = {}
    runtime = _formal_runtime()
    return _tool_call(
        tool="server_status",
        request=request,
        runner=lambda: {**_run_db_worker("server_status"), **_runtime_provenance(runtime)},
        diagnostics={"worker_action": "server_status"},
    )


def health_status() -> dict[str, Any]:
    request: dict[str, Any] = {}
    repo_root = _repo_src_path().parent
    return _tool_call(
        tool="health_status",
        request=request,
        runner=lambda: build_health_snapshot(
            repo_root=repo_root,
            db_probe=lambda: _run_db_worker("server_status").get("db_probe", {"ok": False}),
            public_probe=lambda: {
                "pubmed": {"ok": True, "status": "configured"},
                "uniprot": {"ok": True, "status": "configured"},
                "pdb": {"ok": True, "status": "configured"},
            },
            ragkb_status=ensure_ragkb_importable(),
            formal_runtime=_formal_runtime(),
        ),
    )


def tool_contract_version() -> dict[str, Any]:
    return build_tool_response(
        tool="tool_contract_version",
        request={},
        result={"contract_version": CONTRACT_VERSION},
        diagnostics={},
    )


def list_available_sources(record_type: str | None = None, limit: int = 100) -> dict[str, Any]:
    request = {"record_type": record_type, "limit": limit}
    runtime = _formal_runtime()
    return _tool_call(
        tool="list_sources",
        request=request,
        runner=lambda: _enrich_source_listing_result(_run_db_worker("list_sources", request), runtime),
        provenance={"record_type": record_type, **_runtime_provenance(runtime)},
        diagnostics={"worker_action": "list_sources"},
    )


def list_record_types(limit: int = 1000) -> dict[str, Any]:
    request = {"limit": limit}
    runtime = _formal_runtime()
    return _tool_call(
        tool="list_record_types",
        request=request,
        runner=lambda: _run_db_worker("list_record_types", request),
        provenance=_runtime_provenance(runtime),
        diagnostics={"worker_action": "list_record_types"},
    )


def get_source_summary(source: str, limit: int = 1000) -> dict[str, Any]:
    request = {"source": source, "limit": limit}
    runtime = _formal_runtime()
    return _tool_call(
        tool="get_source_summary",
        request=request,
        runner=lambda: _enrich_source_listing_result(_run_db_worker("get_source_summary", request), runtime),
        provenance={"source": source, **_runtime_provenance(runtime)},
        diagnostics={"worker_action": "get_source_summary"},
    )


def get_document_chunk_by_id(source: str, chunk_id: str) -> dict[str, Any]:
    request = {"source": source, "chunk_id": chunk_id}
    runtime = _formal_runtime()
    return _tool_call(
        tool="get_document_chunk",
        request=request,
        runner=lambda: _run_db_worker("get_document_chunk", request),
        provenance={"source": source, "chunk_id": chunk_id, **_runtime_provenance(runtime)},
        diagnostics={"worker_action": "get_document_chunk"},
    )


def search_knowledge_via_formal_http_gateway(
    query: str,
    top_k: int | None = None,
    record_type: str | None = None,
    filters: list[str] | None = None,
    include_answer: bool = True,
    include_evidence: bool = False,
    answer_mode: str | None = None,
) -> dict[str, Any]:
    effective_answer_mode = _effective_answer_mode(answer_mode, include_answer)
    request = {
        "query": query,
        "top_k": top_k or _default_top_k(),
        "record_type": record_type,
        "filters": filters or [],
        "include_answer": include_answer,
        "include_evidence": include_evidence,
        "answer_mode": effective_answer_mode,
    }
    cache_key = json.dumps({"mode": "formal_http_gateway", **request}, ensure_ascii=False, sort_keys=True)
    cached = _FORMAL_GATEWAY_SEARCH_CACHE.get(cache_key)
    if cached and (time.time() - cached[0]) < _search_cache_ttl_seconds():
        return cached[1]

    gateway_url = _formal_query_gateway_url()
    gateway_request = {
        "query": request["query"],
        "topK": request["top_k"],
        "recordType": request["record_type"],
        "filters": request["filters"],
        "includeAnswer": request["include_answer"],
        "includeEvidence": request["include_evidence"],
        "answerMode": effective_answer_mode,
    }

    try:
        encoded = json.dumps(gateway_request, ensure_ascii=False).encode("utf-8")
        http_request = urllib_request.Request(
            gateway_url,
            data=encoded,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(http_request, timeout=_formal_query_gateway_timeout_seconds()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        error_message = f"Formal query gateway returned HTTP {exc.code}"
        if details:
            error_message = f"{error_message}: {details}"
        return build_error_response(
            tool="search_knowledge",
            request=request,
            diagnostics={"query_transport": "formal_http_gateway", "gateway_url": gateway_url},
            error={"code": "FORMAL_QUERY_GATEWAY_ERROR", "message": error_message, "details": {}},
        )
    except Exception as exc:
        return build_error_response(
            tool="search_knowledge",
            request=request,
            diagnostics={"query_transport": "formal_http_gateway", "gateway_url": gateway_url},
            error={"code": "FORMAL_QUERY_GATEWAY_ERROR", "message": str(exc), "details": {}},
        )

    if not isinstance(payload, dict):
        return build_error_response(
            tool="search_knowledge",
            request=request,
            diagnostics={"query_transport": "formal_http_gateway", "gateway_url": gateway_url},
            error={
                "code": "FORMAL_QUERY_GATEWAY_ERROR",
                "message": "Formal query gateway returned a non-object payload.",
                "details": {},
            },
        )

    response = dict(payload)
    response.setdefault("tool", "search_knowledge")
    response.setdefault("contract_version", CONTRACT_VERSION)
    response.setdefault("request", request)
    response.setdefault("result", {})

    diagnostics = dict(response.get("diagnostics") or {})
    backend_transport = diagnostics.get("query_transport")
    diagnostics["query_transport"] = "formal_http_gateway"
    diagnostics["gateway_url"] = gateway_url
    if backend_transport:
        diagnostics["gateway_backend_transport"] = backend_transport
    response["diagnostics"] = diagnostics

    if response.get("ok"):
        _FORMAL_GATEWAY_SEARCH_CACHE[cache_key] = (time.time(), response)
    return response


def search_knowledge(
    query: str,
    top_k: int | None = None,
    record_type: str | None = None,
    filters: list[str] | None = None,
    include_answer: bool = True,
    include_evidence: bool = False,
    answer_mode: str | None = None,
) -> dict[str, Any]:
    effective_answer_mode = _effective_answer_mode(answer_mode, include_answer)
    request = {
        "query": query,
        "top_k": top_k or _default_top_k(),
        "record_type": record_type,
        "filters": filters or [],
        "include_answer": include_answer,
        "include_evidence": include_evidence,
        "answer_mode": effective_answer_mode,
    }
    cache_key = json.dumps(request, ensure_ascii=False, sort_keys=True)
    cached = _SEARCH_CACHE.get(cache_key)
    if cached and (time.time() - cached[0]) < _search_cache_ttl_seconds():
        return cached[1]
    runtime = _formal_runtime()
    query_plan = _build_formal_query_plan(
        query=query,
        top_k=request["top_k"],
        record_type=record_type,
        filters=filters,
        runtime=runtime,
    )

    if include_answer and effective_answer_mode == "formal":
        def run_formal_fusion() -> dict[str, Any]:
            merged_results, fusion_errors = _merge_formal_query_results(query_plan, runtime, request["top_k"])
            if not merged_results and fusion_errors:
                raise RuntimeError(fusion_errors[0]["message"])
            raw_result = {
                "query": query,
                "record_type": record_type,
                "result_count": len(merged_results),
                "results": merged_results,
                "answer": None,
                "formal_synthesized": True,
            }
            enriched = _enrich_search_result(raw_result, runtime)
            if fusion_errors:
                known_unknowns = enriched["structured_output"].setdefault("known_unknowns", [])
                for fusion_error in fusion_errors:
                    message = (
                        f"Formal retrieval pass '{fusion_error['label']}' failed: {fusion_error['message']}"
                    )
                    if message not in known_unknowns:
                        known_unknowns.append(message)
            formal_answer = _render_formal_answer_text(query, enriched["structured_output"])
            enriched["answer"] = formal_answer
            enriched["answer_text"] = formal_answer
            return enriched

        response = _tool_call(
            tool="search_knowledge",
            request=request,
            runner=run_formal_fusion,
            provenance={
                "record_type": record_type,
                "filter_summary": filters or [],
                "answer_mode": effective_answer_mode,
                **_runtime_provenance(runtime),
            },
            diagnostics={
                "worker_action": "search_knowledge",
                "cache_enabled": True,
                "answer_mode": effective_answer_mode,
                "retrieval_strategy": "multi_query_fusion",
                "query_plan": [
                    {
                        "label": plan["label"],
                        "query": plan["query"],
                        "filters": plan["filters"],
                    }
                    for plan in query_plan
                ],
            },
        )
        if response.get("ok"):
            response["provenance"] = {
                **response.get("provenance", {}),
                "retrieval_count": response["result"].get("result_count", 0),
                "sources": _result_sources(response["result"]),
            }
            _SEARCH_CACHE[cache_key] = (time.time(), response)
        return response

    response = _tool_call(
        tool="search_knowledge",
        request=request,
        runner=lambda: _enrich_search_result(_run_db_worker("search_knowledge", request), runtime),
        provenance={
            "record_type": record_type,
            "filter_summary": filters or [],
            "answer_mode": effective_answer_mode,
            **_runtime_provenance(runtime),
        },
        diagnostics={"worker_action": "search_knowledge", "cache_enabled": True},
    )
    if not response.get("ok") and include_answer:
        fallback_request = {
            **request,
            "include_answer": False,
        }
        fallback_response = _tool_call(
            tool="search_knowledge",
            request=fallback_request,
            runner=lambda: _enrich_search_result(_run_db_worker("search_knowledge", fallback_request), runtime),
            provenance={
                "record_type": record_type,
                "filter_summary": filters or [],
                "answer_mode": effective_answer_mode,
                **_runtime_provenance(runtime),
            },
            diagnostics={
                "worker_action": "search_knowledge",
                "cache_enabled": True,
                "fallback_mode": "retrieval_only",
                "answer_generation_error": (response.get("error") or {}).get("message"),
            },
        )
        if fallback_response.get("ok"):
            response = fallback_response
            response.setdefault("result", {})["answer_generation_failed"] = True
            response["result"]["answer"] = None
            response["result"] = _enrich_search_result(response["result"], runtime)
    if response.get("ok"):
        response["provenance"] = {
            **response.get("provenance", {}),
            "retrieval_count": response["result"].get("result_count", 0),
            "sources": _result_sources(response["result"]),
        }
    if response.get("ok"):
        _SEARCH_CACHE[cache_key] = (time.time(), response)
    return response


def explain_search(
    query: str,
    top_k: int | None = None,
    record_type: str | None = None,
    filters: list[str] | None = None,
    answer_mode: str | None = None,
) -> dict[str, Any]:
    request = {
        "query": query,
        "top_k": top_k or _default_top_k(),
        "record_type": record_type,
        "filters": filters or [],
        "answer_mode": answer_mode or _default_answer_mode(),
    }
    runtime = _formal_runtime()
    return _tool_call(
        tool="explain_search",
        request=request,
        runner=lambda: _run_db_worker("explain_search", request),
        provenance={
            "record_type": record_type,
            "filter_summary": filters or [],
            "answer_mode": request["answer_mode"],
            **_runtime_provenance(runtime),
        },
        diagnostics={"worker_action": "explain_search"},
    )


def preview_ingest(input_path: str) -> dict[str, Any]:
    path = Path(input_path)
    request = {"input_path": str(path)}
    if not path.exists():
        return build_error_response(
            tool="preview_ingest",
            request=request,
            error={"code": "INGEST_INPUT_ERROR", "message": "Input path does not exist", "details": {}},
        )

    file_paths = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
    suffixes = sorted({item.suffix.lower() or "<none>" for item in file_paths})
    total_bytes = sum(item.stat().st_size for item in file_paths)
    return build_tool_response(
        tool="preview_ingest",
        request=request,
        result={
            "exists": True,
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "file_count": len(file_paths),
            "suffixes": suffixes,
            "total_bytes": total_bytes,
        },
        provenance={"input_path": str(path), **_runtime_provenance()},
    )


def ingest_sources_into_knowledge(
    input_path: str,
    limit: int | None = None,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    batch_size: int = 64,
) -> dict[str, Any]:
    path = Path(input_path)
    if not path.exists():
        return build_error_response(
            tool="ingest_sources",
            request={
                "input_path": str(path),
                "limit": limit,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "batch_size": batch_size,
            },
            error={"code": "INGEST_INPUT_ERROR", "message": "Input path does not exist", "details": {}},
        )

    request = {
        "input_path": str(path),
        "limit": limit,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "batch_size": batch_size,
    }
    return _tool_call(
        tool="ingest_sources",
        request=request,
        runner=lambda: _run_db_worker("ingest_sources", request),
        provenance={"input_path": str(path), **_runtime_provenance()},
        diagnostics={"worker_action": "ingest_sources"},
    )


def search_pubmed_articles(query: str, retmax: int = 5) -> dict[str, Any]:
    request = {"query": query, "retmax": retmax}
    return _tool_call(
        tool="search_pubmed",
        request=request,
        runner=lambda: run_search_pubmed(query=query, retmax=retmax),
        provenance={"provider": "pubmed", "query": query},
    )


def get_uniprot_entry(accession: str) -> dict[str, Any]:
    request = {"accession": accession}
    return _tool_call(
        tool="get_uniprot_entry",
        request=request,
        runner=lambda: fetch_uniprot_entry(accession=accession),
        provenance={"provider": "uniprot", "identifier": accession},
    )


def get_pdb_entry(pdb_id: str) -> dict[str, Any]:
    request = {"pdb_id": pdb_id}
    return _tool_call(
        tool="get_pdb_entry",
        request=request,
        runner=lambda: fetch_pdb_entry(pdb_id=pdb_id),
        provenance={"provider": "pdb", "identifier": pdb_id},
    )
