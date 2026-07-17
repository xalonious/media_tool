import os

from .errors import ToolError
from .formats import (
    SUPPORTED_OUTPUT_EXTENSIONS,
    default_compressed_output_path,
    extension_from_path,
    human_bytes,
    media_kind_from_extension,
    validate_common_input,
    validate_distinct_paths,
    validate_output_dir,
)
from .images import compress_image
from .video import build_ffmpeg_arguments, run_ffmpeg


def report_size_change(input_path: str, output_path: str, action: str) -> None:
    before_size = os.path.getsize(input_path)
    after_size = os.path.getsize(output_path)
    difference = before_size - after_size
    percentage = (difference / before_size) * 100.0 if before_size else 0.0

    print(f"Successfully {action} '{input_path}' to '{output_path}'.")
    print(f"Original: {human_bytes(before_size)}")
    print(f"New:      {human_bytes(after_size)}")
    if difference >= 0:
        print(f"Saved:    {human_bytes(difference)} ({percentage:.2f}%)")
    else:
        print(f"Increase: {human_bytes(-difference)} ({-percentage:.2f}%)")


def compress_audio_video(
    input_path: str,
    input_kind: str,
    output_path: str,
) -> None:
    run_ffmpeg(build_ffmpeg_arguments(input_path, input_kind, output_path, True))
    report_size_change(input_path, output_path, "compressed")


def process_compress(input_path: str, output_path: str | None) -> None:
    source_ext, input_kind = validate_common_input(input_path)
    if not output_path:
        output_path = default_compressed_output_path(input_path)
    elif not extension_from_path(output_path):
        output_path = f"{output_path}.{source_ext}"

    output_ext = extension_from_path(output_path)
    if output_ext not in SUPPORTED_OUTPUT_EXTENSIONS:
        raise ToolError(f"The output extension '.{output_ext}' is not supported.")

    output_kind = media_kind_from_extension(output_ext)
    if output_kind != input_kind:
        raise ToolError(
            f"Compression must keep the same media type; got {input_kind} to {output_kind}."
        )

    validate_output_dir(output_path)
    validate_distinct_paths(input_path, output_path)
    if input_kind == "image":
        compress_image(input_path, output_path)
        report_size_change(input_path, output_path, "compressed")
    else:
        compress_audio_video(input_path, input_kind, output_path)
