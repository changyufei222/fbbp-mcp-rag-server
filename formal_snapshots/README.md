# Formal Snapshots

This directory stores the checked-in formal JSONL snapshots that `fbtp-mcp-rag-server` reads at runtime.

Current active dataset:

- `fbbp_private_v2026_04`

Refresh the snapshot only through:

```powershell
scripts\sync_formal_snapshot.ps1
```

That command copies the canonical exports from `llm-rag-knowledge-base` into this repo and writes a `MANIFEST.json` beside the snapshot files.
