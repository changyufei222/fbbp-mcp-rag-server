from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
OUTPUT_ROOT = REPO_ROOT / "reports" / "final_release" / "latest"
LIVE_ACCEPTANCE_JSON = OUTPUT_ROOT / "live_client_acceptance.json"
LIVE_ACCEPTANCE_MD = OUTPUT_ROOT / "live_client_acceptance.md"
EXPECTED_TOOLS = {
    "server_status",
    "health_status",
    "tool_contract_version",
    "list_sources",
    "list_record_types",
    "get_source_summary",
    "get_document_chunk",
    "search_knowledge",
    "explain_search",
    "preview_ingest",
    "ingest_sources",
    "search_pubmed",
    "get_uniprot_entry",
    "get_pdb_entry",
}
CLIENT_CONFIGS = {
    "codex": REPO_ROOT / "examples" / "clients" / "codex.config.toml",
    "claude_code": REPO_ROOT / "examples" / "clients" / "claude-code.mcp.json",
    "cursor": REPO_ROOT / "examples" / "clients" / "cursor.mcp.json",
    "deerflow": REPO_ROOT / "examples" / "extensions_config.deerflow.json",
}
CLIENT_METADATA = {
    "codex": {
        "label": "Codex",
        "transport": "http",
        "auth_shape": "inherits Codex env / MCP server URL settings",
        "smoke_command": "load examples/clients/codex.config.toml and call tool_contract_version",
    },
    "claude_code": {
        "label": "Claude Code",
        "transport": "http",
        "auth_shape": "inherits wrapper env / MCP server URL settings",
        "smoke_command": "load examples/clients/claude-code.mcp.json and call server_status",
    },
    "cursor": {
        "label": "Cursor",
        "transport": "http",
        "auth_shape": "inherits local MCP host env",
        "smoke_command": "import examples/clients/cursor.mcp.json and call health_status",
    },
    "deerflow": {
        "label": "DeerFlow",
        "transport": "stdio",
        "auth_shape": "server-side env block in the extension config",
        "smoke_command": "load examples/extensions_config.deerflow.json and run search_knowledge",
    },
}


def _check(name: str, ok: bool, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "details": details or {}}


def _run_python(code: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    env = dict(**{k: v for k, v in dict().items()})
    proc_env = None
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        f"repo_root = Path(r'{REPO_ROOT}')\n"
        "sys.path = [str(repo_root / '.venv' / 'Lib' / 'site-packages'), str(repo_root / 'src')] + list(sys.path)\n"
        + code
    )
    return subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout, check=False, env=proc_env)


def check_tool_registration() -> dict[str, Any]:
    proc = _run_python(
        "import json\n"
        "import fbbp_mcp_server.server as mcp_server\n"
        "print(json.dumps(sorted(mcp_server.mcp._tool_manager._tools.keys())))\n",
        timeout=90,
    )
    tools: list[str] = []
    if proc.returncode == 0:
        try:
            tools = json.loads(proc.stdout.strip())
        except Exception:
            tools = []
    missing = sorted(EXPECTED_TOOLS - set(tools))
    return _check(
        "tool_registration",
        proc.returncode == 0 and not missing,
        details={"registered_count": len(tools), "missing": missing, "stderr_tail": proc.stderr.strip().splitlines()[-5:]},
    )


def check_client_matrix() -> dict[str, Any]:
    matrix: dict[str, Any] = {}
    ok = True
    for client, path in CLIENT_CONFIGS.items():
        meta = CLIENT_METADATA.get(client, {})
        exists = path.exists()
        text = path.read_text(encoding="utf-8", errors="ignore") if exists else ""
        has_fbbp = "fbbp-rag" in text or "fbbp-mcp-rag-server" in text or "/fbbp" in text
        legacy_upper = "FBTP" in text
        transport = str(meta.get("transport") or "")
        if transport == "http":
            has_transport_hint = "http://127.0.0.1:8000/mcp" in text or '"type": "http"' in text or '"url"' in text
        elif transport == "stdio":
            has_transport_hint = '"type": "stdio"' in text or "command" in text
        else:
            has_transport_hint = bool(transport) and transport in text
        matrix[client] = {
            "label": meta.get("label", client),
            "path": str(path),
            "exists": exists,
            "transport": meta.get("transport"),
            "auth_shape": meta.get("auth_shape"),
            "smoke_command": meta.get("smoke_command"),
            "has_fbbp_reference": has_fbbp,
            "has_transport_hint": has_transport_hint,
            "uppercase_fbtp_found": legacy_upper,
        }
        ok = ok and exists and has_fbbp and has_transport_hint and not legacy_upper
    return _check("multi_client_config_matrix", ok, details=matrix)


