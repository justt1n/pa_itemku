from pydantic import BaseModel


class Game(BaseModel):
    id: int
    name: str
    slug: str


class ItemType(BaseModel):
    how_to_trade_faq_id: str
    item_category_id: int
    name: str
    risky_type_id: int
    is_use_catalog_design: int
    slug: str


class Seller(BaseModel):
    id: int
    shop_name: str
    # last_activity_at: str
    # average_rating: float
    # rating_count: int
    # profile_picture_url: str | None = None
    # is_open: int


class Product(BaseModel):
    id: int
    name: str
    # game_id: int
    # game: Game
    # item_category_id: int
    # item_info_group_id: int | None = None
    # item_type: ItemType
    # item_type_id: int
    # item_info_id: int | None = None
    min_order: int
    price: int
    # server_id: int
    server_name: str | None = None
    stock: int
    base_unit: int
    seller: Seller

    def usd_price(
        self,
        exchange_rate: float,
    ) -> float:
        return round(self.price / exchange_rate, 2)


class Data(BaseModel):
    total_item: int
    item_per_page: int
    current_page: int
    data: list[Product]
    metadata: list


class CrwlAPIRes(BaseModel):
    success: bool
    data: Data
    message: str
    statusCode: str
