from enum import Enum
from typing import Final
from urllib.parse import urlparse, parse_qs, urlencode, unquote

import requests
from pydantic import BaseModel
from requests import HTTPError

from app.decorator.retry import retry
from app.models.gsheet_model import G2G


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
    delivery_time: int
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

        if self.delivery_time > g2g.G2G_DELIVERY_TIME:
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
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9,vi;q=0.8',
    'origin': 'https://www.g2g.com',
    'referer': 'https://www.g2g.com/',
    'sec-ch-ua': '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 '
                  'Safari/537.36 Edg/135.0.0.0'
}

DEFAULT_COOKIES: Final[dict[str, str]] = {
    "g2g_regional": '{"country": "VN", "currency": "IDR", "language": "en"}'
}


def build_g2g_request_details(user_url: str, currency: str = 'JPY', country: str = 'JP') -> tuple[str, dict]:
    """
    Builds the API request URL and headers from the user-facing URL.
    """
    # Parse the original user URL into its components
    parsed_url = urlparse(user_url)
    path_parts = parsed_url.path.strip('/').split('/')
    query_params = parse_qs(parsed_url.query)

    # Extract 'seo_term' from the URL path (e.g., 'rbl-item')
    seo_term = ""
    if 'categories' in path_parts:
        try:
            seo_term = path_parts[path_parts.index('categories') + 1]
        except (ValueError, IndexError):
            pass  # Ignore if not found

    # Get filter and sort values from the query parameters
    filter_attr_value = query_params.get('fa', [''])[0]
    sort_value = query_params.get('sort', [''])[0]

    # Construct the API request URL with required parameters
    api_base_url = 'https://sls.g2g.com/offer/search'
    api_params = {
        'seo_term': seo_term,
        'filter_attr': filter_attr_value,  # Note: 'fa' is renamed to 'filter_attr'
        'sort': sort_value,
        'page_size': 20,
        'group': 0,
        'currency': currency,
        'country': country,
        'v': 'v2'
    }

    # BUG FIX: Change condition to 'is not None' to keep params with value 0.
    # The previous condition 'if v' incorrectly removed 'group=0'.
    api_params = {k: v for k, v in api_params.items() if v is not None}
    api_url = f"{api_base_url}?{unquote(urlencode(api_params))}"

    # Define the headers to mimic a real browser request
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9,vi;q=0.8',
        'origin': 'https://www.g2g.com',
        'referer': 'https://www.g2g.com/',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0'
    }

    return api_url, headers

def fetch_g2g_offers(user_url: str, currency: str = 'JPY', country: str = 'JP') -> dict | None:
    """
    Fetches offer data from G2G's API by converting a user-facing URL.

    Args:
        user_url: The URL from the browser's address bar.
        currency: The currency code.
        country: The country code.

    Returns:
        A dictionary containing the JSON response data, or None if an error occurs.
    """
    # print("--- Bắt đầu quá trình ---")

    api_url, headers = build_g2g_request_details(user_url, currency, country)
    # print(f"[*] Đã xây dựng URL API: {api_url}")

    # print("[*] Đang gửi yêu cầu đến máy chủ G2G...")
    try:
        # Send the GET request to the API endpoint
        response = requests.get(api_url, headers=headers, timeout=10)

        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # print(f"[*] Yêu cầu thành công! (Status Code: {response.status_code})")

        # Return the response data as a Python dictionary
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        print(f"[LỖI] Lỗi HTTP xảy ra: {http_err}")
        print(f"Nội dung phản hồi: {response.text}")
    except requests.exceptions.RequestException as err:
        print(f"[LỖI] Đã xảy ra lỗi khi gửi yêu cầu: {err}")

    return None


def extract_offer_items_from_response(response_json: dict) -> list[G2GOfferItem]:
    """
    Extracts a list of G2GOfferItem objects from the API's JSON response.

    Args:
        response_json: The parsed JSON dictionary from the G2G API.

    Returns:
        A list of G2GOfferItem objects.
    """
    g2g_offer_items = []

    # The list of offers is located under the 'results' key in the 'payload'.
    offer_list = response_json.get('payload', {}).get('results', [])

    for offer_data in offer_list:
        # Extract delivery time as an integer. Default to a high value (999) if not found.
        delivery_time_int = 999
        delivery_details = offer_data.get('delivery_speed_details')
        if delivery_details and isinstance(delivery_details, list) and len(delivery_details) > 0:
            delivery_time_int = delivery_details[0].get('delivery_time', 999)

        # Extract price as a float from 'converted_unit_price' for accurate comparison.
        price_float = offer_data.get('converted_unit_price', 0.0)

        # Construct the G2GOfferItem object with the correct data types.
        g2g_offer_items.append(
            G2GOfferItem(
                seller_name=offer_data.get('username', 'N/A'),
                delivery_time=delivery_time_int,
                stock=offer_data.get('available_qty', 0),
                min_purchase=offer_data.get('min_qty', 1),
                price_per_unit=price_float
            )
        )

    return g2g_offer_items


@retry(retries=5, delay=0.5, exception=HTTPError)
def g2g_extract_offer_items(
    url: str,
) -> list[G2GOfferItem]:
    offer_items_raw = fetch_g2g_offers(url, currency='USD', country='US')
    offer_items = []
    if offer_items_raw is not None:
        offer_items = extract_offer_items_from_response(offer_items_raw)
    else:
        print("[LỖI] Không thể lấy dữ liệu từ G2G.")
    return offer_items


if __name__ == "__main__":
    input_url = "https://www.g2g.com/categories/rbl-item/offer/group?fa=b08c318c%3Aeff0694f%7C4f6e1c7b%3A7ce96ac1%7Cfe55a392%3Aa10072ed&sort=lowest_price"

    # 1. Fetch the raw JSON data from the API
    # The currency is set to 'USD' to match the desired float price comparison.
    json_data = fetch_g2g_offers(input_url, currency='USD', country='US')

    if json_data:
        # 2. Extract and structure the data into a list of objects
        offer_items = extract_offer_items_from_response(json_data)

        print("\n--- Extracted Offer Items ---")
        if not offer_items:
            print("No offers found in the response.")
        else:
            # 3. Print the structured data
            for i, item in enumerate(offer_items[:5]):  # Print first 5 items as a sample
                print(f"\n--- Offer #{i + 1} ---")
                print(f"  Seller: {item.seller_name}")
                print(f"  Price: {item.price_per_unit:.4f} USD")  # Format float for display
                print(f"  Stock: {item.stock}")
                print(f"  Min Purchase: {item.min_purchase}")
                print(f"  Delivery Time: {item.delivery_time} Mins")
            min_item = G2GOfferItem.min_offer_item(offer_items)
            print("\n--- Minimum Offer Item ---")
            print(f"  Seller: {min_item.seller_name}")
            print(f"  Price: {min_item.price_per_unit:.4f} USD")
            print(f"  Stock: {min_item.stock}")
            print(f"  Min Purchase: {min_item.min_purchase}")
            print(f"  Delivery Time: {min_item.delivery_time} Mins")
    else:
        print("\n--- Failed to retrieve data. Please check the errors above. ---")