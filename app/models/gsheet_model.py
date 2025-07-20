from typing import Annotated, Self, Final

from gspread.worksheet import Worksheet
from pydantic import BaseModel, ConfigDict, Field

from app.shared.consts import COL_META_FIELD_NAME
from app.shared.exceptions import SheetError
from app.utils.ggsheet import GSheet
from app.utils.google_api import StockManager

IS_UPDATE_META: Final[str] = "is_update"


class ColSheetModel(BaseModel):
    # Model config
    model_config = ConfigDict(arbitrary_types_allowed=True)

    worksheet: Worksheet = Field(exclude=True)
    index: int

    @classmethod
    def mapping_fields(cls) -> dict:
        mapping_fields = {}
        for field_name, field_info in cls.model_fields.items():
            if hasattr(field_info, "metadata"):
                for metadata in field_info.metadata:
                    if COL_META_FIELD_NAME in metadata:
                        mapping_fields[field_name] = metadata[COL_META_FIELD_NAME]
                        break

        return mapping_fields

    @classmethod
    def update_mapping_fields(cls) -> dict:
        mapping_fields = {}
        for field_name, field_info in cls.model_fields.items():
            if hasattr(field_info, "metadata"):
                for metadata in field_info.metadata:
                    if COL_META_FIELD_NAME in metadata and IS_UPDATE_META in metadata:
                        mapping_fields[field_name] = metadata[COL_META_FIELD_NAME]
                        break

        return mapping_fields

    @classmethod
    def get(
            cls,
            worksheet: Worksheet,
            index: int,
    ) -> Self:
        mapping_dict = cls.mapping_fields()

        query_value = []

        for _, v in mapping_dict.items():
            query_value.append(f"{v}{index}")

        model_dict = {
            "index": index,
            "worksheet": worksheet,
        }

        query_results = worksheet.batch_get(query_value)
        count = 0
        for k, _ in mapping_dict.items():
            model_dict[k] = query_results[count].first()
            if isinstance(model_dict[k], str):
                model_dict[k] = model_dict[k].strip()
            count += 1
        return cls.model_validate(model_dict)

    def update(
            self,
    ) -> None:
        mapping_dict = self.update_mapping_fields()
        model_dict = self.model_dump(mode="json")

        update_batch = []
        for k, v in mapping_dict.items():
            update_batch.append(
                {
                    "range": f"{v}{self.index}",
                    "values": [[model_dict[k]]],
                }
            )

        self.worksheet.batch_update(update_batch)


