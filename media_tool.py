import argparse
import json
import math
import os
import subprocess
import sys
from PIL import Image

from media_runtime import MediaRuntimeError, require_ffmpeg, require_ffprobe


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

PILLOW_FORMATS = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "tif": "TIFF",
    "tiff": "TIFF",
    "pgm": "PPM",
    "pbm": "PPM",
    "ppm": "PPM",
}


class ToolError(RuntimeError):
    """A user-facing media tool error."""


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
    # WAV and AIFF contain uncompressed PCM in normal use. FLAC gives them a
    # useful lossless compression default instead of merely rewriting the PCM.
    if ext.lower() in {".wav", ".aif", ".aiff"}:
        ext = ".flac"
    return f"{base}_compressed{ext}"


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert and compress media, and cut sections from videos, with "
            "Pillow and FFmpeg."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  Convert an image:       python media_tool.py convert -f photo.webp -e png -o photo.png
  Convert audio:          python media_tool.py convert -f song.wav -e mp3 -o song.mp3
  Convert video:          python media_tool.py convert -f clip.mov -e mp4 -o clip.mp4
  Extract video audio:    python media_tool.py convert -f clip.mp4 -e flac -o audio.flac
  Compress automatically: python media_tool.py compress -f clip.mp4
  Compress to WebM:       python media_tool.py compress -f clip.mp4 -o smaller.webm
  Remove first 10 sec:    python media_tool.py cut -f clip.mp4 --before 10
  Remove after 30 sec:    python media_tool.py cut -f clip.mp4 --after 30
  Remove 10 through 20:   python media_tool.py cut -f clip.mp4 --between 10 20

supported formats:
  Images: png, jpg/jpeg, bmp, gif, ico, tif/tiff, eps, pcx, webp,
          ppm/pgm/pbm, xbm, tga, msp, pdf (PSD is input-only)
  Audio:  mp3, wav, flac, aac, m4a, ogg, opus, wma, aif/aiff, ac3
  Video:  mp4/m4v, mov, mkv, webm, avi, wmv, mpg/mpeg, flv,
          ts/m2ts, ogv

notes:
  Audio and video operations require FFmpeg. Run python bootstrap.py once
  if FFmpeg is not already installed. WAV and AIFF compression defaults to
  lossless FLAC. Run a command with --help for all of its options.
""",
    )
    subparsers = parser.add_subparsers(
        dest="action", required=True, title="commands", metavar="COMMAND"
    )

    convert = subparsers.add_parser(
        "convert",
        help="Convert a file to another format.",
        description=(
            "Convert within a media type, or extract audio from a video. "
            "The output extension selects the encoder and container."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python media_tool.py convert -f photo.png -e webp -o photo.webp
  python media_tool.py convert -f music.flac -e mp3 -o music.mp3
  python media_tool.py convert -f video.mkv -e mp4 -o video.mp4
  python media_tool.py convert -f video.mp4 -e opus -o soundtrack.opus

Images can convert to images, audio to audio, and video to video or audio.
""",
    )
    convert.add_argument(
        "-f", "--file", required=True, metavar="INPUT", help="Input media file."
    )
    convert.add_argument(
        "-e",
        "--extension",
        required=True,
        metavar="EXT",
        help="Output extension without a leading dot, such as png, mp3, mp4, or webm.",
    )
    convert.add_argument(
        "-o", "--output", required=True, metavar="OUTPUT", help="Output file path."
    )

    compress = subparsers.add_parser(
        "compress",
        help="Compress a file with format-specific defaults.",
        description=(
            "Compress an image, audio file, or video with sensible defaults. "
            "The result may be larger when the source is already highly compressed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python media_tool.py compress -f photo.jpg
  python media_tool.py compress -f music.mp3 -o music_small.mp3
  python media_tool.py compress -f video.mp4
  python media_tool.py compress -f video.mp4 -o video_small.webm

Without --output, the filename receives _compressed. WAV and AIFF inputs
use FLAC as the default output so their PCM audio is compressed losslessly.
""",
    )
    compress.add_argument(
        "-f", "--file", required=True, metavar="INPUT", help="Input media file."
    )
    compress.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        help="Optional output path or alternate format.",
    )

    cut = subparsers.add_parser(
        "cut",
        help="Remove a section from a video.",
        description=(
            "Remove everything before or after a timestamp, or remove the "
            "section between two timestamps and join the remaining pieces."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python media_tool.py cut -f video.mp4 --before 10
  python media_tool.py cut -f video.mp4 --after 30 -o first_30_seconds.mp4
  python media_tool.py cut -f video.mp4 --between 10 20 -o without_middle.mp4

Timestamps are seconds and may contain decimals. Without --output, the output
filename receives _cut. Cuts are re-encoded for frame-accurate results.
""",
    )
    cut.add_argument(
        "-f", "--file", required=True, metavar="INPUT", help="Input video file."
    )
    cut.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        help="Optional output video path or alternate video format.",
    )
    cut_mode = cut.add_mutually_exclusive_group(required=True)
    cut_mode.add_argument(
        "--before",
        type=non_negative_seconds,
        metavar="SECONDS",
        help="Remove everything before this timestamp.",
    )
    cut_mode.add_argument(
        "--after",
        type=non_negative_seconds,
        metavar="SECONDS",
        help="Remove everything after this timestamp.",
    )
    cut_mode.add_argument(
        "--between",
        type=non_negative_seconds,
        nargs=2,
        metavar=("START", "END"),
        help="Remove this time range and join the remaining pieces.",
    )

    return parser


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


