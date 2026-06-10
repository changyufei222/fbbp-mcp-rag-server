# Upstream Notes

- This repo is primarily your own implementation.
- It does **not** directly fork an upstream MCP RAG repository.
- Design ideas may reference public MCP examples and MCP RAG server patterns.

## Reference-Only Inspirations
- `modelcontextprotocol/python-sdk` for the official Python MCP server pattern
- `shinpr/mcp-local-rag` for tool and client-integration ideas

## Core Design Decision
- Reuse `ragkb` as the knowledge engine
- Expose only a thin MCP service layer
- Avoid maintaining a second RAG ingestion / retrieval stack