class Product(ColSheetModel):
    # highlight: Annotated[str, {COL_META_FIELD_NAME: "A"}]
    CHECK: Annotated[int, {COL_META_FIELD_NAME: "B"}]
    Product_name: Annotated[str, {COL_META_FIELD_NAME: "C"}]
    Note: Annotated[str | None, {COL_META_FIELD_NAME: "D", IS_UPDATE_META: True}] = None
    Last_update: Annotated[
        str | None, {COL_META_FIELD_NAME: "E", IS_UPDATE_META: True}
    ] = None
    Product_link: Annotated[str, {COL_META_FIELD_NAME: "F"}]
    CHECK_PRODUCT_COMPARE: Annotated[int, {COL_META_FIELD_NAME: "G"}]
    PRODUCT_COMPARE: Annotated[str, {COL_META_FIELD_NAME: "H"}]
    DONGIAGIAM_MIN: Annotated[int, {COL_META_FIELD_NAME: "I"}]
    DONGIAGIAM_MAX: Annotated[int, {COL_META_FIELD_NAME: "J"}]
    DONGIA_LAMTRON: Annotated[int, {COL_META_FIELD_NAME: "K"}]
    IDSHEET_MIN: Annotated[str, {COL_META_FIELD_NAME: "L"}]
    SHEET_MIN: Annotated[str, {COL_META_FIELD_NAME: "M"}]
    CELL_MIN: Annotated[str, {COL_META_FIELD_NAME: "N"}]
    IDSHEET_MAX: Annotated[str | None, {COL_META_FIELD_NAME: "O"}] = None
    SHEET_MAX: Annotated[str | None, {COL_META_FIELD_NAME: "P"}] = None
    CELL_MAX: Annotated[str | None, {COL_META_FIELD_NAME: "Q"}] = None
    IDSHEET_STOCK: Annotated[str, {COL_META_FIELD_NAME: "R"}]
    SHEET_STOCK: Annotated[str, {COL_META_FIELD_NAME: "S"}]
    CELL_STOCK: Annotated[str, {COL_META_FIELD_NAME: "T"}]
    IDSHEET_BLACKLIST: Annotated[str, {COL_META_FIELD_NAME: "U"}]
    SHEET_BLACKLIST: Annotated[str, {COL_META_FIELD_NAME: "V"}]
    CELL_BLACKLIST: Annotated[str, {COL_META_FIELD_NAME: "W"}]
    RELAX_TIME: Annotated[int, {COL_META_FIELD_NAME: "X"}]
    INCLUDE_KEYWORD: Annotated[str | None, {COL_META_FIELD_NAME: "Y"}] = None
    EXCLUDE_KEYWORD: Annotated[str | None, {COL_META_FIELD_NAME: "Z"}] = None

    def min_price(self) -> int:
        sheet_manager = StockManager(self.IDSHEET_MIN)
        min_price = sheet_manager.get_cell_float_value(f"'{self.SHEET_MIN}'!{self.CELL_MIN}")

        if min_price is not None:
            return int(min_price)

        raise SheetError(
            f"{self.IDSHEET_MIN}->{self.SHEET_MIN}->{self.CELL_MIN} is None"
        )

    def max_price(self) -> int | None:
        if self.IDSHEET_MAX is None or self.SHEET_MAX is None or self.CELL_MAX is None:
            return None

        sheet_manager = StockManager(self.IDSHEET_MAX)
        max_price = sheet_manager.get_cell_float_value(f"'{self.SHEET_MAX}'!{self.CELL_MAX}")

        if max_price is not None:
            return int(max_price)

        raise SheetError(
            f"{self.IDSHEET_MAX}->{self.SHEET_MAX}->{self.CELL_MAX} is None"
        )

    def stock(self) -> int:
        if self.IDSHEET_STOCK is None or self.SHEET_STOCK is None or self.CELL_STOCK is None:
            raise SheetError(
                f"{self.IDSHEET_STOCK}->{self.SHEET_STOCK}->{self.CELL_STOCK} is None"
            )

        sheet_manager = StockManager(self.IDSHEET_STOCK)
        stock = sheet_manager.get_cell_float_value(f"'{self.SHEET_STOCK}'!{self.CELL_STOCK}")

        if stock is not None:
            return int(stock)

        raise SheetError(
            f"{self.IDSHEET_STOCK}->{self.SHEET_STOCK}->{self.CELL_STOCK} is None"
        )

    def blacklist(self) -> list[str]:
        if self.IDSHEET_BLACKLIST is None or self.SHEET_BLACKLIST is None or self.CELL_BLACKLIST is None:
            raise SheetError(
                f"{self.IDSHEET_BLACKLIST}->{self.SHEET_BLACKLIST}->{self.CELL_BLACKLIST} is None"
            )

        sheet_manager = StockManager(self.IDSHEET_BLACKLIST)
        blacklist = sheet_manager.get_multiple_str_cells(f"'{self.SHEET_BLACKLIST}'!{self.CELL_BLACKLIST}")

        if blacklist:
            return blacklist

        raise SheetError(
            f"{self.IDSHEET_BLACKLIST}->{self.SHEET_BLACKLIST}->{self.CELL_BLACKLIST} is None"
        )


class G2G(ColSheetModel):
    G2G_CHECK: Annotated[int, {COL_META_FIELD_NAME: "AA"}]
    G2G_PROFIT: Annotated[float, {COL_META_FIELD_NAME: "AB"}]
    G2G_PRODUCT_COMPARE: Annotated[str, {COL_META_FIELD_NAME: "AC"}]
    G2G_DELIVERY_TIME: Annotated[int, {COL_META_FIELD_NAME: "AD"}]
    G2G_STOCK: Annotated[int, {COL_META_FIELD_NAME: "AE"}]
    G2G_MINUNIT: Annotated[int, {COL_META_FIELD_NAME: "AF"}]
    G2G_QUYDOIDONVI: Annotated[float, {COL_META_FIELD_NAME: "AG"}]
    G2G_IDSHEET_BLACKLIST: Annotated[str | None, {COL_META_FIELD_NAME: "AH"}] = None
    G2G_SHEET_BLACKLIST: Annotated[str | None, {COL_META_FIELD_NAME: "AI"}] = None
    G2G_CELL_BLACKLIST: Annotated[str | None, {COL_META_FIELD_NAME: "AJ"}] = None

    def get_blacklist(
            self,
            gsheet: GSheet,
    ) -> list[str]:
        sheet_manager = StockManager(self.G2G_IDSHEET_BLACKLIST)
        blacklist = sheet_manager.get_multiple_str_cells(f"'{self.G2G_SHEET_BLACKLIST}'!{self.G2G_CELL_BLACKLIST}")
        # blacklist = [item for sublist in query_values for item in sublist]
        return blacklist


