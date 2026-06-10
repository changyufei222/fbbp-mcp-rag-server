from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fbbp_mcp_server.bootstrap import ensure_local_site_packages

ensure_local_site_packages()

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client


OUTPUT_ROOT = REPO_ROOT / "reports" / "final_release" / "latest"
HTTP_ACCEPTANCE_HOST = "127.0.0.1"
HTTP_ACCEPTANCE_PORT = 8010
HTTP_ACCEPTANCE_URL = f"http://{HTTP_ACCEPTANCE_HOST}:{HTTP_ACCEPTANCE_PORT}/mcp"
CLIENT_CONFIGS = {
    "codex": REPO_ROOT / "examples" / "clients" / "codex.config.toml",
    "claude_code": REPO_ROOT / "examples" / "clients" / "claude-code.mcp.json",
    "cursor": REPO_ROOT / "examples" / "clients" / "cursor.mcp.json",
    "deerflow": REPO_ROOT / "examples" / "extensions_config.deerflow.json",
}
CLIENT_MATRIX = {
    "codex": {
        "label": "Codex",
        "transport": "http",
        "url": HTTP_ACCEPTANCE_URL,
        "tool_calls": [
            ("tool_contract_version", {}),
            ("server_status", {}),
        ],
    },
    "claude_code": {
        "label": "Claude Code",
        "transport": "http",
        "url": HTTP_ACCEPTANCE_URL,
        "tool_calls": [
            ("health_status", {}),
            ("list_record_types", {"limit": 10}),
        ],
    },
    "cursor": {
        "label": "Cursor",
        "transport": "http",
        "url": HTTP_ACCEPTANCE_URL,
        "tool_calls": [
            ("list_sources", {"limit": 5}),
            ("get_source_summary", {"source": "domains.csv", "limit": 5}),
        ],
    },
    "deerflow": {
        "label": "DeerFlow",
        "transport": "stdio",
        "command": "",
        "args": ["-S", str(REPO_ROOT / "server.py")],
        "env": {},
        "tool_calls": [
            ("preview_ingest", {"input_path": str(REPO_ROOT / "docs")}),
            ("server_status", {}),
        ],
    },
}


def _http_health_ok(url: str) -> bool:
    try:
        import urllib.request
        import urllib.error

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=10):
            return True
    except urllib.error.HTTPError as exc:
        try:
            payload = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            payload = ""
        if exc.code == 400 and "Missing session ID" in payload:
            return True
        return False
    except Exception:
        return False


def _parse_content_payload(content_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(content_text)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _formal_acceptance_env() -> dict[str, str]:
    return {
        "PGHOST": "localhost",
        "PGPORT": "5432",
        "PGDATABASE": "ragkb",
        "PGUSER": "ragkb",
        "PGPASSWORD": "ragkb",
        "PGTABLE": "rag_documents_bge_m3",
        "PGCONNECT_TIMEOUT": "5",
        "EMBEDDING_PROVIDER": "bge_m3",
        "ANSWER_MODE": "openai",
        "RAGKB_SRC_PATH": str(REPO_ROOT.parent / "llm-rag-knowledge-base" / "src"),
        "FBBP_FORMAL_DATASET_VERSION": "fbbp_private_v2026_04",
        "FBTP_FORMAL_DATASET_VERSION": "fbbp_private_v2026_04",
        "FBBP_FORMAL_RUNTIME_PROFILE": "local_formal",
        "FBTP_FORMAL_RUNTIME_PROFILE": "local_formal",
    }


def _server_python_executable() -> str:
    local_python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if local_python.exists():
        return str(local_python)
    return sys.executable


def _live_acceptance_log_paths() -> tuple[Path, Path]:
    log_root = REPO_ROOT
    return (
        log_root / "http_mcp_live_acceptance.out.log",
        log_root / "http_mcp_live_acceptance.err.log",
    )


def _render_process_failure(stderr_path: Path, stdout_path: Path, reason: str) -> str:
    stderr_tail = ""
    stdout_tail = ""
    if stderr_path.exists():
        stderr_tail = "\n".join(stderr_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:])
    if stdout_path.exists():
        stdout_tail = "\n".join(stdout_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:])
    details = [reason, f"stderr_log={stderr_path}", f"stdout_log={stdout_path}"]
    if stderr_tail:
        details.append(f"stderr_tai<local_path_removed>")
    if stdout_tail:
        details.append(f"stdout_tai<local_path_removed>")
    return "\n".join(details)


def _start_http_server() -> subprocess.Popen[str] | None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.update(_formal_acceptance_env())
    stdout_path, stderr_path = _live_acceptance_log_paths()
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    python_executable = _server_python_executable()
    process = subprocess.Popen(
        [
            python_executable,
            "-S",
            str(REPO_ROOT / "server.py"),
            "--transport",
            "streamable-http",
            "--host",
            HTTP_ACCEPTANCE_HOST,
            "--port",
            str(HTTP_ACCEPTANCE_PORT),
        ],
        cwd=REPO_ROOT,
        stdout=stdout_handle,
        stderr=stderr_handle,
        env=env,
        text=True,
    )
    stdout_handle.close()
    stderr_handle.close()
    for _ in range(30):
        if _http_health_ok(HTTP_ACCEPTANCE_URL):
            return process
        if process.poll() is not None:
            raise RuntimeError(
                _render_process_failure(
                    stderr_path,
                    stdout_path,
                    f"Streamable-http MCP server exited early with code {process.returncode}",
                )
            )
        time.sleep(1)
    process.terminate()
    try:
        process.wait(timeout=10)
    except Exception:
        process.kill()
    raise RuntimeError(
        _render_process_failure(
            stderr_path,
            stdout_path,
            f"Timed out waiting for streamable-http MCP server on {HTTP_ACCEPTANCE_URL}",
        )
    )


