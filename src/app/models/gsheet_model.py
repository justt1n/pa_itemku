import os
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, Self, Final
from gspread.worksheet import Worksheet
from gspread.auth import service_account

from app.shared.exceptions import SheetError
from app.shared.consts import COL_META_FIELD_NAME
from app.utils.paths import ROOT_PATH


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
        g_client = service_account(ROOT_PATH.joinpath(os.environ["KEYS_PATH"]))

        res = g_client.http_client.values_get(
            id=self.IDSHEET_MIN,
            range=f"{self.SHEET_MIN}!{self.CELL_MIN}",
            params={"valueRenderOption": "UNFORMATTED_VALUE"},
        )

        min_price = res.get("values", None)

        if min_price:
            return int(min_price[0][0])

        raise SheetError(
            f"{self.IDSHEET_MIN}->{self.SHEET_MIN}->{self.CELL_MIN} is None"
        )

    def max_price(self) -> int | None:
        if self.IDSHEET_MAX is None or self.SHEET_MAX is None or self.CELL_MAX is None:
            return None

        g_client = service_account(ROOT_PATH.joinpath(os.environ["KEYS_PATH"]))

        res = g_client.http_client.values_get(
            params={"valueRenderOption": "UNFORMATTED_VALUE"},
            id=self.IDSHEET_MAX,
            range=f"{self.SHEET_MAX}!{self.CELL_MAX}",
        )
        max_price = res.get("values", None)
        if max_price:
            return int(max_price[0][0])

        return None

    def stock(self) -> int:
        g_client = service_account(ROOT_PATH.joinpath(os.environ["KEYS_PATH"]))

        res = g_client.http_client.values_get(
            params={"valueRenderOption": "UNFORMATTED_VALUE"},
            id=self.IDSHEET_STOCK,
            range=f"{self.SHEET_STOCK}!{self.CELL_STOCK}",
        )

        stock = res.get("values", None)
        if stock:
            return int(stock[0][0])

        raise SheetError(
            f"{self.IDSHEET_MIN}->{self.SHEET_MIN}->{self.CELL_MIN} is None"
        )

    def blacklist(self) -> list[str]:
        g_client = service_account(ROOT_PATH.joinpath(os.environ["KEYS_PATH"]))

        spreadsheet = g_client.open_by_key(self.IDSHEET_BLACKLIST)

        worksheet = spreadsheet.worksheet(self.SHEET_BLACKLIST)

        blacklist = worksheet.batch_get([self.CELL_BLACKLIST])[0]
        if blacklist:
            res = []
            for blist in blacklist:
                for i in blist:
                    res.append(i)
            return res

        raise SheetError(
            f"{self.IDSHEET_BLACKLIST}->{self.IDSHEET_BLACKLIST}->{self.CELL_BLACKLIST} is None"
        )
