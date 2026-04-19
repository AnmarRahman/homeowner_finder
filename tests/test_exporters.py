from pathlib import Path

from scraper.exporters import export_csv, export_json
from scraper.models import PropertyRecord


SAMPLE = [
    PropertyRecord(owner_name="Jane Doe", property_address="123 Main St", source_url="mock://1", raw={"a": 1})
]


def test_export_csv(tmp_path: Path) -> None:
    output = tmp_path / "results.csv"
    export_csv(SAMPLE, output)
    text = output.read_text(encoding="utf-8")
    assert "owner_name" in text
    assert "Jane Doe" in text


def test_export_json(tmp_path: Path) -> None:
    output = tmp_path / "results.json"
    export_json(SAMPLE, output)
    text = output.read_text(encoding="utf-8")
    assert "Jane Doe" in text
