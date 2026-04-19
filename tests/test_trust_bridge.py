from scraper.models import PropertyRecord
from scraper.trust_bridge import (
    TrustBridgeOptions,
    build_trust_bridge_leads,
    infer_intent_tags,
    map_property_record,
    normalize_phone,
)


def test_normalize_phone_formats_dialable_number() -> None:
    assert normalize_phone("1-310-555-1212") == "(310) 555-1212"


def test_map_property_record_infers_required_fields() -> None:
    record = PropertyRecord(
        owner_name="Jane Doe",
        property_address="123 Main St",
        mailing_address="123 Main St",
        city="Los Angeles",
        state="CA",
        zip="90001",
        property_type="Single Family Residence",
        parcel_id="APN-1",
        source_url="mock://source",
        raw={"estimated_home_value": "850000"},
    )

    lead = map_property_record(record=record, source_key="la_open_data")
    assert lead.full_name == "Jane Doe"
    assert lead.state == "CA"
    assert lead.property_type == "single_family"
    assert lead.owner_occupied == "yes"


def test_build_trust_bridge_leads_filters_non_matching_rows() -> None:
    allowed = PropertyRecord(
        owner_name="Owner One",
        property_address="100 Oak St",
        mailing_address="100 Oak St",
        city="Portland",
        state="OR",
        zip="97201",
        property_type="Townhouse",
        raw={"phone_number": "(503) 444-1234"},
    )
    blocked = PropertyRecord(
        owner_name="",
        property_address="200 Market St",
        city="Miami",
        state="FL",
        property_type="Commercial Office",
        raw={"phone_number": "(305) 444-1234"},
    )

    leads = build_trust_bridge_leads(
        source_to_records={"mock": [allowed, blocked]},
        final_limit=10,
        options=TrustBridgeOptions(allowed_states=("CA", "OR"), require_dialable_phone=True),
    )

    assert len(leads) == 1
    assert leads[0].state == "OR"
    assert leads[0].full_name == "Owner One"


def test_infer_intent_tags_from_raw_text() -> None:
    record = PropertyRecord(
        owner_name="Owner",
        property_address="500 Pine St",
        state="CA",
        property_type="Single Family",
        raw={"permit_desc": "Kitchen remodel and roofing replacement"},
    )

    tags = infer_intent_tags(record)
    assert "kitchen_remodeling" in tags
    assert "roofing" in tags


def test_build_trust_bridge_leads_deduplicates_same_owner_address_diff_phone() -> None:
    records = [
        PropertyRecord(
            owner_name="Jane Doe",
            property_address="123 Main St",
            mailing_address="123 Main St",
            city="Portland",
            state="OR",
            zip="97201",
            property_type="Single Family Residence",
            parcel_id="",
            raw={"phone_number": "503-444-1234"},
        ),
        PropertyRecord(
            owner_name="Jane Doe",
            property_address="123 Main St",
            mailing_address="123 Main St",
            city="Portland",
            state="OR",
            zip="97201",
            property_type="Single Family Residence",
            parcel_id="",
            raw={"phone_number": "503-444-5678"},
        ),
    ]

    leads = build_trust_bridge_leads(
        source_to_records={"mock": records},
        final_limit=10,
        options=TrustBridgeOptions(allowed_states=("OR",), require_dialable_phone=True),
    )

    assert len(leads) == 1


def test_or_property_class_4xx_infers_residential() -> None:
    record = PropertyRecord(
        owner_name="Owner",
        property_address="1 Pine St",
        city="Bend",
        state="OR",
        property_type="",
        raw={"pcstat": {"PROPERTY_CLASS": "401", "STAT_CLASS": "143"}},
    )

    lead = map_property_record(record=record, source_key="or_deschutes_taxlots")
    assert lead.property_type == "single_family"


def test_build_trust_bridge_leads_deduplicates_by_parcel_id() -> None:
    records = [
        PropertyRecord(
            owner_name="Owner A",
            property_address="100 Oak St",
            mailing_address="100 Oak St",
            city="Bend",
            state="OR",
            zip="97701",
            parcel_id="TL-0001",
            property_type="Single Family Residence",
            raw={"phone_number": "541-444-1111"},
        ),
        PropertyRecord(
            owner_name="Owner B",
            property_address="100 Oak Street",
            mailing_address="PO BOX 1",
            city="Bend",
            state="OR",
            zip="97701",
            parcel_id="TL-0001",
            property_type="Single Family Residence",
            raw={"phone_number": "541-444-2222"},
        ),
    ]

    leads = build_trust_bridge_leads(
        source_to_records={"or_deschutes_taxlots": records},
        final_limit=10,
        options=TrustBridgeOptions(allowed_states=("OR",), require_dialable_phone=True),
    )
    assert len(leads) == 1


def test_map_property_record_respects_ownocc_flag() -> None:
    record = PropertyRecord(
        owner_name="Owner",
        property_address="1 Pine St",
        mailing_address="PO BOX 1",
        city="Eureka",
        state="CA",
        property_type="Improved Single Family Residential",
        raw={"OWNOCC": "Y"},
    )
    lead = map_property_record(record=record, source_key="ca_humboldt_parcels")
    assert lead.owner_occupied == "yes"


def test_build_trust_bridge_leads_enriches_phone_from_free_lookup(monkeypatch) -> None:
    def fake_lookup(**_: object) -> dict[str, object]:
        return {
            "phones": [
                {
                    "number": "(503) 444-1234",
                    "confidence": 92,
                    "sources": ["unit-test"],
                }
            ],
            "errors": [],
        }

    monkeypatch.setattr("scraper.trust_bridge.lookup_free_phones", fake_lookup)

    record = PropertyRecord(
        owner_name="Owner One",
        property_address="100 Oak St",
        mailing_address="100 Oak St",
        city="Portland",
        state="OR",
        zip="97201",
        property_type="Townhouse",
        raw={},
    )

    leads = build_trust_bridge_leads(
        source_to_records={"mock": [record]},
        final_limit=10,
        options=TrustBridgeOptions(
            allowed_states=("OR",),
            require_dialable_phone=True,
            free_phone_lookup_enabled=True,
            free_phone_lookup_use_browser=False,
        ),
    )

    assert len(leads) == 1
    assert leads[0].phone_number == "(503) 444-1234"
