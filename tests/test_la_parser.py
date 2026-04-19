from scraper.sources.la_open_data import LAOpenDataSource


def test_la_map_record_uses_configured_fields() -> None:
    source = LAOpenDataSource()
    raw = {
        "owner_name": "DOE JOHN",
        "property_address": "100 MAIN ST",
        "mailing_address": "PO BOX 9",
        "city": "LOS ANGELES",
        "state": "CA",
        "zip": "90001",
        "parcel_id": "999-999-999",
        "property_type": "Single Family Residence",
    }

    record = source._map_record(raw)

    assert record.owner_name == "DOE JOHN"
    assert record.property_address == "100 MAIN ST"
    assert record.mailing_address == "PO BOX 9"
    assert record.city == "LOS ANGELES"
    assert record.state == "CA"
    assert record.zip == "90001"
    assert record.parcel_id == "999-999-999"
    assert record.property_type == "Single Family Residence"
