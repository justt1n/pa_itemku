import os
import shutil
from typing import List, Dict

import pandas as pd
from pydantic import BaseModel

from constants import TEMPLATE_FOLDER


class CurrencyTemplate(BaseModel):
    game: str | None
    server: str | None
    faction: str | None
    currency_per_unit: float
    total_units: float
    minimum_unit_per_order: float
    price_per_unit: float
    ValueForDiscount: str
    discount: str
    title: str
    duration: int
    delivery_guarantee: int
    delivery_instructions: str = ""
    description: str

    class Config:
        arbitrary_types_allowed = True


class ItemTemplate(BaseModel):
    game: str
    server: str | None
    faction: str | None
    item_category1: str | None
    item_category2: str | None
    item_category3: str | None
    item_per_unit: float
    unit_price: float
    total_units: float
    min_unit_per_order: float
    ValueForDiscount: str
    discount: str
    offer_duration: int
    delivery_guarantee: int
    delivery_info: str
    cover_image: str
    title: str
    description: str

    class Config:
        arbitrary_types_allowed = True


def load_template(template_name: str) -> pd.DataFrame:
    template_path = os.path.join(TEMPLATE_FOLDER, template_name)
    return pd.read_excel(template_path)


def write_template_to_file(file_path: str, template_df: pd.DataFrame):
    template_df.to_excel(file_path, index=False, sheet_name="offer details")


def currency_templates_to_dicts(templates: List[CurrencyTemplate]) -> List[Dict[str, any]]:
    return [template.model_dump(mode="json") for template in templates]


def item_templates_to_dicts(templates: List[ItemTemplate]) -> List[Dict[str, any]]:
    return [template.model_dump(mode="json") for template in templates]


# def write_data_to_xlsx(file_path: str, data: List[Dict[str, any]], mode: str):
#     # Read the first line of the existing file
#     first_line = None
#     if os.path.exists(file_path):
#         df_existing = pd.read_excel(file_path, nrows=0)  # Read only the header
#         if not df_existing.columns.empty:
#             first_line = df_existing.columns.tolist()  # Get the header as a list
#
#     # Create DataFrame using only the values from the dictionary
#     df_new = pd.DataFrame([list(d.values()) for d in data], columns=first_line)
#
#     # Modify the DataFrame based on the mode
#     if mode == "currency":
#         #split data into many list base on they on the same game
#         df_new = df_new.groupby("game").apply(lambda x: x.reset_index(drop=True))
#         #save to file
#         df_new.to_excel(file_path, index=False, sheet_name=f"{df_new['game'][0]}")
#
#     # Keep only the first value in the "Description" column
#     if "Description" in df_new.columns:
#         df_new.loc[1:, "Description"] = ""
#     #filter row with Price Per Unit == 0
#     try:
#         df_new = df_new[df_new["Price Per Unit"] != 0]
#         # filer Total Units > 10000 then set Total Units = 10000
#         df_new.loc[df_new["Total Units"] > 10000, "Total Units"] = 10000
#     except KeyError:
#         pass
#
#     # Write the new content to the file with the specified sheet name
#     df_new.to_excel(file_path, index=False, sheet_name="offer details")

def write_data_to_xlsx(file_path: str, data: List[Dict[str, any]]):
    """
    Writes data to separate Excel files based on the 'game' column value,
    with modifications based on the mode.

    Parameters:
        file_path (str): Path to save the Excel files.
        data (List[Dict[str, Any]]): List of dictionaries containing the data.
    """
    # Read the header (first line) of the existing file, if it exists
    first_line = None
    if os.path.exists(file_path):
        df_existing = pd.read_excel(file_path, nrows=0)  # Read only the header
        if not df_existing.columns.empty:
            first_line = df_existing.columns.tolist()  # Get the header as a list
    # remove file_path
    if os.path.exists(file_path):
        os.remove(file_path)
    # Create DataFrame using the provided data
    df_new = pd.DataFrame([list(d.values()) for d in data], columns=first_line)

    # Process based on the mode
    if "Game" in df_new.columns or "game" in df_new.columns:
        try:
            grouped = df_new.groupby("Game")
        except KeyError:
            grouped = df_new.groupby("game")
        for game, group in grouped:
            # Reset the index for each group
            game = str(game).replace(" / ", "_").replace(" ", "_").replace(":", "_")
            group.reset_index(drop=True, inplace=True)

            # Save each group to a separate Excel file
            if "Item Category 1" not in group.columns:
                if "Description" in group.columns:
                    group.loc[1:, "Description"] = ""
            # Ensure the "Description" column keeps only the first value
            try:
                if "Price Per Unit" in group.columns:
                    group = group[group["Price Per Unit"] != 0]
            except KeyError:
                print("The 'Price Per Unit' column is not present in the file")

            # Cap "Total Units" to a maximum of 10,000 if applicable
            if "Total Units" in group.columns:
                group.loc[group["Total Units"] > 10000, "Total Units"] = 10000
            game_file_path = os.path.join(os.path.dirname(file_path), f"{game}.xlsx")
            group.to_excel(game_file_path, index=False, sheet_name="offer details")
            print("saved to", game_file_path)
    else:
        raise ValueError("The 'Game' column is required for 'currency' mode or it not currency file")


