import asyncio
import os
import random
import re
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


@dataclass
class Query:
    hotel_name: str
    city: str
    checkin: str
    checkout: str
    adults: int = 2
    rooms: int = 1


@dataclass
class PriceResult:
    site: str
    hotel_name: str
    price: Optional[float]
    currency: str
    url: str
    notes: str = ""


DEFAULT_TIMEOUT_MS = 30000
BOOKING_PRICE_SELECTORS = [
    'span[data-testid="price-and-discounted-price"]',
    'div[data-testid="price-and-discounted-price"]',
]
AGODA_CURRENCY_SELECTORS = [
    'span[data-selenium="hotel-currency"]',
]
AGODA_PRICE_SELECTORS = [
    'span[data-selenium="display-price"]',
    'span[data-selenium="price"]',
]


def is_agoda_search_url(url: str) -> bool:
    parsed = urlparse(url)
    if "agoda.com" not in parsed.netloc:
        return False
    if parsed.path.rstrip("/") != "/search":
        return False
    params = parse_qs(parsed.query)
    return any(key in params for key in ("selectedproperty", "hotel", "checkIn"))


def extract_price_number(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    cleaned = (
        text.replace("¥", "")
        .replace("￥", "")
        .replace("US$", "")
        .replace("USD", "")
        .replace("RMB", "")
        .replace("円", "")
        .replace(",", "")
        .strip()
    )
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    return float(match.group(0))


async def polite_wait():
    await asyncio.sleep(random.uniform(1.5, 3.5))


async def first_visible_text(page, selectors: List[str], timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Optional[str]:
    combined = ",".join(selectors)
    await page.wait_for_selector(combined, timeout=timeout_ms, state="visible")
    locator = page.locator(combined).first
    return await locator.inner_text()


async def fetch_booking(query: Query, page) -> PriceResult:
    url = (
        "https://www.booking.com/searchresults.html"
        f"?ss={query.hotel_name}+{query.city}"
        f"&checkin={query.checkin}&checkout={query.checkout}"
        f"&group_adults={query.adults}&no_rooms={query.rooms}"
    )
    await page.goto(url, wait_until="networkidle")
    price_text = await first_visible_text(page, BOOKING_PRICE_SELECTORS)
    price = extract_price_number(price_text)
    await polite_wait()
    return PriceResult("booking", query.hotel_name, price, "USD", url, "total price")


async def fetch_agoda(query: Query, page) -> PriceResult:
    override_url = os.getenv("AGODA_URL")
    if override_url:
        url = override_url
    else:
        url = (
            "https://www.agoda.com/"
            f"search?city=0&locale=en-us"
            f"&checkIn={query.checkin}&checkOut={query.checkout}"
            f"&rooms={query.rooms}&adults={query.adults}"
            f"&hotelName={query.hotel_name}"
        )
    await page.goto(url, wait_until="networkidle")
    if override_url and not is_agoda_search_url(page.url):
        await polite_wait()
        return PriceResult(
            "agoda",
            query.hotel_name,
            None,
            "",
            page.url,
            "redirected to non-search page; copy the full Agoda results URL",
        )
    try:
        price_text = await first_visible_text(page, AGODA_PRICE_SELECTORS)
        try:
            currency_text = await first_visible_text(page, AGODA_CURRENCY_SELECTORS, timeout_ms=5000)
        except PlaywrightTimeoutError:
            currency_text = ""
        price = extract_price_number(price_text)
        notes = "total price"
    except PlaywrightTimeoutError:
        currency_text = ""
        price = None
        notes = "price selector timed out; check Agoda page or selector"
    await polite_wait()
    return PriceResult("agoda", query.hotel_name, price, currency_text.strip(), page.url, notes)


async def capture_debug(page, site: str):
    if os.getenv("DEBUG_ARTIFACTS") != "1":
        return
    try:
        await page.screenshot(path=f"debug_{site}.png", full_page=True)
        content = await page.content()
        with open(f"debug_{site}.html", "w", encoding="utf-8") as handle:
            handle.write(content)
    except Exception:
        pass


async def safe_fetch(fetcher, site: str, query: Query, page) -> PriceResult:
    try:
        result = await fetcher(query, page)
        await capture_debug(page, site)
        return result
    except PlaywrightTimeoutError:
        await capture_debug(page, site)
        return PriceResult(
            site,
            query.hotel_name,
            None,
            "",
            page.url,
            "timeout while waiting for price selector",
        )
    except Exception as exc:
        await capture_debug(page, site)
        return PriceResult(
            site,
            query.hotel_name,
            None,
            "",
            page.url,
            f"failed to fetch price: {exc}",
        )


async def compare_prices(query: Query) -> List[PriceResult]:
    async with async_playwright() as p:
        headless = os.getenv("HEADLESS", "1") != "0"
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = await context.new_page()
        results = [
            await safe_fetch(fetch_agoda, "agoda", query, page),
            await safe_fetch(fetch_booking, "booking", query, page),
        ]
        await context.close()
        await browser.close()
        return results


def summarize(results: List[PriceResult]) -> List[PriceResult]:
    valid = [r for r in results if r.price is not None]
    return sorted(valid, key=lambda x: x.price)


def format_result(result: PriceResult) -> str:
    currency = result.currency or "?"
    price = f"{result.price:.2f}" if result.price is not None else "N/A"
    return f"{result.site}: {currency} {price} ({result.notes or 'no notes'})"


def print_results(results: List[PriceResult]) -> None:
    if os.getenv("FULL_OUTPUT") == "1":
        for result in results:
            print(result)
        return
    for result in results:
        print(format_result(result))


if __name__ == "__main__":
    query = Query(
        hotel_name="Hotel Keihan Tsukiji Ginza Grande",
        city="Tokyo",
        checkin="2026-01-15",
        checkout="2026-01-17",
        adults=2,
        rooms=1,
    )
    final_results = asyncio.run(compare_prices(query))
    sorted_results = summarize(final_results)
    if not sorted_results:
        print("No prices found. Showing diagnostics for each site:")
        print_results(final_results)
    else:
        print_results(sorted_results)
