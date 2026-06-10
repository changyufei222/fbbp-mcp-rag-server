# FBBP MCP RAG Server

[English](./README.md) | **中文**

这是一个面向 Codex、Claude Code、Cursor 等 Agent/AI IDE 的 MCP 检索服务。它复用 llm-rag-knowledge-base 的知识引擎，把 FBBP 私有知识检索、摄取预览、运行状态和公共科学数据库查询统一暴露为可审计的 MCP 工具。

## 核心能力

- 面向 Agent 的 MCP 工具接口
- 带来源、证据行和已知未知项的结构化回答
- 仓库内固定 formal snapshot，降低跨仓运行漂移
- PubMed、UniProt 和 RCSB PDB 的轻量公共查询
- FastAPI/HTTP 网关、健康检查和运行状态诊断
- Docker 与本地 Python 两种运行路径

## 快速导航

| 目标 | 入口 |
|---|---|
| 理解工具契约 | [src/fbbp_mcp_server/server.py](./src/fbbp_mcp_server/server.py) |
| 查看固定数据快照 | [ormal_snapshots/README.md](./formal_snapshots/README.md) |
| 查看运行配置 | [configs/](./configs/) |
| 运行测试 | [	ests/](./tests/) |
| 查看最终结果 | [FINAL_RESULT_SUMMARY.md](./FINAL_RESULT_SUMMARY.md) |

## 最小启动思路

1. 安装 Python 3.10+。
2. 按 pyproject.toml 安装项目依赖。
3. 准备 .env 中的数据库与模型配置，切勿提交真实密钥。
4. 使用 Docker Compose 或 Python 服务入口启动。
5. 先执行健康检查，再连接 MCP 客户端。

该服务依赖相邻的 RAG 知识库及实际运行环境，仓库中的截图和快照用于说明已验证路径，不代表公开托管服务长期在线。

详细界面说明见 [INTERFACE_GUIDE_CN.md](./INTERFACE_GUIDE_CN.md)。