def clear_output_directory(directory: str):
    if os.path.exists(directory):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                print(f"Deleted {file_path}")
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")


def list_files_in_output(directory: str):
    files = []
    exceptFile = ["new_currency_template.xlsx", "new_item_template.xlsx", "__init__.py"]
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path) and filename not in exceptFile:
            files.append(file_path)
    return files


def create_file_from_template(template_name: str, new_file_path: str, data: List[Dict[str, any]]):
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
    template_content = load_template(template_name)
    write_template_to_file(new_file_path, template_content)
    write_data_to_xlsx(new_file_path, data)


def read_xlsx_file(file_path: str) -> List[Dict[str, any]]:
    df = pd.read_excel(file_path)
    return df.to_dict(orient='records')


def write_xlsx_file(file_path: str, data: List[Dict[str, any]]):
    df = pd.DataFrame(data)
    df.to_excel(file_path, index=False)
    return True


def sample_usage():
    currency_templates = [
        CurrencyTemplate(game="OK", server="US", faction="Horde", currency_per_unit=1000, total_units=1000,
                         minimum_unit_per_order=100, price_per_unit=0.1, ValueForDiscount="USD", discount="5%",
                         title="Sell WoW Gold", duration=24, delivery_guarantee=24, description="Sell WoW Gold"),
        CurrencyTemplate(game="CHUa", server="US", faction="Alliance", currency_per_unit=1000, total_units=1000,
                         minimum_unit_per_order=100, price_per_unit=0.1, ValueForDiscount="USD", discount="5%",
                         title="Sell WoW Gold", duration=24, delivery_guarantee=24, description="Sell WoW Gold"),
        CurrencyTemplate(game="Ne", server="US", faction="Alliance", currency_per_unit=1000, total_units=1000,
                         minimum_unit_per_order=100, price_per_unit=0.1, ValueForDiscount="USD", discount="5%",
                         title="Sell WoW Gold", duration=24, delivery_guarantee=24, description="Sell WoW Gold"),
    ]

    # item_templates = [
    #     ItemTemplate(game="WoW7", server="US", faction="Horde", item_category1="Item1", item_category2="Item2",
    #                  item_category3="Item3", item_per_unit=100, unit_price=0.1, min_unit_per_order=10,
    #                  ValueForDiscount=0.1, discount=0.05, offer_duration=24, delivery_guarantee=24,
    #                  delivery_info="Face to Face", cover_image="cover.jpg", title="Sell WoW Item",
    #                  description="Sell WoW Item"),
    #     ItemTemplate(game="WoW8", server="US", faction="Alliance", item_category1="Item1", item_category2="Item2",
    #                  item_category3="Item3", item_per_unit=100, unit_price=0.1, min_unit_per_order=10,
    #                  ValueForDiscount=0.1, discount=0.05, offer_duration=24, delivery_guarantee=24,
    #                  delivery_info="Face to Face", cover_image="cover.jpg", title="Sell WoW Item",
    #                  description="Sell WoW Item"),
    # ]

    currency_data = currency_templates_to_dicts(currency_templates)
    # item_data = item_templates_to_dicts(item_templates)
    clear_output_directory("storage/pa_template/item")
    create_file_from_template("currency_template.xlsx", "storage/pa_template/currency/new_currency_template.xlsx",
                              currency_data)
    # create_file_from_template("item_template.xlsx", "storage/pa_template/item/new_item_template.xlsx", item_data)
    print(list_files_in_output("storage/pa_template/item"))


# sample_usage()
# if __name__ == "__main__":
#     sample_usage()
