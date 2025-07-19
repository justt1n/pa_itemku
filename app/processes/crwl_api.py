import requests

from ..shared.consts import CRWL_API_BASE_URL
from ..models.crwl_api_models import CrwlAPIRes


class CrwlAPI:
    def __init__(
        self,
    ) -> None:
        pass

    def product(
        self,
        game_id: int | None = None,
        item_type_id: int | None = None,
        item_info_group_id: int | None = None,
        item_info_id: int | None = None,
        server_id: int | None = None,
        keyword: str | None = None,
    ):
        query_string = {
            "game_id": game_id,
            "item_type_id": item_type_id,
            "item_info_group_id": item_info_group_id,
            "item_info_id": item_info_id,
            # "server_id": server_id,
            "sort": "cheap",
            "page": 1,
            "per_page": 201,
            "keyword": keyword,
            "country_codes[]": "ID",
            # "is_default_product_list": 1,
            # "is_include_game": 1,
            # "is_from_web": 1,
            # "is_auto_delivery_first": 1,
            # "is_include_item_type": 1,
            # "is_include_item_info_group": 0,
            # "is_include_order_record": 1,
            # "exclude_sharing_account_eligible": 1,
            # "is_include_upselling_product": 1,
            # "use_simple_pagination": 1,
            # "is_exclusive": "false",
            # "platform_id": 2,
            # "is_enough_stock": 1,
            # "is_include_instant_delivery": "true",
            # "is_with_promotion": 1,
        }

        filtered_query_string = {k: v for k, v in query_string.items() if v is not None}

        res = requests.get(f"{CRWL_API_BASE_URL}/product", params=filtered_query_string)

        res.raise_for_status()

        return CrwlAPIRes.model_validate(res.json())

    def expansion_country(
        self,
    ):
        res = requests.get(f"{CRWL_API_BASE_URL}/expansion-country")
        res.raise_for_status()

        return res.json()

    def foreign_exchange_rate(
        self,
        source_currency: str = "USD",
        target_currency: str = "IDR",
    ) -> float:
        params = {
            "source_currency": source_currency,
            "target_currency": target_currency,
        }

        res = requests.get(f"{CRWL_API_BASE_URL}/foreign-exchange/rate", params=params)
        res.raise_for_status()

        return res.json()["data"][0]["exchange_rate"]


crwl_api = CrwlAPI()
