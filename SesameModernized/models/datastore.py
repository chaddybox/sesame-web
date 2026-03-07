from __future__ import annotations
import sqlite3, csv, os
from pathlib import Path

DB_PATH = Path("./sesame.db")

class DataStore:
    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        self._ensure_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_db(self):
        with self._connect() as con:
            cur = con.cursor()
            # Minimal example table; replace with your real schema
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    value REAL,
                    note TEXT
                )
                """
            )
            con.commit()

    # ---------- Import/Export ----------
    def import_csv(self, csv_path: str) -> int:
        if not os.path.exists(csv_path):
            raise FileNotFoundError(csv_path)
        inserted = 0
        with open(csv_path, newline="", encoding="utf-8") as f, self._connect() as con:
            reader = csv.DictReader(f)
            cols = [c.lower() for c in reader.fieldnames or []]
            # Expecting columns: name, value, note (case-insensitive)
            for row in reader:
                name = row.get("name") or row.get("Name") or ""
                try:
                    value = float(row.get("value") or row.get("Value") or 0.0)
                except Exception:
                    value = 0.0
                note = row.get("note") or row.get("Note") or ""
                con.execute("INSERT INTO records(name, value, note) VALUES(?,?,?)", (name, value, note))
                inserted += 1
            con.commit()
        return inserted

    def export_csv(self, csv_path: str) -> int:
        with self._connect() as con, open(csv_path, "w", newline="", encoding="utf-8") as f:
            cur = con.cursor()
            cur.execute("SELECT id, name, value, note FROM records ORDER BY id ASC")
            rows = cur.fetchall()
            writer = csv.writer(f)
            writer.writerow(["id", "name", "value", "note"])
            for r in rows:
                writer.writerow(r)
        return len(rows)

    # ---------- Queries ----------
    def count_rows(self) -> int:
        with self._connect() as con:
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM records")
            (n,) = cur.fetchone()
            return int(n)
