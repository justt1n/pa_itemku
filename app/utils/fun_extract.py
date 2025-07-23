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
            fun: "FUN",  # Assuming FUN model is defined elsewhere
            fun_blacklist: list[str],
    ) -> bool:
        if self.seller in fun_blacklist:
            return False
        # Assuming fun.FUN_STOCK is a valid attribute
        if self.in_stock < getattr(fun, 'FUN_STOCK', 1):
            return False
        return True

    @staticmethod
    def filter_valid_fun_offer_items(
            fun: "FUN",
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
        if not fun_offer_items:
            raise ValueError("Cannot find minimum of an empty list.")
        min_fun_offer_item = fun_offer_items[0]
        for fun_offer_item in fun_offer_items[1:]:
            if fun_offer_item.price < min_fun_offer_item.price:
                min_fun_offer_item = fun_offer_item
        return min_fun_offer_item


# =============================================================================
# CORE CRAWLER LOGIC (Updated)
# =============================================================================

@retry(retries=3, delay=1.2, exception=HTTPError)
def __get_soup(url: str) -> BeautifulSoup:
    """Fetches and parses the HTML content of a URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    res = requests.get(url=url, cookies={"cy": "usd"}, headers=headers)
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")


def __extract_filters_data(
        soup: BeautifulSoup,
        filters: list[str],
) -> list[tuple]:
    """
    -- REWRITTEN LOGIC --
    Finds the correct data-attribute name and value for a given filter.
    It works by matching the filter's value part (e.g., 'trade' from 'f-method_trade')
    with the visible text of an <option> tag on the page.
    """
    filters_data = []
    showcase_filter_input_tags = soup.select(".showcase-filter-input")

    for filter_str in filters:
        try:
            # Extract the value part of the filter, e.g., 'f-method_trade' -> 'trade'
            filter_value_text = filter_str.split("_", 1)[1].lower()
        except IndexError:
            # Skip malformed filters that don't contain an underscore
            print(f"Skipping malformed filter: {filter_str}")
            continue

        found_filter = False
        # Iterate through all filter controls on the page (<select>, etc.)
        for input_tag in showcase_filter_input_tags:
            if input_tag.has_attr("name"):
                name = input_tag.attrs["name"]
                # Find an <option> within the control that matches the filter text
                for option in input_tag.select("option"):
                    option_text = option.get_text(strip=True).lower()

                    # If the option's text matches the filter's value, we've found the right control
                    if option_text == filter_value_text:
                        if option.has_attr("value") and option.attrs.get("value"):
                            filters_data.append((name, option.attrs["value"]))
                            found_filter = True
                            break  # Matching option found, stop searching options
            if found_filter:
                break  # Matching input found, move to the next filter string

    return filters_data


def __extract_seller_name(tag: Tag) -> str:
    """Extracts seller name from an item tag."""
    seller_name_tag = tag.select_one(".media-user-name")
    if seller_name_tag and (seller_name := seller_name_tag.get_text(strip=True)):
        return seller_name
    raise FUNCrawlerError("Can't extract seller name")


def __extract_fun_in_stock(tag: Tag) -> int:
    """Extracts stock amount from an item tag."""
    in_stock_tag = tag.select_one(".tc-amount")
    if in_stock_tag and (in_stock_txt := in_stock_tag.get_text(strip=True).replace(" ", "")):
        try:
            return int(in_stock_txt)
        except (ValueError, TypeError):
            pass
    raise FUNCrawlerError("Can't extract in stock")


def __extract_fun_price(tag: Tag) -> float:
    """Extracts price from an item tag."""
    price_tag = tag.select_one(".tc-price")
    if price_tag:
        # Remove currency symbols or other units to isolate the number
        for unit_tag in price_tag.select(".unit"):
            unit_tag.decompose()
        price_txt = price_tag.get_text(strip=True).replace(" ", "")
        try:
            return float(price_txt)
        except (ValueError, TypeError):
            pass
    raise FUNCrawlerError("Can't extract price")


def __extract_fun_offer_items_from_soup(
        offer_item_tags: list[Tag],
) -> list[FUNOfferItem]:
    """Converts a list of BeautifulSoup tags into a list of FUNOfferItem objects."""
    fun_offer_items = []
    for offer_item_tag in offer_item_tags:
        try:
            fun_offer_items.append(
                FUNOfferItem(
                    seller=__extract_seller_name(offer_item_tag),
                    in_stock=__extract_fun_in_stock(offer_item_tag),
                    price=__extract_fun_price(offer_item_tag),
                )
            )
        except Exception as e:
            # Optionally print error for the specific item that failed
            # print(f"Could not parse an item: {e}")
            pass
    return fun_offer_items


@retry(retries=10, delay=0.25, exception=HTTPError)
def fun_extract_offer_items(
        url: str,
        filters: list[str],
) -> list[FUNOfferItem]:
    """
    -- UPDATED LOGIC --
    Extracts offer items from a FunPay URL, applying a list of filters.
    Handles both data-attribute filters and description-based text search filters.
    """
    # 1. Separate filters for data-attributes (e.g., 'f-method_trade')
    #    from filters for description text search (e.g., 'desc_Raccoon').
    data_filters = [f for f in filters if not f.startswith("desc_")]
    desc_keywords = [f.split("_", 1)[1].lower() for f in filters if f.startswith("desc_")]

    soup = __get_soup(url)

    # 2. Build the CSS selector from the data-attribute filters.
    filters_data = __extract_filters_data(soup, data_filters)
    filter_data_txt = ""
    for filter_item in filters_data:
        filter_data_txt += f'[data-{filter_item[0]}="{filter_item[1]}"]'

    # 3. Select all items that match the data-attribute filters.
    #    The base selector targets any 'a' tag with class 'tc-item'.
    base_selector = f"a.tc-item{filter_data_txt}"
    offer_item_tags = soup.select(base_selector)

    # 4. If there are description keywords, perform a second filtering pass on the results.
    if desc_keywords:
        final_offer_item_tags = []
        for tag in offer_item_tags:
            desc_tag = tag.select_one(".tc-desc-text")
            if desc_tag:
                desc_text = desc_tag.get_text(strip=True).lower()
                # Check if all keywords are present in the description text.
                if all(keyword in desc_text for keyword in desc_keywords):
                    final_offer_item_tags.append(tag)
        offer_item_tags = final_offer_item_tags  # Overwrite with the more specific list.

    # 5. Extract structured data from the final list of filtered tags.
    fun_offer_items = __extract_fun_offer_items_from_soup(offer_item_tags)
    return fun_offer_items


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == '__main__':
    # Example 1: Pet Simulator items
    pet_sim_url = "https://funpay.com/en/lots/2192/trade"
    pet_sim_filters = ["button_Items", "f-method_trade", "desc_Raccoon"]

    print(f"Searching for items on URL: {pet_sim_url}")
    print(f"With filters: {pet_sim_filters}\n")

    try:
        items = fun_extract_offer_items(pet_sim_url, pet_sim_filters)
        if items:
            print(f"Found {len(items)} items matching the criteria.")
            # Find and print the cheapest item
            cheapest_item = FUNOfferItem.min_offer_item(items)
            print("\n--- Cheapest Item ---")
            print(f"Seller: {cheapest_item.seller}")
            print(f"Price: ${cheapest_item.price:.2f}")
            print(f"In Stock: {cheapest_item.in_stock}")
            print("---------------------\n")
        else:
            print("No items found matching the specified criteria.")

    except Exception as e:
        print(f"An error occurred: {e}")

    print("\n" + "=" * 50 + "\n")

    # Example 2: WoW Gold
    wow_gold_url = "https://funpay.com/en/chips/172/"
    wow_gold_filters = ["select_server_(EU) #Anniversary - Thunderstrike", "select_side_Alliance"]

    print(f"Searching for items on URL: {wow_gold_url}")
    print(f"With filters: {wow_gold_filters}\n")

    try:
        items = fun_extract_offer_items(wow_gold_url, wow_gold_filters)
        if items:
            print(f"Found {len(items)} offers matching the criteria.")
            cheapest_offer = FUNOfferItem.min_offer_item(items)
            print("\n--- Cheapest Offer ---")
            print(f"Seller: {cheapest_offer.seller}")
            print(f"Price: ${cheapest_offer.price:.4f}")
            print(f"In Stock: {cheapest_offer.in_stock}")
            print("----------------------\n")
        else:
            print("No offers found matching the specified criteria.")

    except Exception as e:
        print(f"An error occurred: {e}")
