from loguru import logger
import sys


def setup_logger():

    logger.remove()

    logger.add(
        sys.stdout,
        format="<green>{time}</green> | <level>{level}</level> | {message}",
        level="INFO"
    )

    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="7 days",
        level="INFO",
        encoding="utf-8"
    )

    return logger