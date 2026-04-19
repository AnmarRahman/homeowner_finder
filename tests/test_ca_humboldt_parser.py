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
