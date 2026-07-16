from fastapi import FastAPI, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import sqlite3
import json
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Wahlkompass Curation & Coding Portal", version="1.1")

# Database Connection Pool/Factory
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_conn():
    """
    Returns a database connection. Automatically detects if using Postgres or local SQLite.
    """
    if DATABASE_URL:
        # PostgreSQL
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        conn.autocommit = False
        return conn
    else:
        # Local SQLite for development and testing
        db_path = os.environ.get("SQLITE_DB_PATH", "portal.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

def init_dev_db(conn):
    """
    Initializes a local SQLite database for development and testing
    """
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS statement (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        policy_slug TEXT,
        text_de TEXT NOT NULL,
        text_easy_de TEXT,
        context_de TEXT,
        topic TEXT NOT NULL,
        admission_ref TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft'
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evidence_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        party_id INTEGER NOT NULL,
        statement_id INTEGER NOT NULL,
        document_id INTEGER NOT NULL,
        tier INTEGER NOT NULL,
        direction REAL NOT NULL,
        item_weight REAL NOT NULL DEFAULT 1.0,
        evidence_date TEXT NOT NULL,
        extract TEXT NOT NULL,
        coder_a TEXT NOT NULL,
        coder_b TEXT,
        resolution TEXT,
        verified INTEGER NOT NULL DEFAULT 0
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        entity TEXT NOT NULL,
        detail TEXT NOT NULL,
        at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()

# Run migrations if local database
if not DATABASE_URL:
    conn = get_db_conn()
    init_dev_db(conn)
    conn.close()

# Pydantic Schemas
class StatementBase(BaseModel):
    policy_slug: str
    text_de: str
    text_easy_de: Optional[str] = None
    context_de: Optional[str] = None
    topic: str
    admission_ref: str
    status: str = "draft"

class StatementCreate(StatementBase):
    pass

class StatementResponse(StatementBase):
    id: int

class CodingSubmission(BaseModel):
    party_id: int
    statement_id: int
    document_id: int
    tier: int = Field(..., ge=1, le=4)
    direction: float = Field(..., ge=-1.0, le=1.0)
    item_weight: float = Field(1.0, ge=0.0, le=1.0)
    evidence_date: str
    extract: str
    coder_name: str

class ResolutionSubmission(BaseModel):
    direction: float = Field(..., ge=-1.0, le=1.0)
    resolution_notes: str
    board_member: str

# Helper to write audit log
def log_audit(conn, actor: str, action: str, entity: str, detail: Dict[str, Any]):
    cursor = conn.cursor()
    detail_str = json.dumps(detail)
    if isinstance(conn, sqlite3.Connection):
        cursor.execute(
            "INSERT INTO audit_log (actor, action, entity, detail) VALUES (?, ?, ?, ?)",
            (actor, action, entity, detail_str)
        )
    else:
        cursor.execute(
            "INSERT INTO audit_log (actor, action, entity, detail) VALUES (%s, %s, %s, %s)",
            (actor, action, entity, detail_str)
        )

# API Routes

@app.post("/statements", response_model=StatementResponse, status_code=status.HTTP_201_CREATED)
def create_statement(stmt: StatementCreate):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor.execute(
                """INSERT INTO statement (policy_slug, text_de, text_easy_de, context_de, topic, admission_ref, status) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (stmt.policy_slug, stmt.text_de, stmt.text_easy_de, stmt.context_de, stmt.topic, stmt.admission_ref, stmt.status)
            )
            stmt_id = cursor.lastrowid
            log_audit(conn, "system", "CREATE", f"statement:{stmt_id}", stmt.model_dump())
        else:
            cursor.execute(
                """INSERT INTO statement (policy_slug, text_de, text_easy_de, context_de, topic, admission_ref, status) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (stmt.policy_slug, stmt.text_de, stmt.text_easy_de, stmt.context_de, stmt.topic, stmt.admission_ref, stmt.status)
            )
            stmt_id = cursor.fetchone()["id"]
            log_audit(conn, "system", "CREATE", f"statement:{stmt_id}", stmt.model_dump())
            
        conn.commit()
        return {**stmt.model_dump(), "id": stmt_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

@app.get("/statements", response_model=List[StatementResponse])
def get_statements(limit: int = 100, offset: int = 0):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor.execute("SELECT * FROM statement LIMIT ? OFFSET ?", (limit, offset))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        else:
            cursor.execute("SELECT * FROM statement LIMIT %s OFFSET %s", (limit, offset))
            rows = cursor.fetchall()
            return rows
    finally:
        conn.close()

@app.get("/statements/{stmt_id}", response_model=StatementResponse)
def get_statement(stmt_id: int):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor.execute("SELECT * FROM statement WHERE id = ?", (stmt_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Statement not found")
            return dict(row)
        else:
            cursor.execute("SELECT * FROM statement WHERE id = %s", (stmt_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Statement not found")
            return row
    finally:
        conn.close()

@app.post("/coding/submit", status_code=status.HTTP_201_CREATED)
def submit_coding(submission: CodingSubmission):
    """
    Submits a coding direction for an evidence item.
    Enforces double-blind coder comparison:
      - If coder_b is empty, we register the submission from coder_a.
      - If coder_a already exist, we compare the directions:
        - If disagreement <= 0.5, we verify the evidence.
        - If disagreement > 0.5, it remains unverified and escalates to board review.
    """
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        # Check if an unverified entry already exists for this party-statement-document combo
        if isinstance(conn, sqlite3.Connection):
            cursor.execute(
                """SELECT * FROM evidence_item 
                   WHERE party_id = ? AND statement_id = ? AND document_id = ? AND verified = 0""",
                (submission.party_id, submission.statement_id, submission.document_id)
            )
            existing = cursor.fetchone()
        else:
            cursor.execute(
                """SELECT * FROM evidence_item 
                   WHERE party_id = %s AND statement_id = %s AND document_id = %s AND verified = 0""",
                (submission.party_id, submission.statement_id, submission.document_id)
            )
            existing = cursor.fetchone()

        if not existing:
            # First coder submission
            if isinstance(conn, sqlite3.Connection):
                cursor.execute(
                    """INSERT INTO evidence_item 
                       (party_id, statement_id, document_id, tier, direction, item_weight, evidence_date, extract, coder_a, verified) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                    (submission.party_id, submission.statement_id, submission.document_id, submission.tier, 
                     submission.direction, submission.item_weight, submission.evidence_date, submission.extract, submission.coder_name)
                )
                evidence_id = cursor.lastrowid
            else:
                cursor.execute(
                    """INSERT INTO evidence_item 
                       (party_id, statement_id, document_id, tier, direction, item_weight, evidence_date, extract, coder_a, verified) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE) RETURNING id""",
                    (submission.party_id, submission.statement_id, submission.document_id, submission.tier, 
                     submission.direction, submission.item_weight, submission.evidence_date, submission.extract, submission.coder_name)
                )
                evidence_id = cursor.fetchone()["id"]

            log_audit(conn, submission.coder_name, "SUBMIT_CODER_A", f"evidence:{evidence_id}", submission.model_dump())
            conn.commit()
            return {"status": "registered_first_coding", "evidence_id": evidence_id}

        else:
            # Second coder submission
            existing = dict(existing) if isinstance(conn, sqlite3.Connection) else existing
            evidence_id = existing["id"]
            coder_a = existing["coder_a"]
            direction_a = existing["direction"]
            
            if coder_a == submission.coder_name:
                raise HTTPException(status_code=400, detail="The same coder cannot submit coding twice for the same evidence item.")

            # Calculate disagreement
            disagreement = abs(direction_a - submission.direction)
            
            if disagreement <= 0.5:
                # Concordant coding -> automatically verify
                # Direction is the average of the two coders
                final_direction = (direction_a + submission.direction) / 2.0
                if isinstance(conn, sqlite3.Connection):
                    cursor.execute(
                        """UPDATE evidence_item 
                           SET coder_b = ?, direction = ?, verified = 1 
                           WHERE id = ?""",
                        (submission.coder_name, final_direction, evidence_id)
                    )
                else:
                    cursor.execute(
                        """UPDATE evidence_item 
                           SET coder_b = %s, direction = %s, verified = TRUE 
                           WHERE id = %s""",
                        (submission.coder_name, final_direction, evidence_id)
                    )
                
                log_audit(conn, "system", "AUTO_VERIFY", f"evidence:{evidence_id}", {
                    "coder_a": coder_a,
                    "coder_b": submission.coder_name,
                    "direction_a": direction_a,
                    "direction_b": submission.direction,
                    "final_direction": final_direction
                })
                conn.commit()
                return {"status": "auto_verified", "evidence_id": evidence_id, "final_direction": final_direction}
            else:
                # Disagree > 0.5 -> Escalate to methodology board
                if isinstance(conn, sqlite3.Connection):
                    cursor.execute(
                        """UPDATE evidence_item 
                           SET coder_b = ? 
                           WHERE id = ?""",
                        (submission.coder_name, evidence_id)
                    )
                else:
                    cursor.execute(
                        """UPDATE evidence_item 
                           SET coder_b = %s 
                           WHERE id = %s""",
                        (submission.coder_name, evidence_id)
                    )
                
                log_audit(conn, "system", "ESCALATE_TO_BOARD", f"evidence:{evidence_id}", {
                    "coder_a": coder_a,
                    "coder_b": submission.coder_name,
                    "direction_a": direction_a,
                    "direction_b": submission.direction,
                    "disagreement": disagreement
                })
                conn.commit()
                return {"status": "escalated_to_board", "evidence_id": evidence_id, "disagreement": disagreement}

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@app.get("/coding/escalations")
def get_escalations():
    """
    Returns unverified evidence items where both coders have submitted but they disagree > 0.5.
    """
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        # Escalated items have coder_b populated but verified = 0 (and the disagreement was flagged)
        if isinstance(conn, sqlite3.Connection):
            cursor.execute(
                "SELECT * FROM evidence_item WHERE coder_b IS NOT NULL AND verified = 0"
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        else:
            cursor.execute(
                "SELECT * FROM evidence_item WHERE coder_b IS NOT NULL AND verified = FALSE"
            )
            return cursor.fetchall()
    finally:
        conn.close()

@app.post("/coding/escalations/{evidence_id}/resolve")
def resolve_escalation(evidence_id: int, res: ResolutionSubmission):
    """
    Allows a board member to resolve an escalated coding conflict.
    Marks item as verified and records details in audit log.
    """
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor.execute("SELECT * FROM evidence_item WHERE id = ?", (evidence_id,))
            item = cursor.fetchone()
        else:
            cursor.execute("SELECT * FROM evidence_item WHERE id = %s", (evidence_id,))
            item = cursor.fetchone()

        if not item:
            raise HTTPException(status_code=404, detail="Evidence item not found")

        item = dict(item) if isinstance(conn, sqlite3.Connection) else item
        if item["verified"]:
            raise HTTPException(status_code=400, detail="Evidence item is already verified")

        if not item["coder_b"]:
            raise HTTPException(status_code=400, detail="Cannot resolve a non-escalated item (requires double coder entry first)")

        # Perform resolution update
        if isinstance(conn, sqlite3.Connection):
            cursor.execute(
                """UPDATE evidence_item 
                   SET direction = ?, resolution = ?, verified = 1 
                   WHERE id = ?""",
                (res.direction, res.resolution_notes, evidence_id)
            )
        else:
            cursor.execute(
                """UPDATE evidence_item 
                   SET direction = %s, resolution = %s, verified = TRUE 
                   WHERE id = %s""",
                (res.direction, res.resolution_notes, evidence_id)
            )

        log_audit(conn, res.board_member, "RESOLVE_ESCALATION", f"evidence:{evidence_id}", {
            "board_member": res.board_member,
            "original_coder_a": item["coder_a"],
            "original_coder_b": item["coder_b"],
            "original_direction_a": item["direction"],
            "resolved_direction": res.direction,
            "notes": res.resolution_notes
        })
        conn.commit()
        return {"status": "resolved", "evidence_id": evidence_id, "resolved_direction": res.direction}

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
