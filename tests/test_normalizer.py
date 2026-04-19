from scraper.normalizer import clean_text, normalize_record


def test_clean_text_handles_none_and_whitespace() -> None:
    assert clean_text(None) == ""
    assert clean_text("  abc\n") == "abc"


def test_normalize_record_defaults_state_to_ca() -> None:
    record = normalize_record({}, owner_name="Jane Doe")
    assert record.owner_name == "Jane Doe"
    assert record.state == "CA"
