import concurrent.futures
from typing import Optional, Tuple, List

from app.models.crwl_api_models import Product
from app.utils.selenium_util import SeleniumUtil

from app.decorator.retry import retry
from app.decorator.time_execution import time_execution
from app.models.crawl_model import G2GOfferItem, FUNOfferItem
from app.models.gsheet_model import G2G, BIJ, FUN, DD, PriceSheet1, PriceSheet2, PriceSheet3, PriceSheet4
from app.utils.biji_extract import bij_lowest_price
from app.utils.common_utils import getCNYRate
from app.utils.dd_utils import get_dd_min_price
from app.utils.fun_extract import fun_extract_offer_items
from app.utils.g2g_extract import g2g_extract_offer_items
from app.utils.ggsheet import (
    GSheet,
)


class ExtraInfor:
    pass


class Row:
    row_index: int
    product: Product
    g2g: G2G
    fun: FUN
    bij: BIJ
    dd: DD
    s1: PriceSheet1
    s2: PriceSheet2
    s3: PriceSheet3
    s4: PriceSheet4

    def __init__(
            self,
            row_index: int,
            g2g: G2G,
            fun: FUN,
            bij: BIJ,
            dd: DD,
            s1: PriceSheet1,
            s2: PriceSheet2,
            s3: PriceSheet3,
            s4: PriceSheet4,
    ) -> None:
        self.row_index = row_index
        self.g2g = g2g
        self.fun = fun
        self.bij = bij
        self.dd = dd
        self.s1 = s1
        self.s2 = s2
        self.s3 = s3
        self.s4 = s4


def g2g_lowest_price(
        gsheet: GSheet,
        g2g: G2G,
) -> G2GOfferItem:
    g2g_offer_items = g2g_extract_offer_items(g2g.G2G_PRODUCT_COMPARE)
    filtered_g2g_offer_items = G2GOfferItem.filter_valid_g2g_offer_item(
        g2g,
        g2g_offer_items,
        g2g.get_blacklist(gsheet),
    )
    return G2GOfferItem.min_offer_item(filtered_g2g_offer_items)


def _process_g2g(row: Row, gsheet: GSheet) -> Optional[Tuple[float, str]]:
    try:
        print("Starting G2G fetch...")
        g2g_offer_items = g2g_extract_offer_items(row.g2g.G2G_PRODUCT_COMPARE)
        filtered_g2g_offer_items = G2GOfferItem.filter_valid_g2g_offer_item(
            g2g=row.g2g,
            g2g_blacklist=row.g2g.get_blacklist(gsheet),
            g2g_offer_items=g2g_offer_items,
        )
        if filtered_g2g_offer_items:
            g2g_min_offer_item = G2GOfferItem.min_offer_item(filtered_g2g_offer_items)
            g2g_min_price = (
                round(g2g_min_offer_item.price_per_unit * row.g2g.G2G_PROFIT, 4),
                g2g_min_offer_item.seller_name
            )
            print(f"G2G min price calculated: {g2g_min_price}")
            return g2g_min_price
        else:
            print("No valid G2G offer items")
            return None
    except Exception as e:
        print(f"Error processing G2G: {e}")
        return None


def _process_fun(row: Row, gsheet: GSheet) -> Optional[Tuple[float, str]]:
    try:
        print("Starting FUN fetch...")
        fun_offer_items = fun_extract_offer_items(
            row.fun.FUN_PRODUCT_COMPARE,
            [
                i
                for i in [
                row.fun.FUN_FILTER21, row.fun.FUN_FILTER22,
                row.fun.FUN_FILTER23, row.fun.FUN_FILTER24,
            ] if i is not None
            ],
        )
        filtered_fun_offer_items = FUNOfferItem.filter_valid_fun_offer_items(
            fun=row.fun,
            fun_offer_items=fun_offer_items,
            fun_blacklist=row.fun.get_blacklist(gsheet),
        )
        if filtered_fun_offer_items:
            fun_min_offer_item = FUNOfferItem.min_offer_item(filtered_fun_offer_items)
            fun_min_price = (
                round(
                    fun_min_offer_item.price * row.fun.FUN_PROFIT * row.fun.FUN_DISCOUNTFEE * row.fun.FUN_HESONHANDONGIA,
                    4),
                fun_min_offer_item.seller
            )
            print(f"FUN min price calculated: {fun_min_price}")
            return fun_min_price
        else:
            print("No valid FUN offer items")
            return None
    except Exception as e:
        print(f"Error processing FUN: {e}")
        return None


