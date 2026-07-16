import unittest
import os
import sys
import json
import tempfile
import shutil

# Add repo root to sys.path so `tools` is importable.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from tools.reproduce import verify_release


class TestReproduceVerifier(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

        self.meta = {
            "release": "2026.11.1",
            "legislature": "deu-bundestag-21",
            "methodology_version": "1.0",
            "signature_verified": True,
            "statement_count": 1,
            # Pin the target date the release was built against so the verifier
            # does not have to fall back. (Constants fall back to deu-bundestag-21.)
            "as_of": "2026-11-01",
        }
        self.statements = [{"id": 14, "policy_slug": "schuldenbremse-de", "topic": "wirtschaft", "text_de": "…"}]
        self.parties = [{"id": 3, "short_name": "SPD", "name": "SPD", "ballot_status": "parliamentary"}]
        self.evidence = {
            "ev-1043": {"tier": 1, "direction": 1.0, "date": "2026-10-01", "kind": "namentliche_abstimmung"}
        }
        # Single fresh T1 item, +1.0, ~1 month old.
        #   rho   = e^(-0.17328679513 * 31/365.25) = 0.985401
        #   W     = 1.0 * 0.985401
        #   vol   = 1 - e^(-W/1.3028834457) = 0.5306
        #   agree = 1 (single item, std 0)  ->  confidence = 0.5306
        self.positions = {
            "3:14": {
                "p": 1.0,
                "confidence": 0.5306,
                "p_said": None,
                "p_did": 1.0,
                "divergent": False,
                "evidence_ids": ["ev-1043"],
            }
        }
        self._write()

    def _write(self):
        for name, obj in [
            ("meta.json", self.meta), ("statements.json", self.statements),
            ("parties.json", self.parties), ("evidence.json", self.evidence),
            ("positions.json", self.positions),
        ]:
            with open(os.path.join(self.test_dir, name), "w", encoding="utf-8") as f:
                json.dump(obj, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_verify_release_success(self):
        self.assertTrue(verify_release(self.test_dir))

    def test_verify_release_mismatch(self):
        self.positions["3:14"]["p"] = -1.0
        self._write()
        self.assertFalse(verify_release(self.test_dir))

    def test_verify_release_confidence_mismatch_is_exact(self):
        # A confidence off by 0.005 used to pass under a 0.01 tolerance; exact
        # (byte-identical) comparison must now reject it.
        self.positions["3:14"]["confidence"] = 0.5358
        self._write()
        self.assertFalse(verify_release(self.test_dir))


if __name__ == "__main__":
    unittest.main()
