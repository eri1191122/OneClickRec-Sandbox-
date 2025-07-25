# ==============================================
# 📁 logging_core.py
# ==============================================
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from logging import Logger, Handler, Filter
from typing import Optional, List

_LOGGERS = {}

def configure_logger(
    name: str = "OneClickRec",
    level: int = logging.INFO,
    log_file: str = "oneclickrec.log",
    max_bytes: int = 5_000_000,
    backup_count: int = 3,
    use_console: bool = True,
    use_file: bool = True,
    console_formatter: Optional[logging.Formatter] = None,
    file_formatter: Optional[logging.Formatter] = None,
    extra_handlers: Optional[List[Handler]] = None,
    filters: Optional[List[Filter]] = None,
) -> Logger:
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not console_formatter:
        console_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    if not file_formatter:
        file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    if use_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(console_formatter)
        if filters:
            for f in filters:
                ch.addFilter(f)
        logger.addHandler(ch)

    if use_file:
        os.makedirs(os.path.dirname(log_file) or '.', exist_ok=True)
        fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
        fh.setFormatter(file_formatter)
        if filters:
            for f in filters:
                fh.addFilter(f)
        logger.addHandler(fh)

    if extra_handlers:
        for handler in extra_handlers:
            logger.addHandler(handler)

    _LOGGERS[name] = logger
    return logger

def set_log_level(level: int, name: str = "OneClickRec"):
    logger = _LOGGERS.get(name) or logging.getLogger(name)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)

def get_logger(name: str = "OneClickRec") -> Logger:
    return _LOGGERS.get(name) or configure_logger(name)
