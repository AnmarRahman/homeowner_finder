from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse

import requests

from scraper.normalizer import clean_text

PEOPLE_SEARCH_DOMAINS = (
    "truepeoplesearch.com",
    "fastpeoplesearch.com",
    "thatsthem.com",
    "whitepages.com",
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
PHONE_PATTERN = re.compile(
    r"(?:(?:\+?1[\s.\-]?)?\(?([2-9]\d{2})\)?[\s.\-]?([2-9]\d{2})[\s.\-]?(\d{4}))"
)
RESULT_LINK_PATTERN = re.compile(
    r'href="https?://duckduckgo.com/l/\?uddg=([^"&]+)', re.IGNORECASE
)


@dataclass(frozen=True, slots=True)
class PhoneHit:
    number: str
    source: str
    context: str


def lookup_free_phones(
    *,
    full_name: str,
    property_address: str,
    city: str,
    state: str,
    timeout_seconds: float = 10.0,
    use_browser_automation: bool = True,
    max_candidates: int = 5,
) -> dict[str, Any]:
    hits: list[PhoneHit] = []
    errors: list[str] = []

    try:
        hits.extend(
            lookup_via_requests(
                full_name=full_name,
                property_address=property_address,
                city=city,
                state=state,
                timeout_seconds=timeout_seconds,
            )
        )
    except Exception as exc:
        errors.append(f"requests_lookup_error: {exc}")

    if use_browser_automation:
        try:
            hits.extend(
                lookup_via_playwright(
                    full_name=full_name,
                    property_address=property_address,
                    city=city,
                    state=state,
                    timeout_seconds=timeout_seconds,
                )
            )
        except Exception as exc:
            errors.append(f"browser_lookup_error: {exc}")

    phones = rank_phone_hits(
        hits=hits,
        full_name=full_name,
        property_address=property_address,
        city=city,
        state=state,
        max_candidates=max_candidates,
    )
    return {"phones": phones, "errors": errors}


def lookup_via_requests(
    *,
    full_name: str,
    property_address: str,
    city: str,
    state: str,
    timeout_seconds: float,
) -> list[PhoneHit]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})

    queries = build_search_queries(
        full_name=full_name,
        property_address=property_address,
        city=city,
        state=state,
    )

    hits: list[PhoneHit] = []
    for query in queries:
        html = fetch_duckduckgo_html(session=session, query=query, timeout_seconds=timeout_seconds)
        hits.extend(extract_phone_hits_from_text(html, source="ddg_snippet"))
        links = extract_duckduckgo_links(html)
        for link in links[:3]:
            if not is_allowed_people_lookup_domain(link):
                continue
            try:
                page = session.get(link, timeout=timeout_seconds)
                page.raise_for_status()
            except Exception:
                continue
            hits.extend(
                extract_phone_hits_from_text(page.text, source=f"web:{urlparse(link).netloc}")
            )
    return hits


def lookup_via_playwright(
    *,
    full_name: str,
    property_address: str,
    city: str,
    state: str,
    timeout_seconds: float,
) -> list[PhoneHit]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return []

    queries = build_search_queries(
        full_name=full_name,
        property_address=property_address,
        city=city,
        state=state,
    )
    hits: list[PhoneHit] = []
    timeout_ms = max(2000, int(timeout_seconds * 1000))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.set_default_timeout(timeout_ms)
        for query in queries:
            url = f"https://duckduckgo.com/?q={quote_plus(query)}"
            try:
                page.goto(url, wait_until="domcontentloaded")
                content = page.content()
            except Exception:
                continue
            hits.extend(extract_phone_hits_from_text(content, source="browser:ddg"))

            links = extract_duckduckgo_links(content)
            for link in links[:2]:
                if not is_allowed_people_lookup_domain(link):
                    continue
                try:
                    page.goto(link, wait_until="domcontentloaded")
                    site_content = page.content()
                except Exception:
                    continue
                hits.extend(
                    extract_phone_hits_from_text(
                        site_content, source=f"browser:{urlparse(link).netloc}"
                    )
                )
        browser.close()

    return hits


