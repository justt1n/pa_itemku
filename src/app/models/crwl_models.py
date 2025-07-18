from pydantic import BaseModel


class Game(BaseModel):
    game_id: int
    game_name: str
    game_slug: str


class Server(BaseModel):
    id: int
    name: str


class ItemInfo(BaseModel):
    id: int
    name: str
    item_info_group_id: int
    slug: str
    is_highest_sales: bool


class ItemInfoGroup(BaseModel):
    id: int
    name: str
    slug: str
    item_info: list[ItemInfo]


class ItemType(BaseModel):
    id: int
    name: str
    slug: str

    game_id: int
    game_name: str
    game_slug: str

    item_info: list[ItemInfo]
    item_info_group: list[ItemInfoGroup]


class GameInfo(BaseModel):
    game: Game
    has_game_page: int
    has_server: int
    item_type: list[ItemType]
    server: list[Server]


class ExchangeRate(BaseModel):
    exchange_rate: float
    source_currency: str
    source_currency_name: str | None = None
    target_currency: str
    target_currency_name: str | None = None


class PageProps1st(BaseModel):
    gameInfo: GameInfo
    exchangeRate: ExchangeRate


class Props1st(BaseModel):
    pageProps: PageProps1st


class Query1st(BaseModel):
    page: int | None = None
    server: int | None = None
    group: int | None = None
    region: str | None = None
    game_name: str | None = None
    item_name: str | None = None
    item_info_name: str | None = None
    sort: int | None = None
    keyword: str | None = None


class NextData1st(BaseModel):
    page: str
    props: Props1st
    query: Query1st


class ProductDetail(BaseModel):
    id: int

    item_info_group_id: int | None = None
    item_info_id: int | None = None
    item_type_id: int
    server_id: int
    game_id: int

    base_unit: int


class PageProps2nd(BaseModel):
    productDetail: ProductDetail


class Props2nd(BaseModel):
    pageProps: PageProps2nd


# class Query2nd(BaseModel):
#     product_id: str
#     region: str


class NextData2nd(BaseModel):
    page: str
    # query: Query2nd
    props: Props2nd