def check_contract_docs() -> dict[str, Any]:
    docs = {
        "formal_tool_contract": REPO_ROOT / "docs" / "formal_tool_contract.md",
        "api_reference": REPO_ROOT / "docs" / "mcp_tool_api_reference.md",
    }
    details = {}
    ok = True
    for name, path in docs.items():
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        has_all = all(tool in text for tool in ["search_knowledge", "list_sources", "search_pubmed", "get_uniprot_entry", "get_pdb_entry"])
        details[name] = {"path": str(path), "exists": path.exists(), "has_core_tools": has_all}
        ok = ok and path.exists() and has_all
    return _check("tool_contract_documentation", ok, details=details)


def check_ops_docs() -> dict[str, Any]:
    docs = {
        "client_acceptance_matrix": REPO_ROOT / "docs" / "client_acceptance_matrix.md",
        "production_service_runbook": REPO_ROOT / "docs" / "production_service_runbook.md",
    }
    required_markers = {
        "client_acceptance_matrix": ["Codex", "Claude Code", "Cursor", "DeerFlow", "streamable-http", "smoke"],
        "production_service_runbook": ["Docker Compose", "systemd", "health", "rate limit", "auth", "reverse proxy"],
    }
    details = {}
    ok = True
    for name, path in docs.items():
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing = [marker for marker in required_markers[name] if marker not in text]
        details[name] = {"path": str(path), "exists": path.exists(), "missing": missing}
        ok = ok and path.exists() and not missing
    return _check("service_ops_documentation", ok, details=details)


def check_live_client_acceptance() -> dict[str, Any]:
    payload = {}
    if LIVE_ACCEPTANCE_JSON.exists():
        try:
            payload = json.loads(LIVE_ACCEPTANCE_JSON.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    clients = payload.get("clients") if isinstance(payload.get("clients"), list) else []
    client_labels = {str(item.get("label") or "") for item in clients if isinstance(item, dict)}
    required_labels = {"Codex", "Claude Code", "Cursor", "DeerFlow"}
    missing_labels = sorted(required_labels - client_labels)
    all_live_ok = bool(clients) and all(bool(item.get("ok")) for item in clients if isinstance(item, dict))
    ok = LIVE_ACCEPTANCE_JSON.exists() and LIVE_ACCEPTANCE_MD.exists() and not missing_labels and all_live_ok
    return _check(
        "live_client_acceptance",
        ok,
        details={
            "json_path": str(LIVE_ACCEPTANCE_JSON),
            "md_path": str(LIVE_ACCEPTANCE_MD),
            "client_count": len(clients),
            "missing_labels": missing_labels,
            "client_labels": sorted(client_labels),
        },
    )


def check_deployment_assets(require_docker_live: bool = False) -> dict[str, Any]:
    files = {
        "dockerfile": REPO_ROOT / "Dockerfile",
        "compose": REPO_ROOT / "docker-compose.yml",
        "production_env": REPO_ROOT / "configs" / "production.example.env",
        "systemd": REPO_ROOT / "configs" / "fbbp-mcp-rag-server.service.example",
    }
    missing = {name: str(path) for name, path in files.items() if not path.exists()}
    docker_live = {"required": require_docker_live, "checked": False, "ok": not require_docker_live}
    docker = shutil.which("docker")
    if docker:
        proc = subprocess.run([docker, "compose", "config"], cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=120)
        docker_live = {
            "required": require_docker_live,
            "checked": True,
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr.strip().splitlines()[-5:],
        }
    return _check(
        "deployment_assets",
        not missing and bool(docker_live["ok"]),
        details={"missing": missing, "docker_live": docker_live},
    )


def check_response_contract() -> dict[str, Any]:
    proc = _run_python(
        "import json\n"
        "from fbbp_mcp_server.schemas import CONTRACT_VERSION, build_tool_response, build_error_response\n"
        "ok = build_tool_response(tool='x', request={'a': 1}, result={'b': 2})\n"
        "err = build_error_response(tool='x', error={'code': 'INVALID_REQUEST', 'message': 'bad', 'details': {}})\n"
        "print(json.dumps({'version': CONTRACT_VERSION, 'ok_keys': sorted(ok), 'err_ok': err['ok'], 'err_code': err['error']['code']}))\n",
    )
    payload = {}
    if proc.returncode == 0:
        try:
            payload = json.loads(proc.stdout.strip())
        except Exception:
            payload = {}
    expected_keys = sorted(["ok", "tool", "contract_version", "request", "result", "provenance", "diagnostics", "error"])
    return _check(
        "response_contract_shape",
        proc.returncode == 0 and payload.get("version") == "1.1" and payload.get("ok_keys") == expected_keys and payload.get("err_code") == "INVALID_REQUEST",
        details=payload | {"stderr_tail": proc.stderr.strip().splitlines()[-5:]},
    )


def check_public_naming() -> dict[str, Any]:
    paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "formal_tool_contract.md",
        REPO_ROOT / "docs" / "mcp_tool_api_reference.md",
        REPO_ROOT / "docs" / "client_acceptance_matrix.md",
        REPO_ROOT / "docs" / "production_service_runbook.md",
    ]
    hits = []
    for path in paths:
        if not path.exists():
            continue
        for idx, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            if "FBTP" in line:
                hits.append(f"{path}:{idx}:{line.strip()}")
    return _check("fbbp_public_naming", not hits, details={"uppercase_fbtp_hits": hits})


