import concurrent.futures
import os
import re
from enum import Enum
from typing import Optional, Tuple, List, TypeVar, Type, Any

import gspread
from pydantic import BaseModel, ValidationError

from app.decorator.retry import retry
from app.decorator.time_execution import time_execution
from app.models.crwl_api_models import Product
from app.models.gsheet_model import G2G, BIJ, FUN, DD, PriceSheet1, PriceSheet2, PriceSheet3, PriceSheet4
from app.utils.biji_extract import bij_lowest_price
from app.utils.common_utils import getCNYRate
from app.utils.dd_utils import get_dd_min_price
from app.utils.fun_extract import fun_extract_offer_items, FUNOfferItem
from app.utils.g2g_extract import g2g_extract_offer_items, G2GOfferItem
from app.utils.ggsheet import (
    GSheet,
)
from app.utils.google_api import StockManager


class ExtraInfor:
    pass


class Seller(BaseModel):
    name: str | None
    feedback_count: int | None
    canGetFeedback: bool | None


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


class OfferItem(BaseModel):
    offer_id: str
    server: str
    seller: Seller | None
    delivery_time: DeliveryTime
    min_unit: int
    min_stock: int
    quantity: int
    price: float

    @staticmethod
    def min_offer_item(
        offer_items: list["OfferItem"],
    ) -> "OfferItem":
        min = offer_items[0]
        for offer_item in offer_items:
            if offer_item.price < min.price:  # type: ignore
                min = offer_item

        return min


def extract_integers_from_string(s):
    return [int(num) for num in re.findall(r"\d+", s)]