def pillow_format(extension: str) -> str:
    return PILLOW_FORMATS.get(extension, extension.upper())


def convert_image(input_path: str, output_path: str, output_format: str) -> None:
    try:
        with Image.open(input_path) as image:
            print(
                f"Opened image: {input_path} "
                f"(Format: {image.format}, Mode: {image.mode})"
            )
            if output_format in {"jpg", "jpeg"} and image.mode in {"RGBA", "P", "LA"}:
                image = image.convert("RGB")
            if output_format == "pdf":
                image.save(output_path, "PDF", resolution=100.0)
            else:
                image.save(output_path, pillow_format(output_format))
    except (OSError, ValueError) as exc:
        raise ToolError(f"Image conversion failed: {exc}") from exc

    print(f"Successfully converted '{input_path}' to '{output_path}'.")


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


def compress_image(input_path: str, output_path: str) -> None:
    output_ext = extension_from_path(output_path)
    try:
        with Image.open(input_path) as image:
            print(
                f"Opened image: {input_path} "
                f"(Format: {image.format}, Mode: {image.mode})"
            )
            if output_ext in {"jpg", "jpeg"}:
                if image.mode in {"RGBA", "P", "LA"}:
                    image = image.convert("RGB")
                image.save(
                    output_path,
                    "JPEG",
                    quality=85,
                    optimize=True,
                    progressive=True,
                )
            elif output_ext == "png":
                image.save(output_path, "PNG", optimize=True, compress_level=9)
            elif output_ext == "webp":
                image.save(output_path, "WEBP", quality=82, method=6)
            else:
                try:
                    image.save(output_path, pillow_format(output_ext), optimize=True)
                except TypeError:
                    image.save(output_path, pillow_format(output_ext))
    except (OSError, ValueError) as exc:
        raise ToolError(f"Image compression failed: {exc}") from exc

    report_size_change(input_path, output_path, "compressed")


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


def build_cut_arguments(
    input_path: str,
    output_path: str,
    mode: str,
    start: float,
    end: float | None,
    has_audio: bool,
) -> list[str]:
    output_ext = extension_from_path(output_path)
    codecs = video_codec_arguments(output_ext, False)
    start_text = ffmpeg_seconds(start)

    if mode == "before":
        return [
            "-ss", start_text, "-i", input_path, *codecs,
            "-map_metadata", "0", output_path,
        ]
    if mode == "after":
        return [
            "-i", input_path, "-t", start_text, *codecs,
            "-map_metadata", "0", output_path,
        ]
    if mode != "between" or end is None:
        raise ValueError("A between cut requires both start and end timestamps.")

    end_text = ffmpeg_seconds(end)
    if has_audio:
        filter_graph = (
            f"[0:v:0]trim=end={start_text},setpts=PTS-STARTPTS[v0];"
            f"[0:a:0]atrim=end={start_text},asetpts=PTS-STARTPTS[a0];"
            f"[0:v:0]trim=start={end_text},setpts=PTS-STARTPTS[v1];"
            f"[0:a:0]atrim=start={end_text},asetpts=PTS-STARTPTS[a1];"
            "[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]"
        )
        maps = ["-map", "[outv]", "-map", "[outa]"]
    else:
        filter_graph = (
            f"[0:v:0]trim=end={start_text},setpts=PTS-STARTPTS[v0];"
            f"[0:v:0]trim=start={end_text},setpts=PTS-STARTPTS[v1];"
            "[v0][v1]concat=n=2:v=1:a=0[outv]"
        )
        maps = ["-map", "[outv]"]
    return [
        "-i", input_path, "-filter_complex", filter_graph, *maps, *codecs,
        "-map_metadata", "0", output_path,
    ]


