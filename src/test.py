from app.processes.crwl_api import CrwlAPI


# print(api.product(item_info_id=34919, server_id=149))

from app.utils.gsheet import worksheet
from app.models.gsheet_model import Product
from app.main_process import extract_product_id_from_product_link

api = CrwlAPI()

# urls = [
#     "https://itemku.com/g/world-of-warcraft-classic-hardcore-era-sod/gold/doomhowl?page=1&server=722&group=707",
#     "https://itemku.com/g/world-of-warcraft-classic-hardcore-era-sod/gold/crusader-strike?page=1&server=722&group=707",
#     "https://itemku.com/dagangan/path-of-exile-2-standard-exalted-orbs-cnlgamingindo/3210076",
#     "https://itemku.com/g/growtopia/lock?page=1&item_info_name=blue-gem-lock&sort=1",
#     "https://itemku.com/g/anime-defenders-roblox/item?page=1&group=1135&item_info_name=1000-trait-crystal&sort=1",
#     "https://itemku.com/g/lost-ark/gold?page=1&from=product-type-game-coin&group=437&sort=1",
#     # "https://tokoku.itemku.com/dagangan/2890981/edit",
#     "https://itemku.com/dagangan/genshin-impact-64801600-genesis-crystals-kevin-storee/1385246",
#     "https://itemku.com/g/afk-journey/akun?page=1&sort=1",
#     "https://itemku.com/dagangan/roblox-10000-robux-remillia-store/2889718",
# ]


# exchange_rate = api.foreign_exchange_rate()

for i in range(4, 14):
    product = Product.get(worksheet, i)
    print(product.Product_link)
    print(extract_product_id_from_product_link(product.Product_link))

# itemku_api = ItemkuAPI()
# print(
#     itemku_api.generate_auth_token(
#         payload={
#             "order_id": 34234,
#         }
#     )
# )

# print(itemku_api.update_price(product_id=3210076, new_price=8300))
