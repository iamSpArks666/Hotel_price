import asyncio
import random
import re
from dataclasses import dataclass
from typing import Optional, List

from playwright.async_api import async_playwright


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


BOOKING_SELECTOR = 'span[data-testid="price-and-discounted-price"]'
AGODA_CURRENCY_SELECTOR = 'span[data-selenium="hotel-currency"]'
AGODA_PRICE_SELECTOR = 'span[data-selenium="display-price"]'
JALAN_PRICE_SELECTOR = 'span.p-searchResultItem__perPersonPrice'


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


async def fetch_booking(query: Query, page) -> PriceResult:
    url = (
        "https://www.booking.com/searchresults.html"
        f"?ss={query.hotel_name}+{query.city}"
        f"&checkin={query.checkin}&checkout={query.checkout}"
        f"&group_adults={query.adults}&no_rooms={query.rooms}"
    )
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_selector(BOOKING_SELECTOR, timeout=20000)
    price_text = await page.locator(BOOKING_SELECTOR).first.inner_text()
    price = extract_price_number(price_text)
    await polite_wait()
    return PriceResult("booking", query.hotel_name, price, "USD", url, "total price")


async def fetch_agoda(query: Query, page) -> PriceResult:
    url = (
        "https://www.agoda.com/"
        f"search?city=0&locale=en-us"
        f"&checkIn={query.checkin}&checkOut={query.checkout}"
        f"&rooms={query.rooms}&adults={query.adults}"
        f"&hotelName={query.hotel_name}"
    )
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_selector(AGODA_PRICE_SELECTOR, timeout=20000)
    currency_text = await page.locator(AGODA_CURRENCY_SELECTOR).first.inner_text()
    price_text = await page.locator(AGODA_PRICE_SELECTOR).first.inner_text()
    price = extract_price_number(price_text)
    await polite_wait()
    return PriceResult("agoda", query.hotel_name, price, currency_text.strip(), page.url, "total price")


async def fetch_jalan(query: Query, page) -> PriceResult:
    url = "https://www.jalan.net/"
    await page.goto(url, wait_until="networkidle")
    await page.locator('input[type="text"]').first.fill(query.hotel_name)
    await page.keyboard.press("Enter")
    await page.wait_for_selector(JALAN_PRICE_SELECTOR, timeout=20000)
    price_text = await page.locator(JALAN_PRICE_SELECTOR).first.inner_text()
    price = extract_price_number(price_text)
    await polite_wait()
    return PriceResult("jalan", query.hotel_name, price, "JPY", page.url, "total price")


async def compare_prices(query: Query) -> List[PriceResult]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        results = [
            await fetch_jalan(query, page),
            await fetch_agoda(query, page),
            await fetch_booking(query, page),
        ]
        await browser.close()
        return results


def summarize(results: List[PriceResult]) -> List[PriceResult]:
    valid = [r for r in results if r.price is not None]
    return sorted(valid, key=lambda x: x.price)


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
    for result in summarize(final_results):
        print(result)
