# FBBP MCP Production Service Runbook

This runbook captures the production-shaped operating story for `fbbp-mcp-rag-server`.

## Deployment Shapes

- Docker Compose: use `docker-compose.yml` for a local or single-host deployment baseline.
- systemd: use `configs/fbbp-mcp-rag-server.service.example` when the service should run as a durable Linux unit.
- Reverse proxy: place nginx / Caddy / another reverse proxy in front of the MCP service when exposing it beyond loopback.

## Health And Monitoring

- Health endpoint: probe `/mcp` plus a lightweight tool such as `server_status`.
- Structured smoke: call `tool_contract_version`, then `health_status`, then one retrieval tool.
- Logging: capture stdout/stderr from the Python process and from the reverse proxy separately.
- Alerting baseline: fire alerts on repeated MCP 5xx, repeated timeout envelopes, or sustained public lookup failures.

## Auth Boundary

- Loopback-only local usage can rely on host-level trust.
- Non-loopback deployments should add auth at the reverse proxy or service mesh layer.
- Acceptable auth patterns include API key injection, OIDC-backed gateway auth, or private service-network ACLs.
- Document the client auth expectation together with the client config used by Codex, Claude Code, Cursor, or DeerFlow.

## Rate Limit Boundary

- Public scientific lookups can be bursty and should be protected with rate limit controls at the proxy layer.
- Retrieval-heavy MCP usage should cap concurrency before the upstream public services start failing.
- When in doubt, prefer reverse-proxy rate limit rules plus client-side retry with backoff instead of letting the server saturate upstream APIs.

## Rollout Checklist

1. Validate Docker Compose syntax and environment variables.
2. Validate systemd or process-manager wiring.
3. Confirm reverse proxy routes `/mcp` correctly.
4. Run Codex / Claude Code / Cursor / DeerFlow smoke calls from the client acceptance matrix.
5. Confirm logs, health probes, auth, and rate limit behavior.

## Recovery Pattern

- If the MCP process is healthy but tools fail, check environment variables and data-path mounts first.
- If HTTP MCP fails while stdio still works, check reverse proxy and loopback binding.
- If public scientific lookup tools fail but private retrieval works, treat that as an upstream dependency issue rather than a core server outage.
