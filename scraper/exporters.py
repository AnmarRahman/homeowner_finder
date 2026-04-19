from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from scraper.models import PropertyRecord

FIELDS = [
    "owner_name",
    "property_address",
    "mailing_address",
    "city",
    "state",
    "zip",
    "parcel_id",
    "property_type",
    "source_url",
    "raw",
]


def export_csv(records: Iterable[PropertyRecord], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for record in records:
            row = record.to_dict()
            row["raw"] = json.dumps(row["raw"], ensure_ascii=False)
            writer.writerow(row)
    return path


def export_json(records: Iterable[PropertyRecord], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [record.to_dict() for record in records]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