def convert_audio_video(
    input_path: str,
    input_kind: str,
    output_path: str,
) -> None:
    run_ffmpeg(build_ffmpeg_arguments(input_path, input_kind, output_path, False))
    print(f"Successfully converted '{input_path}' to '{output_path}'.")


def compress_audio_video(
    input_path: str,
    input_kind: str,
    output_path: str,
) -> None:
    run_ffmpeg(build_ffmpeg_arguments(input_path, input_kind, output_path, True))
    report_size_change(input_path, output_path, "compressed")


def process_convert(input_path: str, output_path: str, desired_ext: str) -> None:
    _, input_kind = validate_common_input(input_path)
    desired_ext = desired_ext.lower().lstrip(".")
    if desired_ext not in SUPPORTED_OUTPUT_EXTENSIONS:
        raise ToolError(f"The output extension '.{desired_ext}' is not supported.")

    output_path = normalize_output_extension(output_path, desired_ext)
    validate_output_dir(output_path)
    validate_distinct_paths(input_path, output_path)
    output_kind = media_kind_from_extension(desired_ext)

    if input_kind == "image" and output_kind == "image":
        convert_image(input_path, output_path, desired_ext)
    elif input_kind in {"audio", "video"} and output_kind in {"audio", "video"}:
        convert_audio_video(input_path, input_kind, output_path)
    else:
        raise ToolError(
            f"Conversion from {input_kind} to {output_kind or 'unknown media'} is not supported."
        )


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
    else:
        compress_audio_video(input_path, input_kind, output_path)


def process_cut(
    input_path: str,
    output_path: str | None,
    before: float | None,
    after: float | None,
    between: list[float] | None,
) -> None:
    source_ext, input_kind = validate_common_input(input_path)
    if input_kind != "video":
        raise ToolError("The cut command only accepts video files.")

    if not output_path:
        output_path = default_cut_output_path(input_path)
    elif not extension_from_path(output_path):
        output_path = f"{output_path}.{source_ext}"
    output_ext = extension_from_path(output_path)
    if output_ext not in VIDEO_EXTENSIONS:
        raise ToolError(f"The output extension '.{output_ext}' is not a video format.")
    validate_output_dir(output_path)
    validate_distinct_paths(input_path, output_path)

    duration, has_audio = probe_video(input_path)
    tolerance = 0.001
    if before is not None:
        mode, start, end = "before", before, None
        if start <= 0 or start >= duration - tolerance:
            raise ToolError(
                f"--before must be greater than 0 and less than the video "
                f"duration ({ffmpeg_seconds(duration)} seconds)."
            )
    elif after is not None:
        mode, start, end = "after", after, None
        if start <= 0 or start >= duration - tolerance:
            raise ToolError(
                f"--after must be greater than 0 and less than the video "
                f"duration ({ffmpeg_seconds(duration)} seconds)."
            )
    elif between is not None:
        start, end = between
        if start >= end:
            raise ToolError("The --between START timestamp must be before END.")
        if end > duration + tolerance:
            raise ToolError(
                f"The --between END timestamp exceeds the video duration "
                f"({ffmpeg_seconds(duration)} seconds)."
            )
        end = min(end, duration)
        if start <= tolerance and end >= duration - tolerance:
            raise ToolError("The --between range cannot remove the entire video.")
        if start <= tolerance:
            mode, start, end = "before", end, None
        elif end >= duration - tolerance:
            mode, start, end = "after", start, None
        else:
            mode = "between"
    else:
        raise ToolError("Choose --before, --after, or --between.")

    run_ffmpeg(
        build_cut_arguments(input_path, output_path, mode, start, end, has_audio)
    )
    print(f"Successfully cut '{input_path}' to '{output_path}'.")


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.action == "convert":
            process_convert(args.file, args.output, args.extension)
        elif args.action == "compress":
            process_compress(args.file, args.output)
        else:
            process_cut(
                args.file, args.output, args.before, args.after, args.between
            )
        return 0
    except ToolError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