# BE BF BG BH BI BJ BK BL BM BN BO BP BQ BR BS
class FUN(ColSheetModel):
    FUN_CHECK: Annotated[int, {COL_META_FIELD_NAME: "AK"}]
    FUN_PROFIT: Annotated[float, {COL_META_FIELD_NAME: "AL"}]
    FUN_DISCOUNTFEE: Annotated[float, {COL_META_FIELD_NAME: "AM"}]
    FUN_PRODUCT_COMPARE: Annotated[str, {COL_META_FIELD_NAME: "AN"}]
    NAME2: Annotated[str | None, {COL_META_FIELD_NAME: "AO"}] = None
    FACTION: Annotated[str, {COL_META_FIELD_NAME: "AP"}]
    FUN_FILTER21: Annotated[str | None, {COL_META_FIELD_NAME: "AQ"}] = None
    FUN_FILTER22: Annotated[str | None, {COL_META_FIELD_NAME: "AR"}] = None
    FUN_FILTER23: Annotated[str | None, {COL_META_FIELD_NAME: "AS"}] = None
    FUN_FILTER24: Annotated[str | None, {COL_META_FIELD_NAME: "AT"}] = None
    FUN_HESONHANDONGIA: Annotated[float | None, {COL_META_FIELD_NAME: "AU"}] = None
    FUN_STOCK: Annotated[int, {COL_META_FIELD_NAME: "AV"}]
    FUN_IDSHEET_BLACKLIST: Annotated[str | None, {COL_META_FIELD_NAME: "AW"}] = None
    FUN_SHEET_BLACKLIST: Annotated[str | None, {COL_META_FIELD_NAME: "AX"}] = None
    FUN_CELL_BLACKLIST: Annotated[str | None, {COL_META_FIELD_NAME: "AY"}] = None

    def get_blacklist(self) -> list[str]:
        sheet_manager = StockManager(self.FUN_IDSHEET_BLACKLIST)
        blacklist = sheet_manager.get_multiple_str_cells(f"'{self.FUN_SHEET_BLACKLIST}'!{self.FUN_CELL_BLACKLIST}")
        return blacklist


# BT BJ BV BW BX BY BZ CA CB CC CD
class BIJ(ColSheetModel):
    BIJ_CHECK: Annotated[int, {COL_META_FIELD_NAME: "AZ"}]
    BIJ_PROFIT: Annotated[float, {COL_META_FIELD_NAME: "BA"}]
    BIJ_NAME: Annotated[str | None, {COL_META_FIELD_NAME: "BB"}] = None
    BIJ_SERVER: Annotated[str | None, {COL_META_FIELD_NAME: "BC"}] = None
    BIJ_DELIVERY_METHOD: Annotated[str | None, {COL_META_FIELD_NAME: "BD"}] = None
    BIJ_STOCKMIN: Annotated[int, {COL_META_FIELD_NAME: "BE"}]
    BIJ_STOCKMAX: Annotated[int, {COL_META_FIELD_NAME: "BF"}]
    HESONHANDONGIA3: Annotated[float, {COL_META_FIELD_NAME: "BG"}]
    BIJ_IDSHEET_BLACKLIST: Annotated[str | None, {COL_META_FIELD_NAME: "BH"}] = None
    BIJ_SHEET_BLACKLIST: Annotated[str | None, {COL_META_FIELD_NAME: "BI"}] = None
    BIJ_CELL_BLACKLIST: Annotated[str | None, {COL_META_FIELD_NAME: "BJ"}] = None

    def get_blacklist(self, gsheet: GSheet) -> list[str]:
        sheet_manager = StockManager(self.BIJ_IDSHEET_BLACKLIST)
        blacklist = sheet_manager.get_multiple_str_cells(f"'{self.BIJ_SHEET_BLACKLIST}'!{self.BIJ_CELL_BLACKLIST}")
        return blacklist


