# Formal Runtime Metadata

The MCP service reads formal runtime metadata from environment variables when available:

- `FBTP_FORMAL_DATASET_VERSION`
- `FBTP_FORMAL_RUNTIME_PROFILE`

If these variables are unset, the service falls back to `unknown`.
