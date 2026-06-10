# Formal Dataset Descriptors

Checked-in dataset descriptors provide stable names for formal MCP runtime metadata.

Each descriptor file is named `<dataset_version>.json`.

Recommended fields:

- `dataset_version`
- `label`
- `primary_sources`
- `notes`

For formal FBBP descriptors, also prefer:

- `formal_snapshot.root`
- `rebuild.source_allowlist`
- `rebuild.upstream_source_allowlist`
- `source_registry.<source>.runtime_snapshot`

The active real-data naming line is `FBBP`, for example `fbbp_private_v2026_04`.
