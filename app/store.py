"""SQLite persistence, including an exact cosine vector store for a small classroom corpus."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np


def now():
    """Return a timezone-aware UTC ISO timestamp for persisted records and events."""
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Persist classroom documents, dense vectors, sessions, runs, and trace events.

    Each operation opens a short-lived SQLite connection with foreign keys enabled.
    Vectors are normalized by Embedder before insertion; search uses an exact NumPy
    scan over the selected corpus rather than an approximate vector index.
    """

    def __init__(self, path):
        """Create the parent directory and initialize the SQLite schema in WAL mode."""
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                  id TEXT PRIMARY KEY, name TEXT, digest TEXT UNIQUE, pages INTEGER,
                  chunks INTEGER, model TEXT, created_at TEXT);
                CREATE TABLE IF NOT EXISTS chunks (
                  id TEXT PRIMARY KEY, document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
                  page INTEGER, position INTEGER, start INTEGER, end INTEGER,
                  text TEXT, vector BLOB);
                CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
                CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created_at TEXT);
                CREATE TABLE IF NOT EXISTS messages (
                  seq INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT REFERENCES sessions(id),
                  role TEXT, content TEXT, run_id TEXT);
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id), query TEXT,
                  status TEXT, created_at TEXT, result TEXT);
                CREATE TABLE IF NOT EXISTS events (
                  seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT REFERENCES runs(id), payload TEXT);
            """)

    @contextmanager
    def connect(self):
        """Yield a row-mapped connection that commits or rolls back, then closes."""
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def documents(self):
        """Return document metadata newest first, excluding chunk text and vectors."""
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM documents ORDER BY created_at DESC")]

    def insert_document(self, doc, chunks, vectors):
        """Atomically insert metadata, chunks, and their normalized float32 vectors.

        Return ``(metadata, created)``; an existing digest returns its original
        record and False. A chunk/vector count mismatch raises ValueError and
        rolls back the transaction instead of leaving a partially indexed document.
        """
        with self.connect() as db:
            previous = db.execute("SELECT * FROM documents WHERE digest=?", (doc["digest"],)).fetchone()
            if previous:
                return dict(previous), False
            db.execute(
                "INSERT INTO documents VALUES (:id,:name,:digest,:pages,:chunks,:model,:created_at)", doc
            )
            db.executemany(
                "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?)",
                [
                    (
                        uuid4().hex,
                        doc["id"],
                        c["page"],
                        i,
                        c["start"],
                        c["end"],
                        c["text"],
                        np.asarray(v, dtype=np.float32).tobytes(),
                    )
                    for i, (c, v) in enumerate(zip(chunks, vectors, strict=True))
                ],
            )
        return doc, True

    def delete_document(self, doc_id):
        """Delete one document and cascade its chunks; return whether it existed."""
        with self.connect() as db:
            return db.execute("DELETE FROM documents WHERE id=?", (doc_id,)).rowcount > 0

    def document_chunks(self, doc_id):
        """Return ordered source slices and offsets for inspection, without vectors."""
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,page,position,start,end,text FROM chunks WHERE document_id=? ORDER BY position",
                    (doc_id,),
                )
            ]

    def search(self, vector, top_k, model, minimum, document_ids=()):
        """Return up to top_k cosine-ranked chunks with evidence and citation IDs.

        Filter by embedding model and optional document IDs, normalize the query,
        and score against stored normalized vectors. Keep only scores at least
        ``minimum`` and assign run-local S1, S2, ... labels in ranked order.
        Incompatible vector dimensions raise ValueError and require reindexing.
        """
        with self.connect() as db:
            sql = "SELECT c.*,d.name,d.model FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.model=?"
            args = [model]
            if document_ids:
                sql += " AND d.id IN (" + ",".join("?" for _ in document_ids) + ")"
                args.extend(document_ids)
            rows = db.execute(sql, args).fetchall()
        if not rows:
            return []
        query = np.asarray(vector, dtype=np.float32)
        query = query / max(float(np.linalg.norm(query)), 1e-12)
        matrix = np.vstack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows])
        if matrix.shape[1] != query.size:
            raise ValueError("Embedding dimensions changed. Delete and re-upload the documents.")
        scores = matrix @ query
        indices = np.argsort(-scores, kind="stable")[:top_k]
        return [
            dict(
                id=rows[i]["id"],
                document_id=rows[i]["document_id"],
                name=rows[i]["name"],
                page=rows[i]["page"],
                position=rows[i]["position"],
                text=rows[i]["text"],
                score=round(float(scores[i]), 4),
                citation=f"S{j + 1}",
            )
            for j, i in enumerate(indices)
            if scores[i] >= minimum
        ]

    def create_session(self):
        """Persist an empty conversation and return its random hexadecimal ID."""
        sid = uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO sessions VALUES (?,?)", (sid, now()))
        return sid

    def session_exists(self, sid):
        """Check whether a conversation ID has been created."""
        with self.connect() as db:
            return db.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone() is not None

    def history(self, sid, limit=12):
        """Return the most recent messages in chronological order for one session."""
        with self.connect() as db:
            rows = db.execute(
                "SELECT role,content,run_id FROM messages WHERE session_id=? ORDER BY seq DESC LIMIT ?",
                (sid, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def create_run(self, sid, query):
        """Persist a queued question and return its ID before background execution."""
        rid = uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)", (rid, sid, query, "queued", now(), None))
        return rid

    def get_run(self, rid):
        """Return decoded result and ordered trace events, or None for an unknown run."""
        with self.connect() as db:
            r = db.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
        if not r:
            return None
        result = dict(r)
        result["result"] = json.loads(result["result"]) if result["result"] else None
        result["events"] = self.events(rid)
        return result

    def update_run(self, rid, status, result=None):
        """Replace a run's status and JSON result, including terminal failure details."""
        with self.connect() as db:
            db.execute("UPDATE runs SET status=?,result=? WHERE id=?", (status, json.dumps(result), rid))

    def save_turn(self, sid, query, answer, rid):
        """Atomically append the user question and final assistant answer to history."""
        with self.connect() as db:
            db.executemany(
                "INSERT INTO messages(session_id,role,content,run_id) VALUES (?,?,?,?)",
                [(sid, "user", query, rid), (sid, "assistant", answer, rid)],
            )

    def event(self, rid, payload):
        """Persist a trace payload and return its monotonically increasing cursor."""
        with self.connect() as db:
            cursor = db.execute("INSERT INTO events(run_id,payload) VALUES (?,?)", (rid, json.dumps(payload)))
            return cursor.lastrowid

    def events(self, rid, after=0):
        """Read one run's events after an exclusive cursor for ordered SSE replay."""
        with self.connect() as db:
            return [
                {"id": r["seq"], **json.loads(r["payload"])}
                for r in db.execute(
                    "SELECT seq,payload FROM events WHERE run_id=? AND seq>? ORDER BY seq", (rid, after)
                )
            ]

    def recover_runs(self):
        """Mark queued/running work as failed after restart; tasks cannot be resumed."""
        with self.connect() as db:
            db.execute(
                "UPDATE runs SET status='failed', result=? WHERE status IN ('queued','running')",
                (json.dumps({"error": "Server restarted during this run. Please retry."}),),
            )
