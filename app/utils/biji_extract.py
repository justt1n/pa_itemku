import csv
from typing import List, Optional, Dict, Any

import requests
from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationInfo
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from app.models.gsheet_model import BIJ
from app.utils.selenium_util import SeleniumUtil


class FlexibleBaseModel(BaseModel):
    """
    A custom base model with a flexible configuration that:
    - Ignores extra fields from the API.
    - Automatically converts None to "" for string fields.
    """
    model_config = ConfigDict(
        extra='ignore',  # Ignore fields not defined in the model
        populate_by_name=True,  # Allow using aliases
    )

    @field_validator('*', mode='before')
    @classmethod
    def none_to_empty_str(cls, v: Any, info: ValidationInfo) -> Any:
        """If a field should be a string and the value is None, convert it to ""."""
        field_info = cls.model_fields.get(info.field_name)
        if field_info:
            is_string_field = field_info.annotation is str or \
                              str in getattr(field_info.annotation, '__args__', ())
            if is_string_field and v is None:
                return ""  # Convert None to empty string
        return v


class Server(FlexibleBaseModel):
    """Model Server đầy đủ, map tất cả các trường từ JSON."""
    id: int
    parent_id: int = Field(alias='parentId')
    name: str
    leaf: bool
    type: str
    type_name: str = Field(alias='typeName')
    initial: str
    hot: bool
    sort: str
    # Các trường có thể là null được khai báo là Optional
    code: Optional[str] = None
    english_name: Optional[str] = Field(default=None, alias='englishName')
    unit: Optional[str] = None
    description: Optional[str] = None
    img_url: Optional[str] = Field(default=None, alias='imgUrl')


class Game(BaseModel):
    """Model Game đầy đủ, map tất cả các trường từ JSON."""
    id: int
    name: str
    leaf: bool
    type: str
    type_name: str = Field(alias='typeName')
    initial: str
    hot: bool
    sort: str
    code: str
    english_name: str = Field(alias='englishName')
    unit: str
    description: str
    img_url: Optional[str] = Field(default=None, alias='imgUrl')
    servers: List[Server] = []


class Merchant(FlexibleBaseModel):
    """Model cho đối tượng 'merchant' lồng bên trong."""
    id: str
    user_id: str = Field(alias='userId')
    store_name: str = Field(alias='storeName')
    order_completion_rate: float = Field(alias='orderCompletionRate')
    order_settlement_of_second: int = Field(alias='orderSettlementOfSecond')
    online: bool
    created_at: str = Field(alias='createdAt')


class ShopDemand(FlexibleBaseModel):
    """Model cho một 'mặt hàng' trong danh sách 'list'."""
    id: str
    title: str
    price: float
    sum_quantity: int = Field(alias='sumQuantity')
    min_quantity: int = Field(alias='minQuantity')
    effective_quantity: int = Field(alias='effectiveQuantity')
    unit: str
    delivery_method_label: str = Field(alias='deliveryMethodLabel')
    guaranteed: bool
    deposit: str
    game_code: str = Field(alias='gameCode')
    game_name: str = Field(alias='gameName')
    attr_name_indexes: str = Field(alias='attrNameIndexes')
    created_at: str = Field(alias='createdAt')
    merchant: Merchant  # Lồng model Merchant vào đây


class ShopDemandResponse(FlexibleBaseModel):
    """Model tổng thể cho toàn bộ JSON response."""
    total: int
    current_page: int = Field(alias='currentPage')
    page_size: int = Field(alias='pageSize')
    list: List[ShopDemand]  # Một danh sách các đối tượng ShopDemand


def get_hostname_by_host_id(data, hostid):
    for entry in data:
        if entry['hostid'] == str(hostid):
            return entry['hostname']
    return None


