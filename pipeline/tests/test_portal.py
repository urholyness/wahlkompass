import unittest
import os
import sys
import json
import sqlite3
from fastapi.testclient import TestClient

# Add WID directory to python path to find portal
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Setup test environment variables
os.environ["SQLITE_DB_PATH"] = "test_portal.db"
# Ensure we don't accidentally write to dev db
if os.path.exists("test_portal.db"):
    os.remove("test_portal.db")

from portal.src.main import app, get_db_conn, init_dev_db

class TestPortalBackend(unittest.TestCase):

    def setUp(self):
        # Initialize test database
        self.conn = get_db_conn()
        init_dev_db(self.conn)
        self.client = TestClient(app)

    def tearDown(self):
        self.conn.close()
        if os.path.exists("test_portal.db"):
            try:
                os.remove("test_portal.db")
            except PermissionError:
                pass # SQLite sometimes locks

    def test_statement_crud(self):
        # 1. Create statement
        stmt_data = {
            "policy_slug": "investments-de",
            "text_de": "Der Staat soll mehr investieren.",
            "text_easy_de": "Der Staat soll Geld ausgeben für Straßen und Schulen.",
            "context_de": "Hintergrundinformation...",
            "topic": "wirtschaft",
            "admission_ref": "ev-88",
            "status": "draft"
        }
        response = self.client.post("/statements", json=stmt_data)
        self.assertEqual(response.status_code, 201) # HTTP 201 Created
        resp_json = response.json()
        self.assertEqual(resp_json["policy_slug"], "investments-de")
        self.assertIn("id", resp_json)
        stmt_id = resp_json["id"]

        # 2. Get statement by ID
        response = self.client.get(f"/statements/{stmt_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["policy_slug"], "investments-de")

        # 3. List statements
        response = self.client.get("/statements")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 1)

    def test_double_blind_coding_concordant(self):
        # Create a statement first
        stmt = self.client.post("/statements", json={
            "policy_slug": "test-slug", "text_de": "Test...", "topic": "test", "admission_ref": "ev-0"
        }).json()
        stmt_id = stmt["id"]

        # Coder A submits direction +1.0
        sub_a = {
            "party_id": 1,
            "statement_id": stmt_id,
            "document_id": 100,
            "tier": 2,
            "direction": 1.0,
            "evidence_date": "2026-07-16",
            "extract": "Excerpt text",
            "coder_name": "Alice"
        }
        res_a = self.client.post("/coding/submit", json=sub_a)
        self.assertEqual(res_a.status_code, 201)
        self.assertEqual(res_a.json()["status"], "registered_first_coding")

        # Coder B submits concordant direction +0.8 (disagreement = 0.2 <= 0.5)
        sub_b = {
            "party_id": 1,
            "statement_id": stmt_id,
            "document_id": 100,
            "tier": 2,
            "direction": 0.8,
            "evidence_date": "2026-07-16",
            "extract": "Excerpt text",
            "coder_name": "Bob"
        }
        res_b = self.client.post("/coding/submit", json=sub_b)
        self.assertEqual(res_b.status_code, 201)
        self.assertEqual(res_b.json()["status"], "auto_verified")
        # Final direction should be the average: (1.0 + 0.8)/2 = 0.9
        self.assertAlmostEqual(res_b.json()["final_direction"], 0.9)

    def test_double_blind_coding_discordant_and_resolution(self):
        stmt = self.client.post("/statements", json={
            "policy_slug": "test-slug-2", "text_de": "Test...", "topic": "test", "admission_ref": "ev-0"
        }).json()
        stmt_id = stmt["id"]

        # Coder A submits +1.0
        self.client.post("/coding/submit", json={
            "party_id": 1, "statement_id": stmt_id, "document_id": 101, "tier": 2,
            "direction": 1.0, "evidence_date": "2026-07-16", "extract": "Excerpt...", "coder_name": "Alice"
        })

        # Coder B submits discordant -1.0 (disagreement = 2.0 > 0.5)
        res_b = self.client.post("/coding/submit", json={
            "party_id": 1, "statement_id": stmt_id, "document_id": 101, "tier": 2,
            "direction": -1.0, "evidence_date": "2026-07-16", "extract": "Excerpt...", "coder_name": "Bob"
        })
        self.assertEqual(res_b.json()["status"], "escalated_to_board")

        # Fetch escalations
        escalations = self.client.get("/coding/escalations").json()
        self.assertEqual(len(escalations), 1)
        ev_id = escalations[0]["id"]

        # Resolve escalation
        res_resolution = self.client.post(f"/coding/escalations/{ev_id}/resolve", json={
            "direction": 0.0,
            "resolution_notes": "Board resolved that it represents a neutral/compromise position.",
            "board_member": "Dr. Statistics"
        })
        self.assertEqual(res_resolution.status_code, 200)
        self.assertEqual(res_resolution.json()["status"], "resolved")
        self.assertEqual(res_resolution.json()["resolved_direction"], 0.0)

if __name__ == "__main__":
    unittest.main()
