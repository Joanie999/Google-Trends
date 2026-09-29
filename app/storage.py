"""本地 SQLite 存储：Amazon 关键词、趋势快照和更新计划。"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Storage:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or ROOT / "data" / "trendscope.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS amazon_keywords (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              keyword TEXT NOT NULL, normalized TEXT NOT NULL,
              search_volume REAL, rank REAL, competition TEXT, asin TEXT,
              imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trend_snapshots (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_json TEXT NOT NULL, result_json TEXT NOT NULL,
              fetched_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS schedules (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              keywords_json TEXT NOT NULL, geo TEXT NOT NULL,
              timeframe TEXT NOT NULL, gprop TEXT NOT NULL,
              interval_days INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
              next_run TEXT NOT NULL, last_run TEXT, last_status TEXT
            );
            """)

    def replace_amazon(self, rows: list[dict]) -> int:
        now = datetime.now(UTC).isoformat()
        with self.lock, self._connect() as conn:
            conn.execute("DELETE FROM amazon_keywords")
            conn.executemany(
                "INSERT INTO amazon_keywords(keyword, normalized, search_volume, rank, competition, asin, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        r["keyword"],
                        r.get("normalized", ""),
                        r.get("search_volume"),
                        r.get("rank"),
                        r.get("competition", ""),
                        r.get("asin", ""),
                        now,
                    )
                    for r in rows
                ],
            )
        return len(rows)

    def amazon(self) -> list[dict]:
        with self._connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT keyword, normalized, search_volume, rank, competition, asin, imported_at FROM amazon_keywords ORDER BY id"
                )
            ]

    def save_snapshot(self, request: dict, result: dict):
        with self.lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO trend_snapshots(request_json, result_json, fetched_at) VALUES (?, ?, ?)",
                (
                    json.dumps(request, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False),
                    result.get("fetched_at", datetime.now(UTC).isoformat()),
                ),
            )

    def history(self, limit=30) -> list[dict]:
        with self._connect() as conn:
            return [
                {
                    "id": row["id"],
                    "request": json.loads(row["request_json"]),
                    "fetched_at": row["fetched_at"],
                }
                for row in conn.execute(
                    "SELECT id, request_json, fetched_at FROM trend_snapshots ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            ]

    def add_schedule(self, request: dict, interval_days: int) -> dict:
        if interval_days not in (3, 7):
            raise ValueError("更新周期只能是 3 天或 7 天")
        now = datetime.now(UTC)
        next_run = now + timedelta(days=interval_days)
        with self.lock, self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO schedules(keywords_json, geo, timeframe, gprop, interval_days, next_run, last_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    json.dumps(request["keywords"], ensure_ascii=False),
                    request["geo"],
                    request["timeframe"],
                    request["gprop"],
                    interval_days,
                    next_run.isoformat(),
                    "pending",
                ),
            )
            schedule_id = cur.lastrowid
        return self.schedule(schedule_id)

    def schedules(self) -> list[dict]:
        with self._connect() as conn:
            return [
                self._schedule_row(row)
                for row in conn.execute("SELECT * FROM schedules ORDER BY id DESC")
            ]

    def schedule(self, schedule_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
            ).fetchone()
            return self._schedule_row(row) if row else None

    def delete_schedule(self, schedule_id: int) -> bool:
        with self.lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        return cur.rowcount > 0

    def due_schedules(self) -> list[dict]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            return [
                self._schedule_row(row)
                for row in conn.execute(
                    "SELECT * FROM schedules WHERE enabled = 1 AND next_run <= ?",
                    (now,),
                )
            ]

    def mark_schedule(self, schedule_id: int, status: str, interval_days: int):
        now = datetime.now(UTC)
        next_run = now + timedelta(days=interval_days)
        with self.lock, self._connect() as conn:
            conn.execute(
                "UPDATE schedules SET next_run = ?, last_run = ?, last_status = ? WHERE id = ?",
                (next_run.isoformat(), now.isoformat(), status, schedule_id),
            )

    @staticmethod
    def _schedule_row(row):
        if not row:
            return None
        return {
            "id": row["id"],
            "keywords": json.loads(row["keywords_json"]),
            "geo": row["geo"],
            "timeframe": row["timeframe"],
            "gprop": row["gprop"],
            "interval_days": row["interval_days"],
            "enabled": bool(row["enabled"]),
            "next_run": row["next_run"],
            "last_run": row["last_run"],
            "last_status": row["last_status"],
        }
