from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


DEFAULT_TIMEOUT = 20
USER_AGENT = "fbbp-mcp-rag-server/0.1"
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_LAST_CALL_AT: dict[str, float] = {}


def _cache_ttl_seconds() -> float:
    return float(os.getenv("FBBP_SCI_CACHE_TTL_SECONDS", os.getenv("FBTP_SCI_CACHE_TTL_SECONDS", "300")))


def _retry_attempts() -> int:
    return int(os.getenv("FBBP_SCI_RETRY_ATTEMPTS", os.getenv("FBTP_SCI_RETRY_ATTEMPTS", "3")))


def _retry_backoff_seconds() -> float:
    return float(
        os.getenv("FBBP_SCI_RETRY_BACKOFF_SECONDS", os.getenv("FBTP_SCI_RETRY_BACKOFF_SECONDS", "0.75"))
    )


def _min_interval_seconds() -> float:
    return float(os.getenv("FBBP_SCI_MIN_INTERVAL_SECONDS", os.getenv("FBTP_SCI_MIN_INTERVAL_SECONDS", "0.25")))


def _throttle(key: str) -> None:
    min_interval = _min_interval_seconds()
    if min_interval <= 0:
        return
    now = time.monotonic()
    last = _LAST_CALL_AT.get(key)
    if last is not None:
        remaining = min_interval - (now - last)
        if remaining > 0:
            time.sleep(remaining)
    _LAST_CALL_AT[key] = time.monotonic()


def _get_json(url: str) -> dict[str, Any]:
    cached = _CACHE.get(url)
    if cached and (time.time() - cached[0]) < _cache_ttl_seconds():
        return cached[1]

    request = Request(url, headers={"User-Agent": USER_AGENT})
    last_exc: Exception | None = None
    for attempt in range(_retry_attempts()):
        try:
            _throttle(url)
            with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
                _CACHE[url] = (time.time(), payload)
                return payload
        except HTTPError as exc:
            last_exc = exc
            if exc.code not in {429, 500, 502, 503, 504}:
                raise
        except (TimeoutError, URLError) as exc:
            last_exc = exc

        if attempt < _retry_attempts() - 1:
            time.sleep(_retry_backoff_seconds() * (attempt + 1))

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Scientific lookup failed without an error")


def parse_pubmed_summary(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result", {})
    uids = result.get("uids", []) or []
    articles = []
    for uid in uids:
        row = result.get(uid, {})
        authors = [item.get("name", "") for item in row.get("authors", []) if item.get("name")]
        articles.append(
            {
                "pmid": row.get("uid", uid),
                "title": row.get("title", ""),
                "pubdate": row.get("pubdate", ""),
                "journal": row.get("fulljournalname", ""),
                "authors": authors,
            }
        )
    return {"count": len(articles), "articles": articles}


def parse_uniprot_entry(payload: dict[str, Any]) -> dict[str, Any]:
    protein_description = payload.get("proteinDescription", {})
    recommended_name = protein_description.get("recommendedName", {})
    full_name = recommended_name.get("fullName", {})
    genes = payload.get("genes", []) or []
    first_gene = genes[0].get("geneName", {}).get("value", "") if genes else ""
    sequence = payload.get("sequence", {}) or {}
    organism = payload.get("organism", {}) or {}
    return {
        "accession": payload.get("primaryAccession", ""),
        "entry_name": payload.get("uniProtkbId", ""),
        "protein_name": full_name.get("value", ""),
        "organism": organism.get("scientificName", ""),
        "gene": first_gene,
        "sequence_length": sequence.get("length"),
    }


def parse_pdb_entry(payload: dict[str, Any]) -> dict[str, Any]:
    exptl = payload.get("exptl", []) or []
    methods = [item.get("method", "") for item in exptl if item.get("method")]
    entry_info = payload.get("rcsb_entry_info", {}) or {}
    accession = payload.get("rcsb_accession_info", {}) or {}
    resolutions = entry_info.get("resolution_combined", []) or []
    resolution = resolutions[0] if resolutions else None
    return {
        "pdb_id": payload.get("rcsb_id", ""),
        "title": payload.get("struct", {}).get("title", ""),
        "methods": methods,
        "resolution": resolution,
        "release_date": accession.get("initial_release_date", ""),
    }


def search_pubmed(query: str, retmax: int = 5) -> dict[str, Any]:
    params = urlencode({"db": "pubmed", "retmode": "json", "term": query, "retmax": retmax})
    search_payload = _get_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}")
    ids = search_payload.get("esearchresult", {}).get("idlist", []) or []
    if not ids:
        return {"query": query, "count": 0, "articles": []}
    summary_params = urlencode({"db": "pubmed", "retmode": "json", "id": ",".join(ids)})
    summary_payload = _get_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{summary_params}")
    parsed = parse_pubmed_summary(summary_payload)
    parsed["query"] = query
    return parsed


def get_uniprot_entry(accession: str) -> dict[str, Any]:
    payload = _get_json(f"https://rest.uniprot.org/uniprotkb/{accession}.json")
    result = parse_uniprot_entry(payload)
    result["query"] = accession
    return result


def get_pdb_entry(pdb_id: str) -> dict[str, Any]:
    payload = _get_json(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}")
    result = parse_pdb_entry(payload)
    result["query"] = pdb_id
    return result
