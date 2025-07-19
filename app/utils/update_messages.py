from datetime import datetime
from ..models.crwl_api_models import Product


def last_update_message(
    now: datetime,
) -> str:
    formatted_date = now.strftime("%d/%m/%Y %H:%M:%S")
    return formatted_date


def __lower_min_price_product_format(
    lower_min_price_products: list[Product] = [],
) -> str:
    return ", ".join(
        [
            f"{product.seller.shop_name} - {product.price}"
            for product in lower_min_price_products
        ]
    )


def update_with_min_price_message(
    price: float,
    price_min: float,
    price_max: float | None = None,
    lower_min_price_products: list[Product] = [],
) -> tuple[str, str]:
    now = datetime.now()
    _last_update_message = last_update_message(now)
    note_message = f"""{_last_update_message}:Giá đã cập nhật thành công; Price = {price}; Pricemin = {price_min}, Pricemax = {price_max}
Đối thủ có giá bé hơn giá min : {__lower_min_price_product_format(lower_min_price_products)}
"""
    return note_message, _last_update_message


def update_with_comparing_seller_message(
    price: float,
    price_min: float,
    comparing_price: float,
    comparing_seller: str,
    price_max: float | None = None,
    lower_min_price_products: list[Product] = [],
) -> tuple[str, str]:
    now = datetime.now()
    _last_update_message = last_update_message(now)
    note_message = f"""{last_update_message(now)}:Giá đã cập nhật thành công; Price = {price}; Pricemin = {price_min}, Pricemax = {price_max}, GiaSosanh = {comparing_price} - Seller: {comparing_seller}
Đối thủ có giá bé hơn giá min : {__lower_min_price_product_format(lower_min_price_products)}
"""
    return note_message, _last_update_message


# def no_need_update_message(
#     my_seller: str,
#     price: float,
#     stock: int,
#     min_quantity: int | None,
#     unit_stock: int,
#     price_min: float,
#     price_max: float | None = None,
# ) -> tuple[str, str]:
#     now = datetime.now()
#     _last_update_message = last_update_message(now)
#     note_message = f"{last_update_message(now)}: Không cần cập nhật giá vì {my_seller} Đã có giá nhỏ nhất: Price = {price}; Stock = {stock}; Unit Stock = {unit_stock}; MinUnitPerOrder = {min_quantity}; Pricemin = {price_min}, Pricemax = {price_max}."
#     return note_message, _last_update_message
