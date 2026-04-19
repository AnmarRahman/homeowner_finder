from scraper.sources.or_deschutes_taxlots import OregonDeschutesTaxlotsSource


def test_or_deschutes_map_record_builds_normalized_fields() -> None:
    source = OregonDeschutesTaxlotsSource()
    base = {"OBJECTID": 10, "TAXLOT": "123456", "MAPNUMBER": "18-11-01"}
    related = {
        source._REL_OWNERS: {10: {"NAME": "DOE JANE"}},
        source._REL_MAILING: {
            10: {
                "M_ADDRESS": "PO BOX 1",
                "M_CITYSTZIP": "BEND OR 97701",
            }
        },
        source._REL_PCSTAT: {10: {"STAT_CLASS_DESC": "Single Family Residence"}},
        source._REL_ROLLVALUES: {10: {"RMV_Land": 200000, "RMV_Impr": 300000}},
        source._REL_ASSESSOR_ACCOUNT: {
            10: {
                "Address": "123 NW PINE ST",
                "City": "BEND",
                "State": "OR",
                "Zip": "97701",
            }
        },
    }

    record = source._map_record(base, related, 10)

    assert record.owner_name == "DOE JANE"
    assert record.property_address == "123 NW PINE ST"
    assert record.mailing_address == "PO BOX 1, BEND, OR, 97701"
    assert record.city == "BEND"
    assert record.state == "OR"
    assert record.zip == "97701"
    assert record.parcel_id == "123456"
    assert record.property_type == "Single Family Residence"
    assert record.raw["estimated_home_value"] == "500000"
