from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from fbbp_mcp_server.runtime_env import (
    DEFAULT_ENV_VALUES,
    build_runtime_env_values,
    detect_runtime_mode,
    ensure_runtime_env_file,
    render_runtime_env,
)


class RuntimeEnvTests(unittest.TestCase):
    def test_render_runtime_env_uses_real_mode_defaults(self) -> None:
        rendered = render_runtime_env()
        self.assertIn("PGTABLE=rag_documents_bge_m3", rendered)
        self.assertIn("EMBEDDING_PROVIDER=bge_m3", rendered)
        self.assertIn(r"EMBEDDING_MODEL=..\models\bge-m3-local", rendered)
        self.assertIn("ANSWER_MODE=openai", rendered)
        self.assertIn("LLM_MODEL=DeepSeek-V3.2", rendered)
        self.assertIn("FBBP_MCP_DEFAULT_TOP_K=5", rendered)
        self.assertIn("FBBP_MCP_DEFAULT_ANSWER_MODE=openai", rendered)
        self.assertIn("FBBP_MCP_RUNTIME_MODE=research-dev", rendered)
        self.assertIn("FBTP_MCP_DEFAULT_ANSWER_MODE=openai", rendered)
        self.assertIn("HF_HUB_OFFLINE=1", rendered)
        self.assertIn("TRANSFORMERS_OFFLINE=1", rendered)

    def test_ensure_runtime_env_file_creates_env_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            env_path = ensure_runtime_env_file(repo_root)
            self.assertTrue(env_path.exists())
            original = env_path.read_text(encoding="utf-8")

            env_path.write_text("OPENAI_API_KEY=keep-me\n", encoding="utf-8")
            second = ensure_runtime_env_file(repo_root)
            self.assertEqual(second, env_path)
            self.assertEqual(env_path.read_text(encoding="utf-8"), "OPENAI_API_KEY=keep-me\n")
            self.assertNotEqual(original, "OPENAI_API_KEY=keep-me\n")

    def test_build_runtime_env_values_prefers_sibling_ragkb_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            repo_root = workspace / "fbbp-mcp-rag-server"
            ragkb_root = workspace / "llm-rag-knowledge-base"
            repo_root.mkdir()
            ragkb_root.mkdir()
            (ragkb_root / ".env").write_text(
                "\n".join(
                    [
                        "OPENAI_API_KEY=test-key",
                        "BASE_URL=https://example.invalid",
                        "OPENAI_BASE_URL=https://example.invalid",
                        "OPENAI_API_BASE=https://example.invalid",
                        "LLM_MODEL=GLM-5",
                        "PGTABLE=rag_documents_custom",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.dict("os.environ", {}, clear=True):
                values = build_runtime_env_values(repo_root)

        self.assertEqual(values["OPENAI_API_KEY"], "test-key")
        self.assertEqual(values["BASE_URL"], "https://example.invalid")
        self.assertEqual(values["LLM_MODEL"], "GLM-5")
        self.assertEqual(values["PGTABLE"], "rag_documents_custom")

    def test_default_env_order_keeps_api_key_near_runtime_config(self) -> None:
        keys = list(DEFAULT_ENV_VALUES.keys())
        self.assertLess(keys.index("OPENAI_API_KEY"), keys.index("LLM_MODEL"))
        self.assertLess(keys.index("LLM_MODEL"), keys.index("EMBEDDING_PROVIDER"))

    def test_detect_runtime_mode_prefers_fbbp_runtime_env_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            with mock.patch.dict(
                "os.environ",
                {
                    "FBBP_MCP_RUNTIME_MODE": "formal-prod",
                    "FBTP_MCP_RUNTIME_MODE": "legacy-dev",
                },
                clear=True,
            ):
                runtime_mode = detect_runtime_mode(repo_root)

        self.assertEqual(runtime_mode, "formal-prod")


if __name__ == "__main__":
    unittest.main()
