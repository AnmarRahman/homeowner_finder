from scraper.free_phone_lookup import (
    PhoneHit,
    extract_duckduckgo_links,
    extract_phone_hits_from_text,
    normalize_phone_candidate,
    rank_phone_hits,
)


def test_normalize_phone_candidate_formats_valid_numbers() -> None:
    assert normalize_phone_candidate("1-503-444-1234") == "(503) 444-1234"
    assert normalize_phone_candidate("123-456-7890") == ""


def test_extract_phone_hits_from_text_returns_context_and_source() -> None:
    hits = extract_phone_hits_from_text(
        "Contact John Doe at (503) 444-1234 in Portland OR.",
        source="snippet",
    )
    assert len(hits) == 1
    assert hits[0].number == "(503) 444-1234"
    assert hits[0].source == "snippet"


def test_extract_duckduckgo_links_parses_redirect_targets() -> None:
    html = (
        '<a href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Ftruepeoplesearch.com%2Fabc"></a>'
    )
    links = extract_duckduckgo_links(html)
    assert links == ["https://truepeoplesearch.com/abc"]


def test_rank_phone_hits_scores_multi_source_match_higher() -> None:
    hits = [
        PhoneHit(
            number="(503) 444-1234",
            source="web:truepeoplesearch.com",
            context="John Doe 100 Oak St Portland OR (503) 444-1234",
        ),
        PhoneHit(
            number="(503) 444-1234",
            source="browser:thatsthem.com",
            context="Owner John Doe at 100 Oak St Portland OR",
        ),
        PhoneHit(
            number="(541) 333-2222",
            source="web:fastpeoplesearch.com",
            context="Portland OR unknown contact",
        ),
    ]
    ranked = rank_phone_hits(
        hits=hits,
        full_name="John Doe",
        property_address="100 Oak St",
        city="Portland",
        state="OR",
        max_candidates=5,
    )
    assert ranked[0]["number"] == "(503) 444-1234"
    assert ranked[0]["confidence"] >= ranked[1]["confidence"]
