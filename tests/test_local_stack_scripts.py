from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"


def _powershell_exe() -> str:
    return "powershell"


def _script_parameter_names(script_path: Path) -> list[str]:
    probe = (
        f"$params=(Get-Command '{script_path.as_posix()}').Parameters.Keys | Sort-Object;"
        " $params | ConvertTo-Json -Compress"
    )
    proc = subprocess.run(
        [_powershell_exe(), "-NoProfile", "-Command", probe],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout.strip())


class LocalStackScriptTests(unittest.TestCase):
    def test_json_tail_helper_extracts_structured_payload_from_noisy_output(self) -> None:
        helper_path = SCRIPTS_ROOT / "common_json_output.ps1"
        probe = (
            f". '{helper_path.as_posix()}';"
            " $raw = @'\nNOTICE: extension \"vector\" already exists, skipping\n{\n  \"ok\": true,\n  \"mode\": \"started_wsl_postgres\"\n}\n'@;"
            " $parsed = ConvertFrom-JsonTailPayload -RawText $raw;"
            " $parsed | ConvertTo-Json -Compress"
        )
        proc = subprocess.run(
            [_powershell_exe(), "-NoProfile", "-Command", probe],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )

        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout.strip())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "started_wsl_postgres")

    def test_run_local_smoke_once_avoids_reserved_host_variable_name(self) -> None:
        script = (SCRIPTS_ROOT / "run_local_smoke_once.ps1").read_text(encoding="utf-8")

        self.assertNotIn("[string]$Host", script)
        self.assertIn("TargetHost", script)

    def test_start_http_server_uses_listen_host_parameter(self) -> None:
        params = _script_parameter_names(SCRIPTS_ROOT / "start_http_server.ps1")

        self.assertIn("ListenHost", params)
        self.assertNotIn("Host", params)

    def test_start_http_server_accepts_formal_identity_parameters(self) -> None:
        params = _script_parameter_names(SCRIPTS_ROOT / "start_http_server.ps1")
        script = (SCRIPTS_ROOT / "start_http_server.ps1").read_text(encoding="utf-8")

        self.assertIn("DatasetVersion", params)
        self.assertIn("RuntimeProfile", params)
        self.assertIn("fbbp_private_v2026_04", script)
        self.assertIn("local_formal", script)

    def test_start_fresh_postgres_supports_pg_bin_root_override(self) -> None:
        params = _script_parameter_names(SCRIPTS_ROOT / "start_fresh_postgres_foreground.ps1")

        self.assertIn("PgBinRoot", params)

    def test_run_local_smoke_once_plan_only_defaults_to_reuse_prepared_formal_db(self) -> None:
        script_path = SCRIPTS_ROOT / "run_local_smoke_once.ps1"
        proc = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-PlanOnly",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )

        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        plan = json.loads(proc.stdout.strip())
        self.assertEqual(plan["mode"], "reuse_prepared_formal_db")
        self.assertEqual(plan["dataset_version"], "fbbp_private_v2026_04")
        self.assertIn("rebuild_fbbp_formal_db.ps1", plan["rebuild_command"])

    def test_run_formal_acceptance_script_runs_real_smoke_before_acceptance_suite(self) -> None:
        script_path = SCRIPTS_ROOT / "run_formal_acceptance.ps1"

        self.assertTrue(script_path.exists(), msg="formal acceptance runner script is missing")
        script = script_path.read_text(encoding="utf-8")
        self.assertIn("smoke_local_stack.ps1", script)
        self.assertIn("tests/acceptance", script.replace("\\", "/"))

    def test_smoke_local_stack_defaults_match_formal_local_pg(self) -> None:
        script = (SCRIPTS_ROOT / "smoke_local_stack.ps1").read_text(encoding="utf-8")

        self.assertIn('[string]$PgHost = "localhost"', script)
        self.assertIn('[int]$PgPort = 5432', script)

    def test_smoke_local_stack_uses_real_queries_without_ingest_switches(self) -> None:
        script = (SCRIPTS_ROOT / "smoke_local_stack.ps1").read_text(encoding="utf-8")

        self.assertIn("[switch]$ResolveTopChunk", script)
        self.assertIn('payload["list_sources"] = service.list_available_sources', script)
        self.assertIn('payload["source_summary"] = service.get_source_summary', script)
        self.assertIn('payload["search"] = service.search_knowledge', script)
        self.assertNotIn("preview_ingest", script)
        self.assertNotIn("ingest_sources_into_knowledge", script)

    def test_run_local_smoke_once_invokes_smoke_without_dataset_ingest_arguments(self) -> None:
        script = (SCRIPTS_ROOT / "run_local_smoke_once.ps1").read_text(encoding="utf-8")

        self.assertIn("smoke_local_stack.ps1", script)
        self.assertNotIn("-DatasetPath", script)
        self.assertNotIn("-IngestLimit 1", script)

    def test_rebuild_script_exists_and_uses_explicit_source_allowlist(self) -> None:
        script_path = SCRIPTS_ROOT / "rebuild_fbbp_formal_db.ps1"

        self.assertTrue(script_path.exists(), msg="formal rebuild runner script is missing")
        script = script_path.read_text(encoding="utf-8")
        self.assertIn("source_allowlist", script)
        self.assertIn("reset_table", script)
        self.assertIn("run_ingest", script)

    def test_formal_dataset_descriptor_uses_repo_local_snapshot_paths(self) -> None:
        descriptor = json.loads((REPO_ROOT / "configs" / "datasets" / "fbbp_private_v2026_04.json").read_text(encoding="utf-8"))
        source_allowlist = ((descriptor.get("rebuild") or {}).get("source_allowlist") or [])
        interaction_registry = ((descriptor.get("source_registry") or {}).get("interaction_cards_v2.jsonl") or {})

        self.assertTrue(source_allowlist)
        self.assertTrue(all(not str(item).startswith("<local_path_removed>") for item in source_allowlist))
        self.assertTrue(all(str(item).startswith("formal_snapshots/") for item in source_allowlist))
        self.assertEqual(
            interaction_registry.get("runtime_snapshot"),
            "formal_snapshots/fbbp_private_v2026_04/interaction_cards_v2.jsonl",
        )
        self.assertIn("llm-rag-knowledge-base/data/schema_tables_rag_ready/interaction_cards_v2.jsonl", interaction_registry.get("upstream_pipeline", ""))

    def test_sync_formal_snapshot_script_exists(self) -> None:
        script_path = SCRIPTS_ROOT / "sync_formal_snapshot.ps1"

        self.assertTrue(script_path.exists(), msg="formal snapshot sync script is missing")
        script = script_path.read_text(encoding="utf-8")
        self.assertIn("source_allowlist", script)
        self.assertIn("Copy-Item", script)
        self.assertIn("runtime_snapshot", script)

    def test_ensure_local_formal_pg_ready_script_exists(self) -> None:
        script_path = SCRIPTS_ROOT / "ensure_local_formal_pg_ready.ps1"

        self.assertTrue(script_path.exists(), msg="formal PostgreSQL readiness script is missing")
        script = script_path.read_text(encoding="utf-8")
        self.assertIn("netsh interface portproxy", script)
        self.assertIn("pg_ctlcluster 16 main start", script)
        self.assertIn("SELECT 1", script)
        self.assertNotIn("[string]$Host", script)
        self.assertIn("[string]$ProbeHost", script)

    def test_run_local_smoke_once_ensures_formal_pg_before_smoke(self) -> None:
        script = (SCRIPTS_ROOT / "run_local_smoke_once.ps1").read_text(encoding="utf-8")

        self.assertIn("ensure_local_formal_pg_ready.ps1", script)
        self.assertIn("-ExpectedHost $TargetHost", script)
        self.assertIn("-ExpectedPort $PgPort", script)

    def test_run_local_smoke_once_emits_single_structured_json_payload(self) -> None:
        script = (SCRIPTS_ROOT / "run_local_smoke_once.ps1").read_text(encoding="utf-8")

        self.assertIn("common_json_output.ps1", script)
        self.assertIn("ConvertFrom-Json", script)
        self.assertIn("ensure_pg", script)
        self.assertIn("smoke", script)
        self.assertIn("ConvertTo-Json -Depth 12", script)

    def test_run_formal_acceptance_uses_json_tail_helper(self) -> None:
        script = (SCRIPTS_ROOT / "run_formal_acceptance.ps1").read_text(encoding="utf-8")

        self.assertIn("common_json_output.ps1", script)
        self.assertIn("ConvertFrom-JsonTailPayload", script)


if __name__ == "__main__":
    unittest.main()
