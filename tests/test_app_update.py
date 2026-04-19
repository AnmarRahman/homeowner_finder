from scraper.app_update import is_newer_version, parse_version


def test_parse_version_extracts_numeric_triplet() -> None:
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("v2.0") == (2, 0, 0)
    assert parse_version("3") == (3, 0, 0)


def test_is_newer_version_compares_semver_like_values() -> None:
    assert is_newer_version("1.0.1", "1.0.0")
    assert is_newer_version("1.2.0", "1.1.9")
    assert not is_newer_version("1.0.0", "1.0.0")
    assert not is_newer_version("1.0.0", "1.0.1")
