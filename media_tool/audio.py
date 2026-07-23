from .format_registry import encoder_arguments
from .quality import DEFAULT_QUALITY


def audio_codec_arguments(
    extension: str,
    compress: bool,
    quality: str = DEFAULT_QUALITY,
) -> list[str]:
    return encoder_arguments(extension, "audio", compress, quality)