@retry(
    wait=wait_fixed(2),
    stop=stop_after_attempt(5)
)
def bij_lowest_price(
        BIJ_HOST_DATA: dict,
        selenium: SeleniumUtil,
        data: BIJ,
        black_list) -> Optional[ShopDemand]:
    data.BIJ_NAME = get_hostname_by_host_id(BIJ_HOST_DATA, data.BIJ_NAME)
    data.BIJ_NAME = str(data.BIJ_NAME) + " "
    selenium.get("https://www.bijiaqi.com/")
    try:
        item_list = get_price_list(BIJ_HOST_DATA, int(data.BIJ_SERVER))
        lowest_price = get_the_lowest_price(item_list, data.BIJ_DELIVERY_METHOD, data.BIJ_STOCKMIN, data.BIJ_STOCKMAX,
                                            black_list)
        return lowest_price
    except Exception as e:
        raise RuntimeError(f"Error getting BIJ lowest price: {e}")


def get_price_list(server_map: dict, server_id: int) -> list[ShopDemand] | None:
    game_service = GameService()

    game_id = find_game_id(server_map, server_id)
    if not game_id:
        print(f"Could not find a gameId for server_id: {server_id}")
        return None

    response = game_service.fetch_shop_demand(game_id, server_id)

    if not response or not response.list:
        print(f"No items found for game {game_id}, server {server_id}.")
        return None

    return response.list


def get_the_lowest_price(
        items: List['ShopDemand'],
        delivery_types: str,
        min_qty: int,
        max_qty: int,
        black_list=None
) -> Optional['ShopDemand']:
    if not items:
        return None

    allowed_delivery_methods = {method.strip() for method in delivery_types}

    # Use a generator expression for memory-efficient filtering
    filtered_items = []

    # 2. Loop through all items to filter them
    for item in items:
        # 3. Check if the item matches all conditions
        if (item.min_quantity >= min_qty and
                item.sum_quantity <= max_qty and
                item.delivery_method_label in allowed_delivery_methods):
            if black_list is not None and item.merchant.store_name not in black_list:
                filtered_items.append(item)
    try:
        # The min() function will raise a ValueError if filtered_items is empty
        min_item = min(filtered_items, key=lambda item: item.price)
        return min_item
    except ValueError:
        return None


