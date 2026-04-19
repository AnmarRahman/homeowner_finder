import pytest
import requests

from scraper.models import PropertyRecord
from scraper.sources.ca_humboldt_parcels import CaliforniaHumboldtParcelsSource


def test_ca_humboldt_map_record_builds_owner_and_value() -> None:
    source = CaliforniaHumboldtParcelsSource()
    raw = {
        "APN_12": "109-061-042-000",
        "NAME": "Lair Buddy A & Lair Antonette",
        "FULLADDR": "13 MILL CREEK RD",
        "SITCITY": "SHELTER COVE",
        "SITZIP": "95589",
        "ADDRESS1": "",
        "ADDRESS2": "14 Millcreek Rd",
        "ADDRESS3": "",
        "CITY": "Whitethorn",
        "STATE": "CA",
        "ZIP": "95589",
        "DESCRIPTIO": "Improved Single Family Residential",
        "LAND": 51325,
        "IMPR": 231517,
        "OWNOCC": "Y",
    }

    record = source._map_record(raw)

    assert record.owner_name == "Lair Buddy A & Lair Antonette"
    assert record.property_address == "13 MILL CREEK RD"
    assert record.mailing_address == "14 Millcreek Rd, Whitethorn, CA, 95589"
    assert record.city == "SHELTER COVE"
    assert record.state == "CA"
    assert record.zip == "95589"
    assert record.parcel_id == "109-061-042-000"
    assert record.property_type == "Improved Single Family Residential"
    assert record.raw["estimated_home_value"] == "282842"


def test_ca_humboldt_fetch_returns_partial_records_on_late_timeout(monkeypatch) -> None:
    source = CaliforniaHumboldtParcelsSource()
    calls = {"count": 0}

    def fake_fetch_page(*, page_size: int, offset: int, city: str | None):
        calls["count"] += 1
        if calls["count"] == 1:
            return [{"NAME": "Owner 1"}]
        raise requests.ReadTimeout("timeout")

    monkeypatch.setattr(source, "_fetch_page", fake_fetch_page)
    monkeypatch.setattr(
        source,
        "_map_record",
        lambda raw: PropertyRecord(owner_name=str(raw.get("NAME", "")), state="CA", raw=raw),
    )

    records = source.fetch(limit=5, city=None)
    assert len(records) == 1
    assert records[0].owner_name == "Owner 1"


def test_ca_humboldt_fetch_raises_when_first_page_keeps_timing_out(monkeypatch) -> None:
    source = CaliforniaHumboldtParcelsSource()

    def always_timeout(*, page_size: int, offset: int, city: str | None):
        raise requests.ReadTimeout("timeout")

    monkeypatch.setattr(source, "_fetch_page", always_timeout)
    with pytest.raises(requests.ReadTimeout):
        source.fetch(limit=5, city=None)