# CS CT CU CV CW CX
class DD(ColSheetModel):
    DD_CHECK: Annotated[int, {COL_META_FIELD_NAME: "BK"}]
    DD_PROFIT: Annotated[float, {COL_META_FIELD_NAME: "BL"}]
    DD_QUYDOIDONVI: Annotated[float, {COL_META_FIELD_NAME: "BM"}]
    DD_PRODUCT_COMPARE: Annotated[str | None, {COL_META_FIELD_NAME: "BN"}] = None
    DD_STOCKMIN: Annotated[int, {COL_META_FIELD_NAME: "BO"}]
    DD_LEVELMIN: Annotated[int, {COL_META_FIELD_NAME: "BP"}]


class PriceSheet1(ColSheetModel):
    SHEET_CHECK: Annotated[int, {COL_META_FIELD_NAME: "BQ"}]
    SHEET_PROFIT: Annotated[float, {COL_META_FIELD_NAME: "BR"}]
    HE_SO_NHAN: Annotated[float, {COL_META_FIELD_NAME: "BS"}]
    QUYDOIDONVI: Annotated[float, {COL_META_FIELD_NAME: "BT"}]
    ID_SHEET_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "BU"}] = None
    SHEET_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "BV"}] = None
    CELL_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "BW"}] = None

    def get_price(self) -> float:
        sheet_manager = StockManager(self.ID_SHEET_PRICE)
        price = sheet_manager.get_cell_float_value(f"'{self.SHEET_PRICE}'!{self.CELL_PRICE}")
        return float(price)


class PriceSheet2(ColSheetModel):
    SHEET_CHECK: Annotated[int, {COL_META_FIELD_NAME: "BX"}]
    SHEET_PROFIT: Annotated[float, {COL_META_FIELD_NAME: "BY"}]
    HE_SO_NHAN: Annotated[float, {COL_META_FIELD_NAME: "BZ"}]
    QUYDOIDONVI: Annotated[float, {COL_META_FIELD_NAME: "CA"}]
    ID_SHEET_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "CB"}] = None
    SHEET_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "CC"}] = None
    CELL_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "CD"}] = None

    def get_price(self) -> float:
        sheet_manager = StockManager(self.ID_SHEET_PRICE)
        price = sheet_manager.get_cell_float_value(f"'{self.SHEET_PRICE}'!{self.CELL_PRICE}")
        return float(price)


class PriceSheet3(ColSheetModel):
    SHEET_CHECK: Annotated[int, {COL_META_FIELD_NAME: "CE"}]
    SHEET_PROFIT: Annotated[float, {COL_META_FIELD_NAME: "CF"}]
    HE_SO_NHAN: Annotated[float, {COL_META_FIELD_NAME: "CG"}]
    QUYDOIDONVI: Annotated[float, {COL_META_FIELD_NAME: "CH"}]
    ID_SHEET_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "CI"}] = None
    SHEET_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "CJ"}] = None
    CELL_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "CK"}] = None

    def get_price(self) -> float:
        sheet_manager = StockManager(self.ID_SHEET_PRICE)
        price = sheet_manager.get_cell_float_value(f"'{self.SHEET_PRICE}'!{self.CELL_PRICE}")
        return float(price)


class PriceSheet4(ColSheetModel):
    SHEET_CHECK: Annotated[int, {COL_META_FIELD_NAME: "CL"}]
    SHEET_PROFIT: Annotated[float, {COL_META_FIELD_NAME: "CM"}]
    HE_SO_NHAN: Annotated[float, {COL_META_FIELD_NAME: "CN"}]
    QUYDOIDONVI: Annotated[float, {COL_META_FIELD_NAME: "CO"}]
    ID_SHEET_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "CP"}] = None
    SHEET_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "CQ"}] = None
    CELL_PRICE: Annotated[str | None, {COL_META_FIELD_NAME: "CR"}] = None

    def get_price(self) -> float:
        sheet_manager = StockManager(self.ID_SHEET_PRICE)
        price = sheet_manager.get_cell_float_value(f"'{self.SHEET_PRICE}'!{self.CELL_PRICE}")
        return float(price)
