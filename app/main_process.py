import random
import re

import constants
from app.models.crwl_api_models import Product as CrwlProduct
from app.models.gsheet_model import Product
from app.processes.crwl import extract_data
from app.processes.crwl_api import crwl_api
from app.processes.itemku_api import itemku_api
from app.shared.consts import KEYWORD_SPLIT_BY_CHARACTER
from app.utils.ggsheet import GSheet
from app.utils.gsheet import worksheet
from app.utils.stock_fake import calculate_price_stock_fake, get_row
from app.utils.update_messages import (
    update_with_min_price_message,
    update_with_comparing_seller_message,
)


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
    index: int | None = None,
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

    print(f"Number of product: {len(products)}")
    print(f"Valid products: {len(valid_products)}")

    # project add order site price
    # get price in order site then compare with product price
    order_site_min_price, stock_fake_items = calculate_order_site_price(index)
    new_min_price = min_price
    stock_fake_str = ""
    od_min_price = None
    od_seller = None
    od_site = None
    if order_site_min_price is not None:
        od_min_price = order_site_min_price[0]
        od_seller = order_site_min_price[1]
        od_site = order_site_min_price[2]
        stock_fake_str = f"Order site min price: {od_min_price} - {od_seller} - {od_site}\n"
        stock_fake_str += "Order site items:\n"
        for item in stock_fake_items:
            stock_fake_str += f"{item[0]} - {item[1]} - {item[2]}\n"
    # ==================

    if min_price_product is None:
        if od_min_price is not None and od_min_price > min_price:
            print(f"No valid product found but order site have better price: {od_min_price} > min price: {min_price}")
            print(f"Set {new_min_price} to product")
            new_min_price = min_price
        target_price = update_by_min_price_or_max_price(
            product=product,
            min_price=new_min_price,
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
        print(note_message)
        product.Note = note_message + stock_fake_str
        product.Last_update = last_update_message
        product.update()
    else:
        target_price = calculate_competitive_price(
            product=product,
            min_price=new_min_price,
            compare_price=min_price_product.price,
        )

        if od_min_price is not None and target_price > od_min_price and min_price < od_min_price < max_price:
            new_min_price = min_price
            _compare_price = od_min_price
            _compare_seller = f"{od_seller} ({od_site})"
        else:
            _compare_price = min_price_product.price
            _compare_seller = min_price_product.seller.shop_name

        update_product_price(
            product_id=extract_product_id_from_product_link(
                product_link=product.Product_link
            ),
            target_price=new_min_price,
        )

        note_message, last_update_message = update_with_comparing_seller_message(
            price=target_price,
            price_min=min_price,
            price_max=max_price,
            comparing_price=_compare_price,
            comparing_seller=_compare_seller,
            lower_min_price_products=__filter_lower_than_target_price(
                products=valid_keywords_products, target_price=target_price
            ),
        )
        print(note_message)
        product.Note = note_message + stock_fake_str
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

    print(note_message)
    product.Note = note_message
    product.Last_update = last_update_message
    product.update()


def calculate_order_site_price(index: int | None = None):
    gsheet = GSheet(constants.KEY_PATH)

    # g2g = G2G.get(worksheet, index)
    # bij = BIJ.get(worksheet, index)
    # fun = FUN.get(worksheet, index)
    # dd = DD.get(worksheet, index)
    # p1 = PriceSheet1.get(worksheet, index)
    # p2 = PriceSheet2.get(worksheet, index)
    # p3 = PriceSheet3.get(worksheet, index)
    # p4 = PriceSheet4.get(worksheet, index)
    # row = Row(
    #     row_index=index,
    #     g2g=g2g,
    #     bij=bij,
    #     fun=fun,
    #     dd=dd,
    #     s1=p1,
    #     s2=p2,
    #     s3=p3,
    #     s4=p4,
    # )
    row = get_row(
        worksheet=worksheet,
        row_index=index
    )
    stock_fake_price_tuple, stock_fake_items = calculate_price_stock_fake(
        gsheet=gsheet, row=row, hostdata=constants.BIJ_HOST_DATA
    )
    if stock_fake_price_tuple is None or stock_fake_price_tuple[0] <= 0:  # Ensure valid price
        print("Stock fake price is None or not positive.")
        return None, None

    return stock_fake_price_tuple, stock_fake_items


def process(
    sb,
    product: Product,
    index: int | None = None,
):
    if product.CHECK_PRODUCT_COMPARE == 1:
        print("Check product compare flow")
        check_product_compare_flow(sb, product, index)

    else:
        print("No check product compare flow")
        no_check_product_compare_flow(product)
