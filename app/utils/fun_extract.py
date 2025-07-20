import requests
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel
from requests.exceptions import HTTPError

from app.decorator.retry import retry
from .exceptions import FUNCrawlerError
from ..models.gsheet_model import FUN


class FUNOfferItem(BaseModel):
    seller: str
    in_stock: int
    price: float

    def is_valid(
            self,
            fun: FUN,
            fun_blacklist: list[str],
    ) -> bool:
        if self.seller in fun_blacklist:
            return False

        if self.in_stock < fun.FUN_STOCK:
            return False

        return True

    @staticmethod
    def filter_valid_fun_offer_items(
            fun: FUN,
            fun_offer_items: list["FUNOfferItem"],
            fun_blacklist: list[str],
    ) -> list["FUNOfferItem"]:
        valid_fun_offer_items = []
        for fun_offer_item in fun_offer_items:
            if fun_offer_item.is_valid(fun, fun_blacklist):
                valid_fun_offer_items.append(fun_offer_item)

        return valid_fun_offer_items

    @staticmethod
    def min_offer_item(
            fun_offer_items: list["FUNOfferItem"],
    ) -> "FUNOfferItem":
        min_fun_offer_item = fun_offer_items[0]
        for fun_offer_item in fun_offer_items:
            if fun_offer_item.price < min_fun_offer_item.price:
                min_fun_offer_item = fun_offer_item

        return min_fun_offer_item


@retry(retries=3, delay=1.2, exception=HTTPError)
def __get_soup(
        url: str,
) -> BeautifulSoup:
    res = requests.get(url=url, cookies={"cy": "usd"})
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")


def __extract_filters_data(
        soup: BeautifulSoup,
        filters: list[str],
) -> list[tuple]:
    filters_data = []

    # Get all filter input tag
    showcase_filter_input_tags = soup.select(".showcase-filter-input")

    for filter in filters:
        for showcase_filter_input_tag in showcase_filter_input_tags:
            if showcase_filter_input_tag.has_attr("name"):
                name = showcase_filter_input_tag.attrs["name"]
                if name in filter:
                    for option in showcase_filter_input_tag.select("option"):
                        if option.has_attr("value"):
                            # If value in option in filter
                            if option.get_text(strip=True).replace(" ", "").replace(
                                    "\n", ""
                            ) in filter.replace(" ", "").replace("\n", ""):
                                filters_data.append(
                                    (
                                        name,
                                        option.attrs["value"],
                                    )
                                )
    return filters_data


def __extract_seller_name(
        tag: Tag,
) -> str:
    seller_name_tag = tag.select_one(".media-user-name")
    if seller_name_tag:
        seller_name = seller_name_tag.get_text(strip=True)
        if seller_name:
            return seller_name

    raise FUNCrawlerError("Can't extract seller name")


def __extract_fun_in_stock(
        tag: Tag,
) -> int:
    in_stock_tag = tag.select_one(".tc-amount")
    if in_stock_tag:
        in_stock_txt = in_stock_tag.get_text(strip=True).replace(" ", "")

        if in_stock_txt:
            try:
                return int(in_stock_txt)
            except Exception:
                pass

    raise FUNCrawlerError("Can't extract in stock")


def __extract_fun_price(
        tag: Tag,
) -> float:
    price_tag = tag.select_one(".tc-price")
    if price_tag:
        unit_tags = price_tag.select(".unit")
        for unit_tag in unit_tags:
            unit_tag.decompose()
        price_txt = price_tag.get_text(strip=True)
        try:
            return float(price_txt)
        except Exception:
            pass

    raise FUNCrawlerError("Can't extract price")


def __extract_fun_offer_items_from_soup(
        offer_item_tags: list[Tag],
) -> list[FUNOfferItem]:
    fun_offer_items = []
    for offer_item_tag in offer_item_tags:
        fun_offer_items.append(
            FUNOfferItem(
                seller=__extract_seller_name(offer_item_tag),
                in_stock=__extract_fun_in_stock(offer_item_tag),
                price=__extract_fun_price(offer_item_tag),
            )
        )
    return fun_offer_items


@retry(10, 0.25, HTTPError)
def fun_extract_offer_items(
        url: str,
        filters: list[str],
) -> list[FUNOfferItem]:
    soup = __get_soup(url)
    filters_data = __extract_filters_data(soup, filters)
    filter_data_txt = ""
    for filter in filters_data:
        filter_data_txt += f'[data-{filter[0]}="{filter[1]}"]'

    offer_item_tags = soup.select(f".tc-item{filter_data_txt}")
    fun_offer_items = __extract_fun_offer_items_from_soup(offer_item_tags)
    return fun_offer_items
