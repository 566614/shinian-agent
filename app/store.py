from __future__ import annotations
import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

JSON_FIELDS = ("tags", "action_items", "people", "related_ids")

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    type TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    action_items TEXT NOT NULL DEFAULT '[]',
    people TEXT NOT NULL DEFAULT '[]',
    project TEXT,
    scene TEXT,
    location TEXT,
    status TEXT NOT NULL DEFAULT 'inbox',
    related_ids TEXT NOT NULL DEFAULT '[]',
    audio_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at DESC);
"""

UPDATABLE = {
    "title",
    "summary",
    "type",
    "tags",
    "action_items",
    "project",
    "status",
    "scene",
    "location",
}


class Store:
    """SQLite 存储。单文件、零依赖，方便比赛现场与本地演示。"""

    def __init__(self, path: str, tz: str = "Asia/Shanghai") -> None:
        self.tz = ZoneInfo(tz)
        if path != ":memory:":
            parent = os.path.dirname(os.path.abspath(path))
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def now(self) -> str:
        return datetime.now(self.tz).isoformat(timespec="seconds")

    def _row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for field in JSON_FIELDS:
            raw = data.get(field)
            try:
                data[field] = json.loads(raw) if raw else []
            except (TypeError, json.JSONDecodeError):
                data[field] = []
        return data

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "created_at": data.get("created_at") or self.now(),
            "raw_text": data["raw_text"],
            "title": data["title"],
            "summary": data["summary"],
            "type": data["type"],
            "tags": json.dumps(data.get("tags") or [], ensure_ascii=False),
            "action_items": json.dumps(data.get("action_items") or [], ensure_ascii=False),
            "people": json.dumps(data.get("people") or [], ensure_ascii=False),
            "project": data.get("project"),
            "scene": data.get("scene"),
            "location": data.get("location"),
            "status": data.get("status") or "inbox",
            "related_ids": json.dumps(data.get("related_ids") or [], ensure_ascii=False),
            "audio_path": data.get("audio_path"),
        }
        keys = ", ".join(payload)
        marks = ", ".join("?" for _ in payload)
        with self._lock:
            cur = self._conn.execute(
                f"INSERT INTO notes ({keys}) VALUES ({marks})", tuple(payload.values())
            )
            self._conn.commit()
            note_id = int(cur.lastrowid)
        return self.get(note_id)

    def get(self, note_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return self._row(row) if row else None

    def list(
        self,
        q: str = "",
        type: str = "",
        status: str = "",
        limit: int = 50,
        offset: int = 0,
        since: str = "",
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM notes WHERE 1 = 1"
        args: list[Any] = []
        if q:
            sql += " AND (title LIKE ? OR summary LIKE ? OR raw_text LIKE ? OR tags LIKE ?)"
            like = f"%{q}%"
            args.extend([like, like, like, like])
        if type:
            sql += " AND type = ?"
            args.append(type)
        if status:
            sql += " AND status = ?"
            args.append(status)
        if since:
            sql += " AND created_at >= ?"
            args.append(since)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
        args.extend([max(1, min(limit, 500)), max(0, offset)])
        with self._lock:
            rows = self._conn.execute(sql, tuple(args)).fetchall()
        return [self._row(r) for r in rows]

    def recent(self, limit: int = 200) -> list[dict[str, Any]]:
        return self.list(limit=limit)

    def update(self, note_id: int, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        sets, args = [], []
        for key, value in fields.items():
            if key not in UPDATABLE or value is None:
                continue
            if key in ("tags", "action_items"):
                value = json.dumps(value, ensure_ascii=False)
            sets.append(f"{key} = ?")
            args.append(value)
        if not sets:
            return self.get(note_id)
        args.append(note_id)
        with self._lock:
            self._conn.execute(f"UPDATE notes SET {', '.join(sets)} WHERE id = ?", tuple(args))
            self._conn.commit()
        return self.get(note_id)

    def delete(self, note_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            self._conn.commit()
        return cur.rowcount > 0

    def count(self, since: str = "") -> int:
        sql, args = "SELECT COUNT(*) AS c FROM notes", []
        if since:
            sql += " WHERE created_at >= ?"
            args.append(since)
        with self._lock:
            row = self._conn.execute(sql, tuple(args)).fetchone()
        return int(row["c"])
