from __future__ import annotations

from scraper.models import PropertyRecord
from scraper.normalizer import normalize_record
from scraper.sources.base import PropertySource


class MockPropertySource(PropertySource):
    key = "mock"
    label = "Mock California Sample Data"

    def fetch(self, limit: int, city: str | None = None) -> list[PropertyRecord]:
        target_city = city or "Los Angeles"
        records: list[PropertyRecord] = []
        for i in range(1, limit + 1):
            raw = {
                "owner": f"Sample Owner {i}",
                "property_address": f"{1000 + i} Example Ave",
                "mailing_address": f"PO Box {2000 + i}",
                "city": target_city,
                "state": "CA",
                "zip": f"9{i:04d}"[-5:],
                "parcel_id": f"MOCK-{i:06d}",
                "property_type": "Single Family Residential",
            }
            records.append(
                normalize_record(
                    raw,
                    owner_name=raw["owner"],
                    property_address=raw["property_address"],
                    mailing_address=raw["mailing_address"],
                    city=raw["city"],
                    state=raw["state"],
                    zip_code=raw["zip"],
                    parcel_id=raw["parcel_id"],
                    property_type=raw["property_type"],
                    source_url="mock://sample-data",
                )
            )
        return records
