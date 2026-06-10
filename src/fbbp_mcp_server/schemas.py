from __future__ import annotations

from typing import Any


CONTRACT_VERSION = "1.1"


def build_tool_response(
    *,
    tool: str,
    request: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "tool": tool,
        "contract_version": CONTRACT_VERSION,
        "request": request or {},
        "result": result or {},
        "provenance": provenance or {},
        "diagnostics": diagnostics or {},
        "error": None,
    }


def build_error_response(
    *,
    tool: str,
    request: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "contract_version": CONTRACT_VERSION,
        "request": request or {},
        "result": result or {},
        "provenance": provenance or {},
        "diagnostics": diagnostics or {},
        "error": error or {"code": "UNKNOWN_ERROR", "message": "unknown error"},
    }