def write_client_acceptance_artifacts(checks: list[dict[str, Any]], output_root: Path) -> dict[str, str]:
    client_details = next((item.get("details") for item in checks if item.get("name") == "multi_client_config_matrix"), {}) or {}
    json_payload = {
        "schema_version": "fbbp.mcp.client_acceptance.v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "clients": client_details,
        "notes": "This report validates config presence, FBBP naming, transport hints, and the recommended smoke command per client. Live GUI acceptance remains environment-dependent.",
    }
    json_path = output_root / "client_acceptance_matrix.json"
    md_path = output_root / "client_acceptance_matrix.md"
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# FBBP MCP Client Acceptance Matrix",
        "",
        "| Client | Transport | Config Ready | FBBP Naming | Smoke Command |",
        "|---|---|---|---|---|",
    ]
    for key, item in client_details.items():
        lines.append(
            f"| {item.get('label', key)} | {item.get('transport', 'n/a')} | {'yes' if item.get('exists') else 'no'} | {'yes' if item.get('has_fbbp_reference') and not item.get('uppercase_fbtp_found') else 'no'} | {item.get('smoke_command', 'n/a')} |"
        )
    lines.extend(
        [
            "",
            "Live UI verification is intentionally separated from this matrix because Codex, Claude Code, Cursor, and DeerFlow may be attached to different local runtimes even when the config layer is ready.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"client_acceptance_json": str(json_path), "client_acceptance_md": str(md_path)}


def write_summary(checks: list[dict[str, Any]], output_root: Path = OUTPUT_ROOT) -> dict[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    client_outputs = write_client_acceptance_artifacts(checks, output_root)
    summary = {
        "schema_version": "fbbp.mcp.final_release.v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "ok": all(item["ok"] for item in checks),
        "passed_count": sum(1 for item in checks if item["ok"]),
        "check_count": len(checks),
        "checks": checks,
        "client_matrix": {client: str(path) for client, path in CLIENT_CONFIGS.items()},
        "artifacts": {
            "api_reference": str(REPO_ROOT / "docs" / "mcp_tool_api_reference.md"),
            "formal_contract": str(REPO_ROOT / "docs" / "formal_tool_contract.md"),
            "client_acceptance_matrix": str(REPO_ROOT / "docs" / "client_acceptance_matrix.md"),
            "production_service_runbook": str(REPO_ROOT / "docs" / "production_service_runbook.md"),
            "live_client_acceptance_json": str(LIVE_ACCEPTANCE_JSON),
            "live_client_acceptance_md": str(LIVE_ACCEPTANCE_MD),
            "docker_compose": str(REPO_ROOT / "docker-compose.yml"),
            **client_outputs,
        },
    }
    json_path = output_root / "final_release_summary.json"
    md_path = output_root / "final_release_summary.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# FBBP MCP Final Release Summary",
        "",
        f"- ok: {summary['ok']}",
        f"- checks: {summary['passed_count']}/{summary['check_count']}",
        "",
        "## Checks",
        "",
    ]
    for item in checks:
        lines.append(f"- {'PASS' if item['ok'] else 'FAIL'} {item['name']}")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- API reference: `{summary['artifacts']['api_reference']}`",
            f"- Formal contract: `{summary['artifacts']['formal_contract']}`",
            f"- Client acceptance matrix: `{summary['artifacts']['client_acceptance_matrix']}`",
            f"- Production service runbook: `{summary['artifacts']['production_service_runbook']}`",
            f"- Live client acceptance JSON: `{summary['artifacts']['live_client_acceptance_json']}`",
            f"- Docker Compose: `{summary['artifacts']['docker_compose']}`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"summary_json": str(json_path), "summary_md": str(md_path)}


def run_final_release_check(require_docker_live: bool = False) -> dict[str, Any]:
    checks = [
        check_tool_registration(),
        check_response_contract(),
        check_client_matrix(),
        check_contract_docs(),
        check_ops_docs(),
        check_live_client_acceptance(),
        check_deployment_assets(require_docker_live=require_docker_live),
        check_public_naming(),
    ]
    outputs = write_summary(checks)
    return {
        "ok": all(item["ok"] for item in checks),
        "passed_count": sum(1 for item in checks if item["ok"]),
        "check_count": len(checks),
        "outputs": outputs,
        "checks": [{"name": item["name"], "ok": item["ok"]} for item in checks],
    }


def main() -> None:
    require_docker_live = "--require-docker-live" in sys.argv
    result = run_final_release_check(require_docker_live=require_docker_live)
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
