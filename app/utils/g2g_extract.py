from typing import Final
import requests
from decorator.retry import retry
from requests import HTTPError, Session
from bs4 import BeautifulSoup, Tag

from model.crawl_model import DeliveryTime, TimeUnit, G2GOfferItem
from .exceptions import G2GCrawlerError

import re

DEFAULT_HEADERS: Final[dict[str, str]] = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 '
                  'Safari/537.36',
    # Common browser UA
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
              'application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',  # Requests handles decompression
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    # 'Referer': 'https://www.g2g.com/', # Optional: Sometimes helps, set to a plausible referring page if needed
}

DEFAULT_COOKIES: Final[dict[str, str]] = {
    "g2g_regional": '{"country": "VN", "currency": "USD", "language": "en"}'
}


@retry(retries=5, delay=1.2, exception=HTTPError)
def __get_soup(
        url: str,
) -> BeautifulSoup:
    try:
        session = Session()
        session.headers.update(DEFAULT_HEADERS) # Set default headers for the session

        res = session.get(
            url=url,
            cookies=DEFAULT_COOKIES, # Pass cookies to the specific request
            timeout=15 # Add a timeout to prevent hanging
        )
        # Check for HTTP errors AFTER the request is made
        res.raise_for_status() # This will raise HTTPError for 4xx/5xx responses

        return BeautifulSoup(res.text, "html.parser")

    # Catch specific HTTPError for retries
    except HTTPError as e:
        print(f"HTTP Error encountered for {url}: {e.response.status_code} {e.response.reason}")
        # Optionally print some response text for debugging, might show a block page
        # print(f"Response text snippet: {e.response.text[:500]}")
        raise e # Re-raise the HTTPError so the @retry decorator catches it

    # Catch other potential request errors (network issues, DNS errors, timeouts)
    except requests.exceptions.RequestException as e:
        print(f"Request failed for {url}: {e}")
        # Wrap in your custom exception or raise directly
        raise G2GCrawlerError(f"Request failed for {url}: {e}") from e


def __g2g_extract_offer_items_from_soup(
        soup: BeautifulSoup,
) -> list[G2GOfferItem]:
    g2g_offer_items = []

    for offer_item_tag in soup.select(
            "#pre_checkout_sls_offer .other_offer-desk-main-box"
    ):
        g2g_offer_items.append(
            G2GOfferItem(
                seller_name=__g2g_extract_seller_name(offer_item_tag),
                delivery_time=__g2g_extract_delivery_time(offer_item_tag),
                stock=__g2g_extract_stock(offer_item_tag),
                min_purchase=__g2g_extract_min_purchase(offer_item_tag),
                price_per_unit=__g2g_extract_price_per_unit(offer_item_tag),
            )
        )

    return g2g_offer_items


def __g2g_extract_seller_name(
        tag: Tag,
) -> str:
    seller_name_tag = tag.select_one(".seller__name-detail")
    if seller_name_tag:
        return seller_name_tag.get_text(strip=True)
    raise G2GCrawlerError("Can't get seller name")


def __g2g_extract_delivery_time(
        tag: Tag,
) -> DeliveryTime:
    UNIT_MAP: Final[dict[str, str]] = {
        "h": "Hours",
    }

    for flex_tag in tag.select(".flex-1.align-self"):
        if "Delivery speed" in flex_tag.get_text(strip=True):
            lower_tag = flex_tag.select_one(".offer__content-lower-items")
            if lower_tag:
                pattern = r"(\d+)([a-zA-Z]*)"
                match = re.match(pattern, lower_tag.get_text(strip=True))
                if match:
                    value = match.group(1)
                    unit = match.group(2)
                    if unit in UNIT_MAP:
                        return DeliveryTime(
                            value=int(value),
                            unit=TimeUnit(UNIT_MAP[unit]),
                        )
    raise G2GCrawlerError("Can't extract delivery time")


def __g2g_extract_stock(
        tag: Tag,
) -> int:
    for flex_tag in tag.select(".flex-1.align-self"):
        if "Stock" in flex_tag.get_text(strip=True):
            lower_tag = flex_tag.select_one(".offer__content-lower-items")
            if lower_tag:
                pattern = r"(\d+)([a-zA-Z]*)"
                lower_tag_text = lower_tag.get_text(strip=True).replace(",", "")
                match = re.match(pattern, lower_tag_text)
                if match:
                    value = match.group(1)
                    return int(value)
    raise G2GCrawlerError("Can't extract Stock")


def __g2g_extract_min_purchase(
        tag: Tag,
) -> int:
    for flex_tag in tag.select(".flex-1.align-self"):
        if "Min. purchase" in flex_tag.get_text(strip=True):
            lower_tag = flex_tag.select_one(".offer__content-lower-items")
            if lower_tag:
                pattern = r"(\d+)([a-zA-Z]*)"
                lower_tag_text = lower_tag.get_text(strip=True).replace(",", "")
                match = re.match(pattern, lower_tag_text)
                if match:
                    value = match.group(1)
                    return int(value)
    raise G2GCrawlerError("Can't extract Min purchase")


def __g2g_extract_price_per_unit(
        tag: Tag,
) -> float:
    price_tag = tag.select_one(".offer-price-amount")
    if price_tag:
        return float(price_tag.get_text(strip=True))

    raise G2GCrawlerError("Can't extract Price per unit")


@retry(retries=5, delay=0.5, exception=HTTPError)
def g2g_extract_offer_items(
        url: str,
) -> list[G2GOfferItem]:
    soup = __get_soup(url)
    return __g2g_extract_offer_items_from_soup(soup)
