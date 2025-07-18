import execjs
from bs4 import BeautifulSoup, Tag
from requests import HTTPError

from decorator.retry import retry
from model.crawl_model import Seller, DeliveryTime, TimeUnit, OfferItem
from .exceptions import PACrawlerError
from .selenium_util import SeleniumUtil


@retry(retries=3, delay=1.2, exception=HTTPError)
def __get_soup(url: str, browser: SeleniumUtil) -> BeautifulSoup:
    browser.driver.get(url)
    res = browser.driver.page_source
    return BeautifulSoup(res, "html.parser")


def __extract_offer_items_from_soup(soup: BeautifulSoup) -> list[OfferItem]:
    offer_items = []
    offers_model = __extract_min_unit_and_min_stock(soup)

    for offer_item_tag in soup.select(".offer-item"):
        offer_item_id = __extract_offer_id(offer_item_tag)
        offer_items.append(
            OfferItem(
                offer_id=offer_item_id,
                server=__extract_server(offer_item_tag),
                seller=__extract_seller(offer_item_tag),
                delivery_time=__extract_delivery_time(offer_item_tag),
                min_stock=offers_model[offer_item_id].get("min_stock", None),
                min_unit=offers_model[offer_item_id].get("min_unit", None),
                quantity=__extract_quantity(offer_item_tag),
                price=__extract_price(offer_item_tag),
            )
        )
    for offer_item_tag in soup.select(".product-item"):
        offer_item_id = __extract_offer_id(offer_item_tag)
        offer_items.append(
            OfferItem(
                offer_id=offer_item_id,
                server=__extract_server(offer_item_tag),
                seller=__extract_seller(offer_item_tag),
                delivery_time=__extract_delivery_time(offer_item_tag),
                min_stock=offers_model[offer_item_id].get("min_stock", None),
                min_unit=offers_model[offer_item_id].get("min_unit", None),
                quantity=__extract_quantity(offer_item_tag),
                price=__extract_price(offer_item_tag),
            )
        )
        # Sleep interval
        # time.sleep(random.uniform(1, 1.5))

    return offer_items


def __extract_offer_id(
        tag: Tag,
) -> str:
    offer_id_tag = tag.select_one(".offerid")
    if offer_id_tag:
        return offer_id_tag.get_text(strip=True)
    raise PACrawlerError("Can't extract offer id")


def __extract_server(
        tag: Tag,
) -> str:
    offer_title_lv1_tag = tag.select_one(".offer-title-lv1")
    offer_title_lv2_tag = tag.select_one(".offer-title-lv2")

    offer_title_lv1 = (
        offer_title_lv1_tag.get_text(strip=True) if offer_title_lv1_tag else ""
    )
    offer_title_lv2 = (
        offer_title_lv2_tag.get_text(strip=True) if offer_title_lv2_tag else ""
    )

    if offer_title_lv1 == "" or offer_title_lv2 == "":
        # raise PACrawlerError("Can't extract server")
        pass

    return f"{offer_title_lv1} - {offer_title_lv2}"


@retry(5, delay=0.25, exception=PACrawlerError)
def __extract_seller_feedback_count(
        soup: BeautifulSoup,
) -> int:
    for grid_item in soup.select(".user-content-grid-item"):
        if "Total feedback" in grid_item.get_text(separator=" ", strip=True):
            feedback_tag = grid_item.select_one(".txt-gold")
            if feedback_tag:
                return int(feedback_tag.get_text(strip=True).replace(",", ""))


def __extract_seller(
        tag: Tag,
) -> Seller:
    canGetFeedback = True
    offer_seller_name_tag = tag.select_one(".username")
    name = offer_seller_name_tag.get_text(strip=True) if offer_seller_name_tag else ""
    if name == "":
        try:
            name = tag.select_one('div.offer-seller-name a span').get_text(strip=True)
        except Exception:
            name = ""
            raise PACrawlerError("Can't extract seller name")
    # seller_soup = __get_soup(f"https://www.playerauctions.com/store/{name}/")
    # try:
    #     feedback_count = __extract_seller_feedback_count(seller_soup)
    # except PACrawlerError:
    #     feedback_count = 0
    #     canGetFeedback = False
    #     print("Can't get feedback count then set to 0")
    return Seller(
        name=name,
        feedback_count=0,
        canGetFeedback=canGetFeedback,
    )


def __extract_delivery_time(
        tag: Tag,
) -> DeliveryTime:
    delivery_text_tag = tag.select_one(".OLP-delivery-text")
    if delivery_text_tag:
        delivery_text = delivery_text_tag.get_text(strip=True)
        delivery_splitted = delivery_text.split(" ")
        return DeliveryTime(
            value=int(delivery_splitted[0]),
            unit=TimeUnit(delivery_splitted[1]),
        )
    raise PACrawlerError("Can't extract delivery time")


def __extract_price(
        tag: Tag,
) -> float:
    price_tag = tag.select_one(".offer-price-tag")
    if price_tag:
        price_txt = price_tag.get_text(strip=True).replace("$", "")
        return float(price_txt)

    raise PACrawlerError("Can't extract price")


def __extract_quantity(
        tag: Tag,
) -> int:
    quan_tag = tag.select_one(".OLP-input-number")
    if quan_tag:
        return int(quan_tag.attrs["value"])

    raise PACrawlerError("Can't extract quantity")


def __extract_min_unit_and_min_stock(
        soup: BeautifulSoup,
) -> dict:
    for script_tag in soup.select("script"):
        if "varoffersModel" in script_tag.text.replace(" ", ""):
            ctx = execjs.compile(script_tag.text)
            offers_model = ctx.eval("offersModel")
            res_dict = {}
            for offer_model in offers_model:
                res_dict[str(offer_model["id"])] = {
                    "min_unit": offer_model["currencyPerUnit"],
                    "min_stock": offer_model["currencyPerUnit"]
                                 * offer_model["minValue"],
                }

            return res_dict

    raise PACrawlerError("Can't extract min_unit and min_stock")


@retry(5, delay=0.25, exception=PACrawlerError)
def extract_offer_items(
        url: str,
        browser: SeleniumUtil,
) -> list[OfferItem]:
    return __extract_offer_items_from_soup(
        __get_soup(url, browser),
    )
