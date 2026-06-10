from __future__ import annotations


class MCPToolError(RuntimeError):
    def __init__(self, *, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def map_exception(exc: Exception) -> dict[str, object]:
    if isinstance(exc, MCPToolError):
        return {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        }

    message = str(exc)
    if isinstance(exc, ValueError):
        code = "INVALID_REQUEST"
    elif isinstance(exc, RuntimeError) and "import ragkb" in message.lower():
        code = "IMPORT_ERROR"
    elif isinstance(exc, TimeoutError):
        code = "TIMEOUT_ERROR"
    else:
        code = "UNKNOWN_ERROR"

    return {
        "code": code,
        "message": message,
        "details": {},
    }
