from collections.abc import Mapping
from typing import TypeVar

from .errors import ToolError


QUALITY_LEVELS = ("high", "medium", "low")
DEFAULT_QUALITY = "medium"

T = TypeVar("T")


def validate_quality(quality: str) -> str:
    if quality not in QUALITY_LEVELS:
        choices = ", ".join(QUALITY_LEVELS)
        raise ToolError(f"Quality must be one of: {choices}.")
    return quality


def quality_value(quality: str, values: Mapping[str, T]) -> T:
    return values[validate_quality(quality)]


def compression_value(
    compress: bool,
    quality: str,
    *,
    conversion: T,
    high: T,
    medium: T,
    low: T,
) -> T:
    if not compress:
        return conversion
    return quality_value(
        quality,
        {"high": high, "medium": medium, "low": low},
    )