class BijOfferItem(BaseModel):
    username: str
    money: float
    gold: list
    min_gold: int
    max_gold: int
    dept: str
    time: str
    link: str
    type: str


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
        print(f"Found {len(g2g_offer_items)} G2G offer items")
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
        print(f"Found {len(fun_offer_items)} FUN offer items")
        filtered_fun_offer_items = FUNOfferItem.filter_valid_fun_offer_items(
            fun=row.fun,
            fun_offer_items=fun_offer_items,
            fun_blacklist=row.fun.get_blacklist(gsheet),
        )
        if filtered_fun_offer_items:
            fun_min_offer_item = FUNOfferItem.min_offer_item(filtered_fun_offer_items)
            fun_min_price = (
                round(
                    fun_min_offer_item.price * row.fun.FUN_PROFIT * row.fun.FUN_DISCOUNTFEE *
                    row.fun.FUN_HESONHANDONGIA,
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


def _process_bij(bij: BIJ, gsheet: GSheet, hostdata: dict) -> Optional[Tuple[float, str]]:
    try:
        print("Starting BIJ fetch...")
        CNY_RATE = getCNYRate()
        _black_list = bij.get_blacklist(gsheet)
        bij_min_offer_item = None
        for attempt in range(2):
            try:
                bij_min_offer_item = bij_lowest_price(hostdata, bij, black_list=_black_list)
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
) -> Tuple[Optional[Tuple[float, str]], List[Optional[Tuple[float, str]]]]:  # Trả về tuple(min_price, list_all_prices)
    # print("DEBUG: Starting calculate_price_stock_fake...")
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
            bij_future = executor.submit(_process_bij, row.bij, gsheet, hostdata)

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
                print(f"G2G Result received: {results['g2g']} USD")
            except Exception as e:
                print(f"G2G task failed with exception: {e}")
                results['g2g'] = None
        else:
            results['g2g'] = None

        if fun_future:
            try:
                results['fun'] = fun_future.result()  # Lấy kết quả từ luồng FUN
                print(f"FUN Result received: {results['fun']} USD")
            except Exception as e:
                print(f"FUN task failed with exception: {e}")
                results['fun'] = None
        else:
            results['fun'] = None

        if bij_future:
            try:
                results['bij'] = bij_future.result()  # Lấy kết quả từ luồng BIJ
                print(f"BIJ Result received: {results['bij']} USD")
            except Exception as e:
                print(f"BIJ task failed with exception: {e}")
                results['bij'] = None
        else:
            results['bij'] = None

        if dd_future:
            try:
                results['dd'] = dd_future.result()  # Lấy kết quả từ luồng DD
                print(f"DD Result received: {results['dd']} USD")
            except Exception as e:
                print(f"DD task failed with exception: {e}")
                results['dd'] = None

        if s1_future:
            try:
                results['s1'] = s1_future.result()
                print(f"S1 Result received: {results['s1']} USD")
            except Exception as e:
                print(f"S1 task failed with exception: {e}")
                results['s1'] = None

        if s2_future:
            try:
                results['s2'] = s2_future.result()
                print(f"S2 Result received: {results['s2']} USD")
            except Exception as e:
                print(f"S2 task failed with exception: {e}")
                results['s2'] = None

        if s3_future:
            try:
                results['s3'] = s3_future.result()
                print(f"S3 Result received: {results['s3']} USD")
            except Exception as e:
                print(f"S3 task failed with exception: {e}")
                results['s3'] = None

        if s4_future:
            try:
                results['s4'] = s4_future.result()
                print(f"S4 Result received: {results['s4']} USD")
            except Exception as e:
                print(f"S4 task failed with exception: {e}")
                results['s4'] = None

    g2g_min_price_usd = results.get('g2g')
    fun_min_price_usd = results.get('fun')
    bij_min_price_usd = results.get('bij')
    dd_min_price_usd = results.get('dd')
    s1_min_price_usd = results.get('s1')
    s2_min_price_usd = results.get('s2')
    s3_min_price_usd = results.get('s3')
    s4_min_price_usd = results.get('s4')
    # convert all this price if not None from usd to idr
    try:
        RATE_SHEET_ID = os.getenv("RATE_SHEET_ID")
        RATE_SHEET_NAME = os.getenv("RATE_SHEET_NAME")
        CELL_RATE_USD = os.getenv("CELL_RATE_USD")
        rate_sheet = StockManager(RATE_SHEET_ID)
        rate = rate_sheet.get_cell_float_value(f"'{RATE_SHEET_NAME}'!{CELL_RATE_USD}")
    except Exception:
        print("Error fetching exchange rate from Google Sheet, using default rate 16326.")
        rate = 16326
    print(f"Exchange rate used: {rate} IDR/USD")
    g2g_min_price = convert_usd_to_idr(g2g_min_price_usd, rate)
    fun_min_price = convert_usd_to_idr(fun_min_price_usd, rate)
    bij_min_price = convert_usd_to_idr(bij_min_price_usd, rate)
    dd_min_price = convert_usd_to_idr(dd_min_price_usd, rate)
    s1_min_price = convert_usd_to_idr(s1_min_price_usd, rate)
    s2_min_price = convert_usd_to_idr(s2_min_price_usd, rate)
    s3_min_price = convert_usd_to_idr(s3_min_price_usd, rate)
    s4_min_price = convert_usd_to_idr(s4_min_price_usd, rate)

    all_prices: List[Optional[Tuple[float, str, str]]] = [
        (price[0], price[1], source) if price is not None else None
        for price, source in zip(
            [g2g_min_price, fun_min_price, bij_min_price, dd_min_price, s1_min_price, s2_min_price, s3_min_price,
             s4_min_price],
            ['g2g', 'fun', 'bij', 'dd', 's1', 's2', 's3', 's4']
        )
    ]
    valid_prices = [p for p in all_prices if p is not None and p[0] > 0]

    if not valid_prices:
        print("No valid prices found from any source.")
        final_min_price = None
    else:
        final_min_price = min(valid_prices, key=lambda x: x[0])
        print(f"Overall minimum price: {final_min_price}")

    return final_min_price, valid_prices


def convert_usd_to_idr(price_in_usd: float | None, rate) -> list[Any] | None:
    """
    Converts a price from USD to IDR, handling None values.

    Args:
        price_in_usd: The price in USD, or None.

    Returns:
        The price in IDR rounded to the nearest whole number, or None if the input was None.
    """
    # Exchange rate as of July 2025. In a real-world application,
    # you would fetch this from a live API.
    USD_TO_IDR_RATE = rate

    if price_in_usd is None:
        return None

    # Calculate and round to the nearest whole Rupiah
    price = price_in_usd[0] * USD_TO_IDR_RATE
    return [round(price), price_in_usd[1]]  # Return as a tuple with the seller name


def get_row(worksheet: gspread.worksheet.Worksheet, row_index: int) -> Row:
    """
    Lấy dữ liệu từ một dòng và trả về một đối tượng Row có cấu trúc.

    Hàm này sẽ tìm nạp dữ liệu cho tất cả các model cần thiết (Product, G2G, ...)
    và tập hợp chúng vào một instance của lớp Row.
    """
    # Định nghĩa tất cả các lớp model cần thiết để tạo thành một Row
    model_classes_to_fetch = [
        G2G, FUN, BIJ, DD,
        PriceSheet1, PriceSheet2, PriceSheet3, PriceSheet4
    ]

    # Sử dụng hàm helper để lấy tất cả các instance model trong một lần gọi API
    model_instances = _get_models_from_row(
        worksheet=worksheet,
        model_classes=model_classes_to_fetch,
        row_index=row_index
    )

    # Tạo một map từ class -> instance để dễ dàng truy cập
    instance_map = {type(instance): instance for instance in model_instances}

    # Tạo và trả về đối tượng Row
    # Hàm sẽ báo lỗi nếu bất kỳ model nào không được tìm thấy
    return Row(
        row_index=row_index,
        g2g=instance_map[G2G],
        fun=instance_map[FUN],
        bij=instance_map[BIJ],
        dd=instance_map[DD],
        s1=instance_map[PriceSheet1],
        s2=instance_map[PriceSheet2],
        s3=instance_map[PriceSheet3],
        s4=instance_map[PriceSheet4],
    )


# --- HÀM HELPER: Logic lấy dữ liệu gốc, giờ là hàm nội bộ ---
T = TypeVar('T', bound='ColSheetModel')


def _get_models_from_row(
    worksheet: gspread.worksheet.Worksheet,
    model_classes: List[Type[T]],
    row_index: int,
) -> List[T]:
    """
    (Hàm nội bộ) Lấy dữ liệu cho nhiều model Pydantic từ một dòng duy nhất.
    """
    all_ranges = []
    model_field_info = []

    # --- Bước 1: Tổng hợp tất cả các ô cần lấy từ tất cả các model ---
    for model_cls in model_classes:
        mapping = model_cls.mapping_fields()
        if not mapping:
            continue

        field_names = list(mapping.keys())
        model_field_info.append({'class': model_cls, 'fields': field_names})

        for col_letter in mapping.values():
            all_ranges.append(f"{col_letter}{row_index}")

    if not all_ranges:
        return []

    # --- Bước 2: Thực hiện một lệnh batch_get duy nhất ---
    try:
        # `batch_get` trả về một danh sách các ma trận giá trị.
        # Ví dụ: [['A1_val']], [['B1_val']], [[]] (cho ô trống)
        query_results = worksheet.batch_get(all_ranges)
    except Exception as e:
        raise ValueError(f"Lỗi khi thực hiện batch_get từ Google Sheet: {e}")

    # --- FIX HERE: Xử lý đúng cấu trúc dữ liệu trả về ---
    all_values = []
    for value_matrix in query_results:
        value = None
        # Kiểm tra xem ma trận và dòng đầu tiên có tồn tại và có nội dung không
        if value_matrix and value_matrix[0]:
            value = value_matrix[0][0]

        # Xử lý chuỗi
        if isinstance(value, str):
            value = value.strip()
            # Coi chuỗi rỗng là None để nhất quán với ô trống
            if not value:
                value = None

        all_values.append(value)

    # --- Bước 3: Phân phối giá trị và khởi tạo các model ---
    validated_models = []
    current_position = 0

    for info in model_field_info:
        model_cls = info['class']
        field_names = info['fields']
        num_fields = len(field_names)

        model_values = all_values[current_position: current_position + num_fields]
        model_dict = dict(zip(field_names, model_values))

        model_dict["worksheet"] = worksheet
        model_dict["index"] = row_index

        try:
            validated_model = model_cls.model_validate(model_dict)
            validated_models.append(validated_model)
        except ValidationError as e:
            error_details = e.errors()
            raise ValidationError(
                f"Lỗi validate cho model '{model_cls.__name__}' tại dòng {row_index}. Chi tiết: {error_details}",
                model=model_cls
            ) from e

        current_position += num_fields

    return validated_models
