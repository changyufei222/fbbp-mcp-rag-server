# Local Smoke Rerun Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local smoke reruns one-command, Windows-first, WSL-fallback, and self-cleaning.

**Architecture:** Keep the existing leaf scripts, repair their broken parameter/preflight behavior, and add a thin orchestration script that chooses Windows PostgreSQL when possible and falls back to WSL otherwise. Reuse the existing smoke script and direct `server.py` HTTP launch semantics.

**Tech Stack:** PowerShell, Python unittest, WSL PostgreSQL 16, MCP server entrypoint

---

## Chunk 1: Regression Tests

### Task 1: Add failing script contract tests

**Files:**
- Create: `E:/项目/fbtp-mcp-rag-server/tests/test_local_stack_scripts.py`
- Test: `E:/项目/fbtp-mcp-rag-server/tests/test_local_stack_scripts.py`

- [ ] **Step 1: Write a failing test for the HTTP script parameter name**
- [ ] **Step 2: Run the test to verify it fails**
- [ ] **Step 3: Add a failing test for PostgreSQL binary override support**
- [ ] **Step 4: Run the test to verify it fails**
- [ ] **Step 5: Add a failing test for the one-command runner `PlanOnly` output**
- [ ] **Step 6: Run the test to verify it fails**

## Chunk 2: Leaf Script Fixes

### Task 2: Repair the MCP HTTP startup script

**Files:**
- Modify: `E:/项目/fbtp-mcp-rag-server/scripts/start_http_server.ps1`
- Test: `E:/项目/fbtp-mcp-rag-server/tests/test_local_stack_scripts.py`

- [ ] **Step 1: Rename the host parameter to avoid `$Host` collisions**
- [ ] **Step 2: Keep the launch command aligned with `python -S server.py --transport streamable-http ...`**
- [ ] **Step 3: Run the targeted script contract test**

### Task 3: Repair the Windows PostgreSQL foreground startup script

**Files:**
- Modify: `E:/项目/fbtp-mcp-rag-server/scripts/start_fresh_postgres_foreground.ps1`
- Test: `E:/项目/fbtp-mcp-rag-server/tests/test_local_stack_scripts.py`

- [ ] **Step 1: Add explicit PostgreSQL binary root override support**
- [ ] **Step 2: Add clear Windows preflight errors for non-ASCII binary paths and elevated sessions**
- [ ] **Step 3: Preserve foreground behavior for valid Windows local runs**
- [ ] **Step 4: Run the targeted script contract test**

## Chunk 3: One-Command Runner

### Task 4: Add the Windows-first, WSL-fallback smoke runner

**Files:**
- Create: `E:/项目/fbtp-mcp-rag-server/scripts/run_local_smoke_once.ps1`
- Create: `E:/项目/fbtp-mcp-rag-server/scripts/run_local_smoke_once.cmd`
- Modify: `E:/项目/fbtp-mcp-rag-server/README.md`
- Test: `E:/项目/fbtp-mcp-rag-server/tests/test_local_stack_scripts.py`

- [ ] **Step 1: Add a `PlanOnly` mode that emits provider order and derived paths as JSON**
- [ ] **Step 2: Implement Windows PostgreSQL attempt with preflight-aware skip/failure capture**
- [ ] **Step 3: Implement WSL PostgreSQL fallback with `-k /tmp`**
- [ ] **Step 4: Start MCP HTTP as a background job using the fixed leaf script or direct server entrypoint**
- [ ] **Step 5: Run the existing smoke script plus an HTTP `/mcp` probe**
- [ ] **Step 6: Always stop MCP and PostgreSQL in `finally` cleanup**
- [ ] **Step 7: Document the one-command workflow in the README**

## Chunk 4: Verification

### Task 5: Verify both unit and real smoke behavior

**Files:**
- Modify: `E:/项目/fbtp-mcp-rag-server/task_plan.md`
- Modify: `E:/项目/fbtp-mcp-rag-server/findings.md`
- Modify: `E:/项目/fbtp-mcp-rag-server/progress.md`

- [ ] **Step 1: Run targeted unit tests for the script contracts**
- [ ] **Step 2: Run the full unittest suite**
- [ ] **Step 3: Run one fresh real end-to-end smoke command**
- [ ] **Step 4: Confirm teardown leaves no `5434` or `8000` listeners**
- [ ] **Step 5: Update project records with evidence and remaining caveats**
