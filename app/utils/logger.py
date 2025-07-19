"""App logger and get logger function

object:
    logger: logging.Logger (entire app logger)

function:

    get_logger(
        name: str | None = None,
        level: int | str = logging.INFO,
        is_log_file: bool = False,
    )

"""

import os
import pathlib

import logging


def get_logger(
    name: str | None = None,
    level: int | str = logging.INFO,
    is_log_file: bool = False,
) -> logging.Logger:
    logger = logging.getLogger(name=name)
    logger.setLevel(level)

    handler = logging.StreamHandler()
    formater = logging.Formatter(fmt="%(asctime)s - %(levelname)s :: %(message)s")

    handler.setFormatter(formater)

    logger.addHandler(handler)

    if is_log_file:
        file_handler = logging.FileHandler(
            filename=pathlib.Path(__file__)
            .parent.parent.parent.joinpath("logs")
            .joinpath(os.environ["LOG_FILE_NAME"]),
            mode="a",
            encoding="utf-8",
        )
        file_handler.setFormatter(formater)
        logger.addHandler(file_handler)

    return logger


logger = get_logger(
    name=os.environ["LOG_NAME"],
    level=os.environ["LOG_LEVEL"],
    is_log_file=bool(os.environ["IS_LOG_FILE"] == "True"),
)