def _process_bij(bij: BIJ, gsheet: GSheet, hostdata: dict, selenium: SeleniumUtil) -> Optional[Tuple[float, str]]:
    try:
        print("Starting BIJ fetch...")
        CNY_RATE = getCNYRate()
        _black_list = bij.get_blacklist(gsheet)
        bij_min_offer_item = None
        for attempt in range(2):
            try:
                bij_min_offer_item = bij_lowest_price(hostdata, selenium, bij, black_list=_black_list)
                break
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for BIJ. Error: {e}")
                if attempt == 1:
                    print("Error when getting BIJ after retries", e)
                    raise  # Ném lại lỗi sau khi hết số lần thử

        if bij_min_offer_item:
            bij_min_price = (
                round(bij_min_offer_item.money * bij.BIJ_PROFIT * bij.HESONHANDONGIA3 * CNY_RATE, 4),
                bij_min_offer_item.username
            )
            print(f"BIJ min price calculated: {bij_min_price}")
            return bij_min_price
        else:
            print("No valid BIJ offer items")
            return None
    except Exception as e:
        print(f"Error processing BIJ: {e}")
        return None


def _process_price1_sheet(row: Row) -> Optional[Tuple[float, str]]:
    try:
        print("Starting SheetPrice1 sheet...")
        for attempt in range(2):
            try:
                min_price = (row.s1.get_price()
                             * row.s1.SHEET_PROFIT
                             * row.s1.QUYDOIDONVI, "Get directly from sheet1")
                print(f"\nSheetPrice1 min price: {min_price}")
                return min_price
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for SheetPrice1. Error: {e}")
                if attempt == 1:
                    print("Error when getting SheetPrice1 after retries", e)
                    raise
                return None
        return None
    except Exception as e:
        print(f"Error processing PRICE1: {e}")
        return None


def _process_price2_sheet(row: Row) -> Optional[Tuple[float, str]]:
    try:
        print("Starting SheetPrice2 sheet...")
        for attempt in range(2):
            try:
                min_price = (row.s2.get_price()
                             * row.s2.SHEET_PROFIT
                             * row.s2.QUYDOIDONVI, "Get directly from sheet2")
                print(f"\nSheetPrice2 min price: {min_price}")
                return min_price
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for SheetPrice2. Error: {e}")
                if attempt == 1:
                    print("Error when getting SheetPrice2 after retries", e)
                    raise
                return None
        return None
    except Exception as e:
        print(f"Error processing SheetPrice2: {e}")
        return None


def _process_price3_sheet(row: Row) -> Optional[Tuple[float, str]]:
    try:
        print("Starting PRICE3 sheet...")
        for attempt in range(2):
            try:
                min_price = (row.s3.get_price()
                             * row.s3.SHEET_PROFIT
                             * row.s3.QUYDOIDONVI, "Get directly from sheet3")
                print(f"\nSheetPrice3 min price: {min_price}")
                return min_price
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for SheetPrice3. Error: {e}")
                if attempt == 1:
                    print("Error when getting SheetPrice3 after retries", e)
                    raise
                return None
        return None
    except Exception as e:
        print(f"Error processing SheetPrice3: {e}")
        return None


def _process_price4_sheet(row: Row) -> Optional[Tuple[float, str]]:
    try:
        print("Starting SheetPrice4 sheet...")
        for attempt in range(2):
            try:
                min_price = (row.s4.get_price()
                             * row.s4.SHEET_PROFIT
                             * row.s4.QUYDOIDONVI, "Get directly from sheet4")
                print(f"\nSheetPrice4 min price: {min_price}")
                return min_price
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for SheetPrice4. Error: {e}")
                if attempt == 1:
                    print("Error when getting SheetPrice4 after retries", e)
                    raise
                return None
        return None
    except Exception as e:
        print(f"Error processing SheetPrice4: {e}")
        return None


def _process_dd(row: Row, gsheet: GSheet) -> Optional[Tuple[float, str]]:
    try:
        print("Starting DD fetch...")
        dd_min_offer_item = None
        for attempt in range(2):
            try:
                dd_min_offer_item = get_dd_min_price(row.dd)
                break
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for DD. Error: {e}")
                if attempt == 1:
                    print("Error when getting DD after retries", e)
                    raise
        return dd_min_offer_item
    except Exception as e:
        print(f"Error processing DD: {e}")
        return None


