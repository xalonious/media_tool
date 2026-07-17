import json
import math
import os
import subprocess

from media_runtime import MediaRuntimeError, require_ffmpeg, require_ffprobe

from .audio import audio_codec_arguments
from .errors import ToolError
from .formats import extension_from_path, media_kind_from_extension


def video_codec_arguments(extension: str, compress: bool) -> list[str]:
    if extension in {"mp4", "m4v", "mov", "mkv", "ts", "m2ts"}:
        arguments = [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "28" if compress else "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k" if compress else "192k",
        ]
        if extension in {"mp4", "m4v", "mov"}:
            arguments.extend(["-movflags", "+faststart"])
        return arguments
    if extension == "webm":
        return [
            "-c:v", "libvpx-vp9",
            "-crf", "34" if compress else "28",
            "-b:v", "0",
            "-c:a", "libopus",
            "-b:a", "96k" if compress else "128k",
        ]
    if extension == "avi":
        return [
            "-c:v", "mpeg4",
            "-q:v", "6" if compress else "3",
            "-c:a", "libmp3lame",
            "-b:a", "128k" if compress else "192k",
        ]
    if extension == "wmv":
        return [
            "-c:v", "wmv2",
            "-b:v", "1M" if compress else "2M",
            "-c:a", "wmav2",
            "-b:a", "128k" if compress else "192k",
        ]
    if extension in {"mpg", "mpeg"}:
        return [
            "-c:v", "mpeg2video",
            "-q:v", "6" if compress else "3",
            "-c:a", "mp2",
            "-b:a", "128k" if compress else "192k",
        ]
    if extension == "flv":
        return [
            "-c:v", "flv1",
            "-q:v", "7" if compress else "4",
            "-c:a", "aac",
            "-b:a", "128k" if compress else "192k",
        ]
    if extension == "ogv":
        return [
            "-c:v", "libtheora",
            "-q:v", "5" if compress else "7",
            "-c:a", "libvorbis",
            "-q:a", "4" if compress else "6",
        ]
    raise ToolError(f"No video encoder preset is configured for '.{extension}'.")


def build_ffmpeg_arguments(
    input_path: str,
    input_kind: str,
    output_path: str,
    compress: bool,
) -> list[str]:
    output_ext = extension_from_path(output_path)
    output_kind = media_kind_from_extension(output_ext)
    arguments = ["-i", input_path]

    if output_kind == "audio":
        if input_kind not in {"audio", "video"}:
            raise ToolError("Only audio and video inputs can produce an audio file.")
        arguments.extend(["-vn", *audio_codec_arguments(output_ext, compress)])
    elif output_kind == "video":
        if input_kind != "video":
            raise ToolError("Only a video input can produce a video file.")
        arguments.extend(video_codec_arguments(output_ext, compress))
    else:
        raise ToolError("FFmpeg conversion requires an audio or video output format.")

    arguments.extend(["-map_metadata", "0", output_path])
    return arguments


def run_ffmpeg(arguments: list[str]) -> None:
    try:
        ffmpeg = require_ffmpeg()
    except MediaRuntimeError as exc:
        raise ToolError(str(exc)) from exc

    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *arguments,
    ]
    print("Processing with FFmpeg...")
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise ToolError(f"FFmpeg could not be started: {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.strip() or "FFmpeg exited without an error message."
        raise ToolError(f"FFmpeg failed:\n{message}")
    if not os.path.isfile(arguments[-1]):
        raise ToolError("FFmpeg reported success but did not create the output file.")


def probe_video(input_path: str) -> tuple[float, bool]:
    try:
        ffprobe = require_ffprobe()
    except MediaRuntimeError as exc:
        raise ToolError(str(exc)) from exc

    command = [
        str(ffprobe),
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type",
        "-of",
        "json",
        input_path,
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise ToolError(f"FFprobe could not be started: {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.strip() or "FFprobe exited without an error message."
        raise ToolError(f"Could not inspect the video:\n{message}")

    try:
        probe = json.loads(result.stdout)
        duration = float(probe["format"]["duration"])
        stream_types = {
            stream.get("codec_type") for stream in probe.get("streams", [])
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ToolError("Could not determine the video's duration.") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ToolError("The video does not report a usable duration.")
    if "video" not in stream_types:
        raise ToolError("The input does not contain a video stream.")
    return duration, "audio" in stream_types


def ffmpeg_seconds(seconds: float) -> str:
    return f"{seconds:.9f}".rstrip("0").rstrip(".")


def convert_audio_video(
    input_path: str,
    input_kind: str,
    output_path: str,
) -> None:
    run_ffmpeg(build_ffmpeg_arguments(input_path, input_kind, output_path, False))
    print(f"Successfully converted '{input_path}' to '{output_path}'.")