class GameService:
    API_BASE_URL = "https://www.bijiaqi.com/api/v1/any/shop"
    HEADERS = {'Content-Type': 'application/json'}

    def __init__(self):
        self.games: List[Game] = []

    # def _setup_mock_api_data(self) -> Dict[int, List[Dict[str, Any]]]:
    #     # Dữ liệu giả lập cho API
    #     return {
    #         560: [
    #             {"id": 37196, "parentId": 560, "name": "Doomhowl(Hardcore) - Alliance", "leaf": False,
    #              "type": "server",
    #              "typeName": "服务器", "initial": "D", "hot": False, "sort": "1940248948203720704",
    #              "code": None,
    #              "englishName": None, "unit": None, "description": None, "imgUrl": None},
    #             {"id": 37197, "parentId": 560, "name": "Doomhowl(Hardcore) - Horde", "leaf": False,
    #              "type": "server",
    #              "typeName": "服务器", "initial": "D", "hot": False, "sort": "1940248948203720705",
    #              "code": None,
    #              "englishName": None, "unit": None, "description": None, "imgUrl": None}
    #         ],
    #         561: [
    #             {"id": 40100, "parentId": 561, "name": "Silvermoon (EU) - Alliance", "leaf": False,
    #              "type": "server",
    #              "typeName": "服务器", "initial": "S", "hot": True, "sort": "2000000000000000001", "code": None,
    #              "englishName": None, "unit": None, "description": None, "imgUrl": None}
    #         ]
    #     }

    # def _fetch_servers_from_api(self, game_id: int) -> List[Dict[str, Any]]:
    #     print(f"▶️  Đang gọi API cho game ID: {game_id}...")
    #     time.sleep(0.5)
    #     servers_data = self._mock_api_data.get(game_id, [])
    #     print(f"✅  Nhận được {len(servers_data)} server.")
    #     return servers_data
    #
    # def join_game_with_servers(self):
    #     print("--- Bắt đầu quá trình kết hợp dữ liệu ---")
    #     for game in self.games:
    #         server_dicts = self._fetch_servers_from_api(game.id)
    #         game.servers = server_dicts # Pydantic tự động phân tích dữ liệu vào model Server đầy đủ
    #     print("--- Hoàn tất quá trình kết hợp ---\n")
    #

    def _fetch_games_from_api(self) -> List[Dict[str, Any]]:
        url = f"{self.API_BASE_URL}/home/games"
        print(f"Fetching games from API: {url}...")

        try:
            response = requests.post(url, headers=self.HEADERS, json={}, timeout=10)
            response.raise_for_status()
            games_data = response.json()
            print(f"Fetched {len(games_data)} games from API.")
            return games_data

        except requests.exceptions.RequestException as e:
            print(f"Error fetching games from API: {e}")
            return []

    def _fetch_servers_from_api(self, game_id: int) -> List[Dict[str, Any]]:
        @retry(
            wait=wait_fixed(2),  # Wait 2 seconds between retries
            stop=stop_after_attempt(5),  # Stop after 3 attempts
            retry=retry_if_exception_type(requests.exceptions.RequestException),  # Only retry on network/HTTP errors
            reraise=False  # Do not re-raise the exception after the last attempt
        )
        def _make_api_call() -> List[Dict[str, Any]]:
            url = f"{self.API_BASE_URL}/home/servers"
            payload = {"gameId": game_id}

            print(f"▶️  Calling API for servers of game ID {game_id} from: {url}...")

            response = requests.post(url, headers=self.HEADERS, json=payload, timeout=30)
            response.raise_for_status()

            servers_data = response.json()
            print(f"✅  Successfully retrieved {len(servers_data)} servers for game ID {game_id}.")
            return servers_data

        try:
            result = _make_api_call()
            return result if result is not None else []
        except Exception as e:
            print(f"❌  All retry attempts failed for game ID {game_id}: {e}")
            return []

    def get_final_result(self) -> List[Dict[str, Any]]:
        return [game.model_dump(by_alias=True) for game in self.games]

    @retry(
        wait=wait_fixed(5),  # Wait 2 seconds between each retry
        stop=stop_after_attempt(5),  # Stop after 3 attempts in total
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        # Only retry on network/HTTP errors
        reraise=False  # Do not re-raise the exception after the last attempt fails
    )
    def fetch_shop_demand(self, game_id: int, server_id: int) -> Optional['ShopDemandResponse']:
        url = "https://www.bijiaqi.com/api/shop/demand/listShopDemand"
        payload = {
            "page": 1,
            "limit": 100,
            "categoryId": 1,
            "gameId": game_id,
            "attrIdIndexes": str(server_id),
            "order": "price,asc",
            "attributeChildrenIds": []
        }

        # print(f"Calling API for shop demand for game {game_id}, server {server_id}...")

        try:
            response = requests.post(url, headers=self.HEADERS, json=payload, timeout=10)

            # This will trigger a retry if the status code is 4xx or 5xx
            response.raise_for_status()

            response_data = response.json()
            validated_response = ShopDemandResponse.model_validate(response_data)

            # print(f"Successfully fetched shop demand for game {game_id}.")
            return validated_response

        except requests.exceptions.RequestException as e:
            print(f"API call failed: {e}. Retrying if possible...")
            raise

        except Exception as e:
            # Catch other errors (like Pydantic validation) that should NOT be retried.
            print(f"Error processing shop demand data: {e}")
            return None


def load_server_map_from_csv(filepath: str) -> dict:
    server_map = {}
    try:
        with open(filepath, mode='r', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            next(reader)  # Bỏ qua dòng tiêu đề (header)
            for row in reader:
                if len(row) >= 2:
                    try:
                        game_id = int(row[0])
                        server_id = int(row[1])
                        server_map[server_id] = game_id
                    except ValueError:
                        print(f"Ignoring {row[0]} as it is not a number.")
    except FileNotFoundError:
        print(f"Can't find {filepath}.")
        return {}
    return server_map


def find_game_id(server_map: dict, server_id_to_find: int) -> int | None:
    if not server_map:
        return None
    return server_map.get(server_id_to_find)
