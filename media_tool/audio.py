from .errors import ToolError
from .quality import DEFAULT_QUALITY, compression_value


def audio_codec_arguments(
    extension: str,
    compress: bool,
    quality: str = DEFAULT_QUALITY,
) -> list[str]:
    if extension == "mp3":
        setting = compression_value(
            compress, quality, conversion="2", high="2", medium="5", low="7"
        )
        return ["-c:a", "libmp3lame", "-q:a", setting]
    if extension in {"aac", "m4a"}:
        setting = compression_value(
            compress,
            quality,
            conversion="192k",
            high="192k",
            medium="128k",
            low="96k",
        )
        return ["-c:a", "aac", "-b:a", setting]
    if extension == "flac":
        return ["-c:a", "flac", "-compression_level", "8" if compress else "5"]
    if extension == "ogg":
        setting = compression_value(
            compress, quality, conversion="6", high="6", medium="4", low="2"
        )
        return ["-c:a", "libvorbis", "-q:a", setting]
    if extension == "opus":
        setting = compression_value(
            compress,
            quality,
            conversion="128k",
            high="128k",
            medium="96k",
            low="64k",
        )
        return ["-c:a", "libopus", "-b:a", setting]
    if extension == "wma":
        setting = compression_value(
            compress,
            quality,
            conversion="192k",
            high="192k",
            medium="128k",
            low="96k",
        )
        return ["-c:a", "wmav2", "-b:a", setting]
    if extension == "ac3":
        setting = compression_value(
            compress,
            quality,
            conversion="256k",
            high="256k",
            medium="192k",
            low="128k",
        )
        return ["-c:a", "ac3", "-b:a", setting]
    if extension == "wav":
        return ["-c:a", "pcm_s16le"]
    if extension in {"aif", "aiff"}:
        return ["-c:a", "pcm_s16be"]
    raise ToolError(f"No audio encoder preset is configured for '.{extension}'.")
