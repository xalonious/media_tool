import argparse
import math
import os

from .errors import ToolError


IMAGE_INPUT_EXTENSIONS = {
    "png", "jpg", "jpeg", "bmp", "gif", "ico", "tiff", "tif", "eps",
    "psd", "pcx", "webp", "ppm", "pgm", "pbm", "xbm", "tga", "msp",
    "pdf",
}
IMAGE_OUTPUT_EXTENSIONS = IMAGE_INPUT_EXTENSIONS - {"psd"}
AUDIO_EXTENSIONS = {
    "mp3", "wav", "flac", "aac", "m4a", "ogg", "opus", "wma", "aif",
    "aiff", "ac3",
}
VIDEO_EXTENSIONS = {
    "mp4", "m4v", "mov", "mkv", "webm", "avi", "wmv", "mpg", "mpeg",
    "flv", "ts", "m2ts", "ogv",
}
SUPPORTED_INPUT_EXTENSIONS = (
    IMAGE_INPUT_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
)
SUPPORTED_OUTPUT_EXTENSIONS = (
    IMAGE_OUTPUT_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
)


def human_bytes(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    size = float(n)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{n} B"


def extension_from_path(path: str) -> str:
    return os.path.splitext(path)[1].lower().lstrip(".")


def media_kind_from_extension(extension: str) -> str | None:
    extension = extension.lower().lstrip(".")
    if extension in IMAGE_INPUT_EXTENSIONS:
        return "image"
    if extension in AUDIO_EXTENSIONS:
        return "audio"
    if extension in VIDEO_EXTENSIONS:
        return "video"
    return None


def default_compressed_output_path(input_path: str) -> str:
    base, ext = os.path.splitext(input_path)
    if ext.lower() in {".wav", ".aif", ".aiff"}:
        ext = ".flac"
    return f"{base}_compressed{ext}"


def default_converted_output_path(input_path: str, output_extension: str) -> str:
    base, _ = os.path.splitext(input_path)
    output_extension = output_extension.lower().lstrip(".")
    return f"{base}_converted.{output_extension}"


def default_cut_output_path(input_path: str) -> str:
    base, ext = os.path.splitext(input_path)
    return f"{base}_cut{ext}"


def non_negative_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number of seconds") from exc
    if not math.isfinite(seconds) or seconds < 0:
        raise argparse.ArgumentTypeError("must be a finite, non-negative number")
    return seconds


def normalize_output_extension(output_path: str, desired_ext: str) -> str:
    desired_ext = desired_ext.lower().lstrip(".")
    if extension_from_path(output_path) != desired_ext:
        return os.path.splitext(output_path)[0] + "." + desired_ext
    return output_path


def validate_common_input(path: str) -> tuple[str, str]:
    if not os.path.isfile(path):
        raise ToolError(f"The file '{path}' does not exist.")

    source_ext = extension_from_path(path)
    source_kind = media_kind_from_extension(source_ext)
    if source_ext not in SUPPORTED_INPUT_EXTENSIONS or source_kind is None:
        raise ToolError(f"The source extension '.{source_ext}' is not supported.")
    return source_ext, source_kind


def validate_output_dir(output_path: str) -> None:
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        raise ToolError(f"The directory '{output_dir}' does not exist.")


def validate_distinct_paths(input_path: str, output_path: str) -> None:
    input_resolved = os.path.normcase(os.path.abspath(input_path))
    output_resolved = os.path.normcase(os.path.abspath(output_path))
    if input_resolved == output_resolved:
        raise ToolError("The output path must be different from the input path.")
