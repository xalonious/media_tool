from .errors import ToolError


def audio_codec_arguments(extension: str, compress: bool) -> list[str]:
    if extension == "mp3":
        return ["-c:a", "libmp3lame", "-q:a", "5" if compress else "2"]
    if extension in {"aac", "m4a"}:
        return ["-c:a", "aac", "-b:a", "128k" if compress else "192k"]
    if extension == "flac":
        return ["-c:a", "flac", "-compression_level", "8" if compress else "5"]
    if extension == "ogg":
        return ["-c:a", "libvorbis", "-q:a", "4" if compress else "6"]
    if extension == "opus":
        return ["-c:a", "libopus", "-b:a", "96k" if compress else "128k"]
    if extension == "wma":
        return ["-c:a", "wmav2", "-b:a", "128k" if compress else "192k"]
    if extension == "ac3":
        return ["-c:a", "ac3", "-b:a", "192k" if compress else "256k"]
    if extension == "wav":
        return ["-c:a", "pcm_s16le"]
    if extension in {"aif", "aiff"}:
        return ["-c:a", "pcm_s16be"]
    raise ToolError(f"No audio encoder preset is configured for '.{extension}'.")
