from scraper.sources.broward_bcpa import BrowardBCPASource


def test_broward_map_record_builds_addresses() -> None:
    source = BrowardBCPASource()
    raw = {
        "FOLIO": "12345678901234",
        "NAME_LINE_": "DOE JOHN",
        "NAME_LINE1": "DOE JANE",
        "ADDRESS_LI": "123 MAIL RD",
        "CITY": "FORT LAUDERDALE",
        "STATE": "FL",
        "ZIP": "33301",
        "SITUS_STRE": "456",
        "SITUS_ST_2": "N",
        "SITUS_ST_4": "MAIN",
        "SITUS_ST_5": "ST",
        "SITUS_UNIT": "5",
    }

    record = source._map_record(raw)

    assert record.owner_name == "DOE JOHN DOE JANE"
    assert record.property_address == "456 N MAIN ST 5"
    assert record.mailing_address == "123 MAIL RD, FORT LAUDERDALE, FL, 33301"
    assert record.parcel_id == "12345678901234"
    assert record.city == "FORT LAUDERDALE"
    assert record.state == "FL"
    assert record.zip == "33301"