@asynccontextmanager
async def _http_session(url: str):
    async with streamable_http_client(url) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


@asynccontextmanager
async def _stdio_session(command: str, args: list[str], env: dict[str, str] | None = None):
    server = StdioServerParameters(
        command=command,
        args=args,
        env={**os.environ, **(env or {})},
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def _run_one_client(client_key: str) -> dict[str, Any]:
    metadata = CLIENT_MATRIX[client_key]
    config_path = CLIENT_CONFIGS[client_key]
    started_at = time.perf_counter()
    result: dict[str, Any] = {
        "client": client_key,
        "label": metadata["label"],
        "transport": metadata["transport"],
        "config_path": str(config_path),
        "config_exists": config_path.exists(),
        "ok": False,
        "tool_count": 0,
        "tool_calls": [],
    }

    if metadata["transport"] == "http":
        session_cm = _http_session(metadata["url"])
    else:
        stdio_command = metadata["command"] or _server_python_executable()
        stdio_env = {**_formal_acceptance_env(), **(metadata.get("env") or {})}
        session_cm = _stdio_session(stdio_command, metadata["args"], stdio_env)
    async with session_cm as session:
        tools = await session.list_tools()
        tool_names = sorted(tool.name for tool in tools.tools)
        result["tool_count"] = len(tool_names)
        result["tool_names"] = tool_names
        for tool_name, arguments in metadata["tool_calls"]:
            call_started = time.perf_counter()
            try:
                call_result = await asyncio.wait_for(session.call_tool(tool_name, arguments), timeout=90)
            except TimeoutError as exc:
                raise RuntimeError(f"{metadata['label']} timed out while calling {tool_name}") from exc
            elapsed_ms = round((time.perf_counter() - call_started) * 1000, 2)
            content_text = ""
            if getattr(call_result, "content", None):
                first_content = call_result.content[0]
                content_text = getattr(first_content, "text", "") or str(first_content)
            structured = getattr(call_result, "structuredContent", None)
            parsed_payload = structured if isinstance(structured, dict) else {}
            if not parsed_payload and content_text:
                parsed_payload = _parse_content_payload(content_text)
            tool_ok = bool(parsed_payload.get("ok")) if parsed_payload else not bool(getattr(call_result, "isError", False))
            result["tool_calls"].append(
                {
                    "tool": tool_name,
                    "arguments": arguments,
                    "ok": tool_ok,
                    "is_error": bool(getattr(call_result, "isError", False)),
                    "latency_ms": elapsed_ms,
                    "content_preview": content_text[:240],
                    "structured_keys": sorted(parsed_payload.keys()) if parsed_payload else [],
                    "error_code": ((parsed_payload.get("error") or {}).get("code") if isinstance(parsed_payload.get("error"), dict) else None),
                }
            )
        result["ok"] = all(item["ok"] for item in result["tool_calls"]) and result["tool_count"] >= 10
    result["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    return result


def _write_reports(payload: dict[str, Any], output_root: Path) -> dict[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "live_client_acceptance.json"
    md_path = output_root / "live_client_acceptance.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# FBBP MCP Live Client Acceptance",
        "",
        f"- created_at_utc: {payload['created_at_utc']}",
        f"- ok: {payload['ok']}",
        "",
        "| Client | Transport | Config | Live Calls | Tool Count | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for item in payload["clients"]:
        notes = ", ".join(f"{call['tool']}={'ok' if call['ok'] else 'fail'}" for call in item["tool_calls"])
        lines.append(
            f"| {item['label']} | {item['transport']} | {'yes' if item['config_exists'] else 'no'} | {'yes' if item['ok'] else 'no'} | {item['tool_count']} | {notes} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


async def _run_all_clients() -> dict[str, Any]:
    server_process = _start_http_server()
    try:
        clients = []
        for client_key in ("codex", "claude_code", "cursor", "deerflow"):
            clients.append(await _run_one_client(client_key))
        payload = {
            "schema_version": "fbbp.mcp.live_acceptance.v1",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "ok": all(item["ok"] for item in clients),
            "clients": clients,
        }
        payload["artifacts"] = _write_reports(payload, OUTPUT_ROOT)
        return payload
    finally:
        if server_process is not None:
            server_process.terminate()
            try:
                server_process.wait(timeout=10)
            except Exception:
                server_process.kill()


def run_live_client_acceptance() -> dict[str, Any]:
    return asyncio.run(_run_all_clients())


def main() -> None:
    global OUTPUT_ROOT
    parser = argparse.ArgumentParser(description="Run live MCP acceptance across Codex, Claude Code, Cursor, and DeerFlow transports.")
    parser.add_argument("--output-root", default=str(OUTPUT_ROOT))
    args = parser.parse_args()
    OUTPUT_ROOT = Path(args.output_root).resolve()
    result = run_live_client_acceptance()
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