@retry(retries=2, delay=0.1)
@time_execution
def calculate_price_stock_fake(
        gsheet: GSheet,
        row: Row,
        hostdata: dict,
        selenium: SeleniumUtil,
) -> Tuple[Optional[Tuple[float, str]], List[Optional[Tuple[float, str]]]]:  # Trả về tuple(min_price, list_all_prices)
    print("DEBUG: Starting calculate_price_stock_fake...")
    g2g_future = None
    fun_future = None
    bij_future = None
    dd_future = None
    s1_future = None
    s2_future = None
    s3_future = None
    s4_future = None

    results = {}  # Dictionary để lưu kết quả theo nguồn

    # Sử dụng ThreadPoolExecutor để chạy song song
    # max_workers=3 để giới hạn số luồng bằng số nguồn dữ liệu
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        # Submit G2G task
        if row.g2g.G2G_CHECK == 1:
            print("Submitting G2G task...")
            g2g_future = executor.submit(_process_g2g, row, gsheet)

        # Submit FUN task
        if row.fun.FUN_CHECK == 1:
            print("Submitting FUN task...")
            fun_future = executor.submit(_process_fun, row, gsheet)

        # Submit BIJ task
        if row.bij.BIJ_CHECK == 1:
            print("Submitting BIJ task...")
            bij_future = executor.submit(_process_bij, row.bij, gsheet, hostdata, selenium)

        if row.dd.DD_CHECK == 1:
            print("Submitting DD task...")
            dd_future = executor.submit(_process_dd, row, gsheet)

        if row.s1.SHEET_CHECK == 1:
            print("Submitting SheetPrice1 task...")
            s1_future = executor.submit(_process_price1_sheet, row)

        if row.s2.SHEET_CHECK == 1:
            print("Submitting SheetPrice2 task...")
            s2_future = executor.submit(_process_price2_sheet, row)

        if row.s3.SHEET_CHECK == 1:
            print("Submitting SheetPrice3 task...")
            s3_future = executor.submit(_process_price3_sheet, row)

        if row.s4.SHEET_CHECK == 1:
            print("Submitting SheetPrice4 task...")
            s4_future = executor.submit(_process_price4_sheet, row)

        if g2g_future:
            try:
                results['g2g'] = g2g_future.result()  # Lấy kết quả từ luồng G2G
                print(f"G2G Result received: {results['g2g']}")
            except Exception as e:
                print(f"G2G task failed with exception: {e}")
                results['g2g'] = None
        else:
            results['g2g'] = None

        if fun_future:
            try:
                results['fun'] = fun_future.result()  # Lấy kết quả từ luồng FUN
                print(f"FUN Result received: {results['fun']}")
            except Exception as e:
                print(f"FUN task failed with exception: {e}")
                results['fun'] = None
        else:
            results['fun'] = None

        if bij_future:
            try:
                results['bij'] = bij_future.result()  # Lấy kết quả từ luồng BIJ
                print(f"BIJ Result received: {results['bij']}")
            except Exception as e:
                print(f"BIJ task failed with exception: {e}")
                results['bij'] = None
        else:
            results['bij'] = None

        if dd_future:
            try:
                results['dd'] = dd_future.result()  # Lấy kết quả từ luồng DD
                print(f"DD Result received: {results['dd']}")
            except Exception as e:
                print(f"DD task failed with exception: {e}")
                results['dd'] = None

        if s1_future:
            try:
                results['s1'] = s1_future.result()
                print(f"S1 Result received: {results['s1']}")
            except Exception as e:
                print(f"S1 task failed with exception: {e}")
                results['s1'] = None

        if s2_future:
            try:
                results['s2'] = s2_future.result()
                print(f"S2 Result received: {results['s2']}")
            except Exception as e:
                print(f"S2 task failed with exception: {e}")
                results['s2'] = None

        if s3_future:
            try:
                results['s3'] = s3_future.result()
                print(f"S3 Result received: {results['s3']}")
            except Exception as e:
                print(f"S3 task failed with exception: {e}")
                results['s3'] = None

        if s4_future:
            try:
                results['s4'] = s4_future.result()
                print(f"S4 Result received: {results['s4']}")
            except Exception as e:
                print(f"S4 task failed with exception: {e}")
                results['s4'] = None

    g2g_min_price = results.get('g2g')
    fun_min_price = results.get('fun')
    bij_min_price = results.get('bij')
    dd_min_price = results.get('dd')
    s1_min_price = results.get('s1')
    s2_min_price = results.get('s2')
    s3_min_price = results.get('s3')
    s4_min_price = results.get('s4')

    all_prices: List[Optional[Tuple[float, str]]] = [g2g_min_price, fun_min_price, bij_min_price, dd_min_price,
                                                     s1_min_price, s2_min_price, s3_min_price, s4_min_price]
    valid_prices = [p for p in all_prices if p is not None and p[0] > 0]

    if not valid_prices:
        print("No valid prices found from any source.")
        final_min_price = None
    else:
        final_min_price = min(valid_prices, key=lambda x: x[0])
        print(f"Overall minimum price: {final_min_price}")

    return final_min_price, all_prices
