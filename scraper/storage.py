from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from scraper.models import PropertyRecord


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS property_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_name TEXT,
    property_address TEXT,
    mailing_address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    parcel_id TEXT,
    property_type TEXT,
    source_url TEXT,
    raw_json TEXT
);
"""


class SQLiteStorage:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, records: Iterable[PropertyRecord]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.executemany(
                """
                INSERT INTO property_results (
                    owner_name, property_address, mailing_address, city, state,
                    zip, parcel_id, property_type, source_url, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record.owner_name,
                        record.property_address,
                        record.mailing_address,
                        record.city,
                        record.state,
                        record.zip,
                        record.parcel_id,
                        record.property_type,
                        record.source_url,
                        json.dumps(record.raw, ensure_ascii=False),
                    )
                    for record in records
                ],
            )
            conn.commit()
