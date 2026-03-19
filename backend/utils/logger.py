"""
PhysioAI Lab — Logger Utility
Centralized logging configuration using loguru
"""

import sys
import logging
from loguru import logger as loguru_logger


def setup_logger(name: str = "physioai") -> logging.Logger:
    """Configure and return a standard Python logger backed by loguru."""

    # Remove default loguru handler
    loguru_logger.remove()

    # Pretty console output
    loguru_logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level="DEBUG",
        colorize=True,
    )

    # File rotation
    loguru_logger.add(
        "logs/physioai_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO",
        encoding="utf-8",
    )

    # Bridge to standard logging
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                level = loguru_logger.level(record.levelname).name
            except ValueError:
                level = record.levelno
            frame, depth = sys._getframe(6), 6
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            loguru_logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    std_logger = logging.getLogger(name)
    std_logger.handlers = [InterceptHandler()]
    std_logger.setLevel(logging.DEBUG)
    std_logger.propagate = False
    return std_logger
