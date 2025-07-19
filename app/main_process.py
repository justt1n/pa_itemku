import re
import random

from app.models.gsheet_model import Product
from app.processes.crwl import extract_data
from app.processes.crwl_api import crwl_api
from app.processes.itemku_api import itemku_api
from app.utils.update_messages import (
    update_with_min_price_message,
    update_with_comparing_seller_message,
)
from app.models.crwl_api_models import Product as CrwlProduct
from app.utils.logger import logger
from app.shared.consts import KEYWORD_SPLIT_BY_CHARACTER


def __filter_lower_than_target_price(
    products: list[CrwlProduct],
    target_price: int,
) -> list[CrwlProduct]:
    return [product for product in products if product.price < target_price]


def update_product_price(
    product_id: int,
    target_price: int,
):
    itemku_api.update_price(
        product_id=product_id,
        new_price=target_price,
    )

    return


def extract_product_id_from_product_link(
    product_link: str,
) -> int:
    pattern = r"/dagangan/(\d+)/edit"

    match = re.search(pattern, product_link)
    if match:
        extracted_id = match.group(1)
        return int(extracted_id)

    raise Exception("Can extract product id ")


def update_by_min_price_or_max_price(
    product: Product,
    min_price: int,
    max_price: int | None,
) -> int:
    if max_price:
        target_price = max_price

    else:
        target_price = min_price

    # Make sure price % 100 == 0
    target_price = itemku_api.valid_price(target_price)

    product_id = extract_product_id_from_product_link(product.Product_link)

    update_product_price(
        product_id=product_id,
        target_price=target_price,
    )

    return target_price


def calculate_competitive_price(
    product: Product,
    min_price: int,
    compare_price: int,
) -> int:
    if compare_price - product.DONGIAGIAM_MAX >= min_price:
        min_target = compare_price - product.DONGIAGIAM_MAX
    else:
        min_target = min_price
    if compare_price - product.DONGIAGIAM_MIN >= min_price:
        max_target = compare_price - product.DONGIAGIAM_MIN
    else:
        max_target = min_price

    target_price = random.randint(min_target, max_target)

    valid_target_price = itemku_api.valid_price(target_price)

    return valid_target_price


def check_product_compare_flow(
    sb,
    product: Product,
):
    min_price = product.min_price()
    max_price = product.max_price()
    blacklist = product.blacklist()

    crwl_api_res = extract_data(
        sb,
        api=crwl_api,
        url=product.PRODUCT_COMPARE,
    )

    products = crwl_api_res.data.data

    valid_products = []

    valid_keywords_products: list[CrwlProduct] = []

    min_price_product: CrwlProduct | None = None

    for _product in products:
        # Check shopname not in backlist
        if _product.seller.shop_name not in blacklist:
            # Check Include and Exclude keyword in product name
            if (
                (
                    product.INCLUDE_KEYWORD
                    and all(
                        (
                            keyword.lower()
                            in _product.name.lower() + _product.server_name.lower()
                            if _product.server_name
                            else ""
                        )
                        for keyword in product.INCLUDE_KEYWORD.split(
                            KEYWORD_SPLIT_BY_CHARACTER
                        )
                    )
                )
                or product.INCLUDE_KEYWORD is None
            ) and (
                product.EXCLUDE_KEYWORD
                and not any(
                    (
                        keyword.lower()
                        in _product.name.lower() + _product.server_name.lower()
                        if _product.server_name
                        else ""
                    )
                    for keyword in product.EXCLUDE_KEYWORD.split(
                        KEYWORD_SPLIT_BY_CHARACTER
                    )
                )
                or product.EXCLUDE_KEYWORD is None
            ):
                # print(f"VALID: {_product}")
                valid_keywords_products.append(_product)
                # Check product price in valid range
                if (max_price and min_price <= _product.price <= max_price) or (
                    max_price is None and min_price <= _product.price
                ):
                    valid_products.append(_product)
                    if (
                        min_price_product is None
                        or _product.price < min_price_product.price
                    ):
                        min_price_product = _product

    logger.info(f"Number of product: {len(products)}")
    logger.info(f"Valid products: {len(valid_products)}")

    if min_price_product is None:
        target_price = update_by_min_price_or_max_price(
            product=product,
            min_price=min_price,
            max_price=max_price,
        )

        note_message, last_update_message = update_with_min_price_message(
            price=target_price,
            price_min=min_price,
            price_max=max_price,
            lower_min_price_products=__filter_lower_than_target_price(
                products=valid_keywords_products, target_price=target_price
            ),
        )
        logger.info(note_message)
        product.Note = note_message
        product.Last_update = last_update_message
        product.update()

    else:
        target_price = calculate_competitive_price(
            product=product,
            min_price=min_price,
            compare_price=min_price_product.price,
        )

        update_product_price(
            product_id=extract_product_id_from_product_link(
                product_link=product.Product_link
            ),
            target_price=target_price,
        )

        note_message, last_update_message = update_with_comparing_seller_message(
            price=target_price,
            price_min=min_price,
            price_max=max_price,
            comparing_price=min_price_product.price,
            comparing_seller=min_price_product.seller.shop_name,
            lower_min_price_products=__filter_lower_than_target_price(
                products=valid_keywords_products, target_price=target_price
            ),
        )
        logger.info(note_message)
        product.Note = note_message
        product.Last_update = last_update_message
        product.update()


def no_check_product_compare_flow(
    product: Product,
):
    min_price = product.min_price()
    max_price = product.max_price()

    update_by_min_price_or_max_price(
        product=product,
        min_price=min_price,
        max_price=None,
    )

    note_message, last_update_message = update_with_min_price_message(
        price=min_price,
        price_min=min_price,
        price_max=max_price,
    )

    logger.info(note_message)
    product.Note = note_message
    product.Last_update = last_update_message
    product.update()


def process(
    sb,
    product: Product,
):
    if product.CHECK_PRODUCT_COMPARE == 1:
        logger.info("Check product compare flow")
        check_product_compare_flow(sb, product)

    else:
        logger.info("No check product compare flow")
        no_check_product_compare_flow(product)
