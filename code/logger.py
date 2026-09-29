# -*- coding: utf-8 -*-
"""
Structured Logging Module for F1 Digital Twin
Provides standard, production-grade logging with credential masking and zero secret leakage.
"""

import logging
import sys
import os
from config import config


class SecretMaskingFilter(logging.Filter):
    """Filter that inspects log messages and masks passwords / credentials."""

    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = config.mask_secret(record.msg)
        if record.args:
            masked_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    masked_args.append(config.mask_secret(arg))
                else:
                    masked_args.append(arg)
            record.args = tuple(masked_args)
        return True


def setup_logger(name: str = "f1_app") -> logging.Logger:
    """Configures and returns a production logger."""
    logger = logging.getLogger(name)
    logger.setLevel(config.get_log_level())

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(config.get_log_level())
        
        # Configure formatter
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        handler.addFilter(SecretMaskingFilter())
        logger.addHandler(handler)

    return logger


# Default application logger
app_logger = setup_logger("f1_digital_twin")
