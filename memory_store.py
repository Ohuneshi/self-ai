from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

class MemoryStore:
    KEYS = ("episodic","semantic","self_model","internal_state","goals","strategy")
    def __init__(self):
        self.db_url = os.getenv("TURSO_DATABASE_URL", "").strip()
        self.auth_token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
        self.local_path = Path(os.getenv("SQLITE_PATH", "data/self_ai.sqlite3"))
        self.seed_dir = Path(__file__).resolve().parent / "seed_memory"
        if not self.db_url:
            self.local_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self):
        if self.db_url:
            import turso_serverless
            return turso_serverless.connect(self.db_url, auth_token=self.auth_token)
        conn = sqlite3.connect(self.local_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self):
        conn = self._connect()
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS memory_state (user_id TEXT NOT NULL, key TEXT NOT NULL, value_json TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(user_id,key))")
            conn.commit()
        finally:
            conn.close()

    def ensure_user(self, user_id: str):
        self.ensure_schema()
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) FROM memory_state WHERE user_id = ?", (user_id,)).fetchone()
            count = row[0]
            if count:
                return
            defaults = {}
            for key in self.KEYS:
                path = self.seed_dir / f"{key}.json"
                if path.exists():
                    try:
                        defaults[key] = json.loads(path.read_text(encoding="utf-8"))
                    except Exception:
                        defaults[key] = [] if key in ("episodic","semantic") else {}
                else:
                    defaults[key] = [] if key in ("episodic","semantic") else {}
            import datetime
            ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
            for key, value in defaults.items():
                conn.execute("INSERT INTO memory_state(user_id,key,value_json,updated_at) VALUES(?,?,?,?)", (user_id,key,json.dumps(value,ensure_ascii=False),ts))
            conn.commit()
        finally:
            conn.close()

def load_state(self, user_id: str, fallback: dict[str, Any]) -> dict[str, Any]:
    print("DEBUG USER ID:", user_id)

    self.ensure_user(user_id)
    conn = self._connect()        try:
            out = {}
            for row in conn.execute("SELECT key, value_json FROM memory_state WHERE user_id = ?", (user_id,)).fetchall():
                key, raw = (row["key"], row["value_json"]) if hasattr(row, "keys") else row
                out[key] = json.loads(raw)
            for key, val in fallback.items():
                out.setdefault(key, val)
            return out
        finally:
            conn.close()

    def save_state(self, user_id: str, state: dict[str, Any]):
        conn = self._connect()
        try:
            import datetime
            ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
            for key in self.KEYS:
                if key not in state:
                    continue
                value = json.dumps(state[key], ensure_ascii=False)
                conn.execute("INSERT INTO memory_state(user_id,key,value_json,updated_at) VALUES(?,?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at", (user_id,key,value,ts))
            conn.commit()
        finally:
            conn.close()
