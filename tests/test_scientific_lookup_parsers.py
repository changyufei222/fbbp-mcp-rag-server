from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fbbp_mcp_server.scientific_lookups import (
    _get_json,
    parse_pdb_entry,
    parse_pubmed_summary,
    parse_uniprot_entry,
)


class ScientificLookupParserTests(unittest.TestCase):
    def test_get_json_uses_cache(self) -> None:
        fake_response = mock.MagicMock()
        fake_response.read.return_value = b'{"ok": true}'
        fake_context = mock.MagicMock()
        fake_context.__enter__.return_value = fake_response
        fake_context.__exit__.return_value = None

        with mock.patch("fbbp_mcp_server.scientific_lookups.urlopen", return_value=fake_context) as mocked:
            first = _get_json("https://example.org/test")
            second = _get_json("https://example.org/test")

        self.assertEqual(first, {"ok": True})
        self.assertEqual(second, {"ok": True})
        self.assertEqual(mocked.call_count, 1)

    def test_parse_pubmed_summary(self) -> None:
        payload = {
            "result": {
                "uids": ["1"],
                "1": {
                    "uid": "1",
                    "title": "Backbone flexibility in binding proteins",
                    "pubdate": "2025 Jan",
                    "fulljournalname": "Protein Science",
                    "authors": [{"name": "Zhang"}],
                },
            }
        }
        result = parse_pubmed_summary(payload)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["articles"][0]["pmid"], "1")

    def test_parse_uniprot_entry(self) -> None:
        payload = {
            "primaryAccession": "P12345",
            "uniProtkbId": "TEST_HUMAN",
            "proteinDescription": {
                "recommendedName": {
                    "fullName": {"value": "Test protein"}
                }
            },
            "organism": {"scientificName": "Homo sapiens"},
            "genes": [{"geneName": {"value": "TEST"}}],
            "sequence": {"length": 321},
        }
        result = parse_uniprot_entry(payload)
        self.assertEqual(result["accession"], "P12345")
        self.assertEqual(result["gene"], "TEST")

    def test_parse_pdb_entry(self) -> None:
        payload = {
            "rcsb_id": "1ABC",
            "struct": {"title": "Example structure"},
            "exptl": [{"method": "X-RAY DIFFRACTION"}],
            "rcsb_entry_info": {"resolution_combined": [2.1]},
            "rcsb_accession_info": {"initial_release_date": "2024-01-01T00:00:00Z"},
        }
        result = parse_pdb_entry(payload)
        self.assertEqual(result["pdb_id"], "1ABC")
        self.assertEqual(result["resolution"], 2.1)


if __name__ == "__main__":
    unittest.main()