def build_search_queries(
    *, full_name: str, property_address: str, city: str, state: str
) -> list[str]:
    location = " ".join(part for part in (clean_text(city), clean_text(state)) if part).strip()
    domain_filter = " OR ".join(f"site:{domain}" for domain in PEOPLE_SEARCH_DOMAINS)

    queries = []
    if clean_text(full_name):
        queries.append(f'"{clean_text(full_name)}" "{location}" phone ({domain_filter})')
    if clean_text(property_address):
        queries.append(f'"{clean_text(property_address)}" "{location}" phone ({domain_filter})')
    return queries


def fetch_duckduckgo_html(
    *, session: requests.Session, query: str, timeout_seconds: float
) -> str:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    response = session.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    return response.text


def extract_duckduckgo_links(html: str) -> list[str]:
    links: list[str] = []
    for encoded in RESULT_LINK_PATTERN.findall(html):
        url = unquote(encoded)
        if url.startswith("http://") or url.startswith("https://"):
            links.append(url)
    return dedupe_preserve_order(links)


def is_allowed_people_lookup_domain(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in PEOPLE_SEARCH_DOMAINS)


def extract_phone_hits_from_text(text: str, *, source: str) -> list[PhoneHit]:
    hits: list[PhoneHit] = []
    if not text:
        return hits
    normalized_text = " ".join(clean_text(text).split())
    for match in PHONE_PATTERN.finditer(normalized_text):
        number = normalize_phone_candidate(match.group(0))
        if not number:
            continue
        start = max(0, match.start() - 100)
        end = min(len(normalized_text), match.end() + 100)
        context = normalized_text[start:end]
        hits.append(PhoneHit(number=number, source=source, context=context))
    return hits


def rank_phone_hits(
    *,
    hits: list[PhoneHit],
    full_name: str,
    property_address: str,
    city: str,
    state: str,
    max_candidates: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[PhoneHit]] = {}
    for hit in hits:
        grouped.setdefault(hit.number, []).append(hit)

    phones: list[dict[str, Any]] = []
    for number, number_hits in grouped.items():
        sources = sorted({hit.source for hit in number_hits})
        combined_context = " ".join(hit.context for hit in number_hits)
        confidence = score_phone_candidate(
            context=combined_context,
            sources=sources,
            full_name=full_name,
            property_address=property_address,
            city=city,
            state=state,
        )
        phones.append(
            {
                "number": number,
                "confidence": confidence,
                "sources": sources,
            }
        )

    phones.sort(key=lambda item: (item["confidence"], len(item["sources"])), reverse=True)
    return phones[:max(1, max_candidates)]


def score_phone_candidate(
    *,
    context: str,
    sources: list[str],
    full_name: str,
    property_address: str,
    city: str,
    state: str,
) -> int:
    text = clean_text(context).lower()
    score = 20

    name_tokens = [token for token in re.findall(r"[a-z]+", clean_text(full_name).lower()) if len(token) >= 3]
    if name_tokens and any(token in text for token in name_tokens):
        score += 25

    city_text = clean_text(city).lower()
    state_text = clean_text(state).lower()
    if (city_text and city_text in text) or (state_text and state_text in text):
        score += 20

    addr_tokens = [token for token in re.findall(r"[a-z0-9]+", clean_text(property_address).lower()) if len(token) >= 3]
    if addr_tokens and any(token in text for token in addr_tokens):
        score += 25

    if len(sources) > 1:
        score += min(20, (len(sources) - 1) * 10)

    return max(0, min(100, score))


def normalize_phone_candidate(value: str) -> str:
    digits = re.sub(r"\D", "", clean_text(value))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    if digits in {"0000000000", "1111111111", "1234567890"}:
        return ""
    if int(digits[0:3]) < 200 or int(digits[3:6]) < 200:
        return ""
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"


def dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
