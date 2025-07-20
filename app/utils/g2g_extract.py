import re
from enum import Enum

from selenium.webdriver.common.by import By
from typing import Final

from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel
from requests import HTTPError, Session
from selenium.webdriver.support.wait import WebDriverWait

from app.decorator.retry import retry
from .exceptions import G2GCrawlerError
from .selenium_util import SeleniumUtil
from ..models.gsheet_model import G2G


class Seller(BaseModel):
    name: str | None
    feedback_count: int | None
    canGetFeedback: bool | None


class StockNumInfo(BaseModel):
    stock_1: int
    stock_2: int
    stock_fake: int


class TimeUnit(Enum):
    Hours = "Hours"
    Hour = "Hour"
    Minutes = "Minutes"
    Minute = "Minute"


class DeliveryTime(BaseModel):
    value: int
    unit: TimeUnit

    def __to_seconds(self):
        if self.unit in [TimeUnit.Hour, TimeUnit.Hours]:
            return self.value * 60 * 60
        return self.value * 60

    def __gt__(self, orther: "DeliveryTime"):
        return self.__to_seconds() > orther.__to_seconds()

    def __lt__(self, orther: "DeliveryTime"):
        return self.__to_seconds() < orther.__to_seconds()

    def __ge__(self, orther: "DeliveryTime"):
        return self.__to_seconds() >= orther.__to_seconds()

    def __le__(self, orther: "DeliveryTime"):
        return self.__to_seconds() <= orther.__to_seconds()

    @staticmethod
    def from_text(
            txt: str,
    ) -> "DeliveryTime":
        # Remove duplicated white space
        while "  " in txt:
            txt = txt.replace("  ", " ")

        txt_splitted = txt.strip().split(" ")
        return DeliveryTime(
            value=int(txt_splitted[0]),
            unit=TimeUnit(txt_splitted[1]),
        )


class G2GOfferItem(BaseModel):
    seller_name: str
    delivery_time: DeliveryTime
    stock: int
    min_purchase: int
    price_per_unit: float

    def is_valid(
            self,
            g2g: G2G,
            g2g_blacklist: list[str],
    ) -> bool:
        if self.seller_name in g2g_blacklist:
            return False

        if self.delivery_time.value > g2g.G2G_DELIVERY_TIME:
            return False

        if self.stock < g2g.G2G_STOCK:
            return False

        if self.min_purchase > g2g.G2G_MINUNIT:
            return False

        return True

    @staticmethod
    def filter_valid_g2g_offer_item(
            g2g: G2G,
            g2g_offer_items: list["G2GOfferItem"],
            g2g_blacklist: list[str],
    ) -> list["G2GOfferItem"]:
        valid_g2g_offer_items = []
        for g2g_offer_item in g2g_offer_items:
            if g2g_offer_item.is_valid(g2g, g2g_blacklist):
                valid_g2g_offer_items.append(g2g_offer_item)

        return valid_g2g_offer_items

    @staticmethod
    def min_offer_item(
            g2g_offer_items: list["G2GOfferItem"],
    ) -> "G2GOfferItem":
        min = g2g_offer_items[0]
        for g2g_offer_item in g2g_offer_items:
            if g2g_offer_item.price_per_unit < min.price_per_unit:
                min = g2g_offer_item

        return min


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


@retry(retries=5, delay=0.5, exception=HTTPError)
def __get_page_source_by_selenium(
        url: str,
        selenium: SeleniumUtil,
) -> str:
    offer_list_container_selector = ".items-center"
    soup = selenium.get_page_src(url, offer_list_container_selector)
    if not soup:
        raise G2GCrawlerError("Failed to retrieve or parse the page content")
    return soup


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
        selenium: SeleniumUtil
) -> list[G2GOfferItem]:
    soup = __get_page_source_by_selenium(url, selenium)
    # If the soup is a string, parse it into BeautifulSoup
    if isinstance(soup, str):
        soup = BeautifulSoup(soup, 'html.parser')
    return __g2g_extract_offer_items_from_soup(soup)
