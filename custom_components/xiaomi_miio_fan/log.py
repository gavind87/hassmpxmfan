"""Logging helper that tags every message as coming from this integration."""

from __future__ import annotations

import logging
from typing import Any

LOG_TAG = "[XIAOMI_MIIO_FAN]"


class _TaggedAdapter(logging.LoggerAdapter):
    """Prefix every message with LOG_TAG so it is obvious in the HA log."""

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        return f"{LOG_TAG} {msg}", kwargs


def get_logger(name: str) -> logging.LoggerAdapter:
    """Return a tagged logger.

    The underlying logger keeps its normal name, so
    ``logger: logs: custom_components.xiaomi_miio_fan: debug`` still works.
    """
    return _TaggedAdapter(logging.getLogger(name), {})
