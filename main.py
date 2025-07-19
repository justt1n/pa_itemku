import os

from datetime import datetime
import time

from dotenv import load_dotenv
from gspread.worksheet import Worksheet
from seleniumbase import SB


from app.utils.gsheet import worksheet
from app.models.gsheet_model import Product
from app.main_process import process
from pydantic import ValidationError
from app.utils.update_messages import last_update_message

def get_run_indexes(sheet: Worksheet) -> list[int]:
    run_indexes = []
    check_col = sheet.col_values(2)
    for idx, value in enumerate(check_col):
        idx += 1
        if isinstance(value, int):
            if value == 1:
                run_indexes.append(idx)
        if isinstance(value, str):
            try:
                int_value = int(value)
            except Exception:
                continue
            if int_value == 1:
                run_indexes.append(idx)

    return run_indexes


def main(sb):
    load_dotenv("setting.env")
    run_indexes = get_run_indexes(worksheet)
    print(f"Run index: {run_indexes}")
    for index in run_indexes:
        print(f"INDEX (ROW): {index}")
        try:
            product = Product.get(worksheet, index)

            process(sb, product, index)
            print(f"Sleep for {product.RELAX_TIME}s")
            time.sleep(product.RELAX_TIME)
        except ValidationError as e:
            print(f"VALIDATION ERROR AT ROW: {index}")
            print(e.errors())
            try:
                now = datetime.now()
                worksheet.batch_update(
                    [
                        {
                            "range": f"D{index}",
                            "values": [
                                [
                                    f"{last_update_message(now)}: VALIDATION ERROR AT ROW: {index}"
                                ]
                            ],
                        }
                    ]
                )
            except Exception as e:
                print(e)
                time.sleep(10)

        except Exception as e:
            print(f"FAILED AT ROW: {index}")
            try:
                now = datetime.now()
                worksheet.batch_update(
                    [
                        {
                            "range": f"D{index}",
                            "values": [[f"{last_update_message(now)}: FAILED: {e}"]],
                        }
                    ]
                )
            except Exception as e1:
                print(e1)
                time.sleep(10)
            logger.exception(e, exc_info=True)

        time.sleep(4)

    print(f"Sleep for {os.getenv('RELAX_TIME_EACH_ROUND', '10')}s")
    time.sleep(
        int(
            os.getenv(
                "RELAX_TIME_EACH_ROUND",
                "10",
            )
        )
    )


while True:
    try:
        with SB(headless=True, uc=True) as sb:
            url = "https://www.itemku.com/"
            sb.activate_cdp_mode(url)
            main(sb)
    except Exception:
        time.sleep(30)
