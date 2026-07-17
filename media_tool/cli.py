import argparse
import sys

from .compression import process_compress
from .cutting import process_cut
from .errors import ToolError
from .formats import (
    SUPPORTED_OUTPUT_EXTENSIONS,
    default_converted_output_path,
    media_kind_from_extension,
    non_negative_seconds,
    normalize_output_extension,
    validate_common_input,
    validate_distinct_paths,
    validate_output_dir,
)
from .images import convert_image
from .video import convert_audio_video


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert and compress media, and cut sections from videos, with "
            "Pillow and FFmpeg."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  Convert an image:       python media_tool_cli.py convert -f photo.webp -e png
  Convert audio:          python media_tool_cli.py convert -f song.wav -e mp3
  Convert video:          python media_tool_cli.py convert -f clip.mov -e mp4
  Extract video audio:    python media_tool_cli.py convert -f clip.mp4 -e flac
  Compress automatically: python media_tool_cli.py compress -f clip.mp4
  Compress to WebM:       python media_tool_cli.py compress -f clip.mp4 -o smaller.webm
  Remove first 10 sec:    python media_tool_cli.py cut -f clip.mp4 --before 10
  Remove after 30 sec:    python media_tool_cli.py cut -f clip.mp4 --after 30
  Remove 10 through 20:   python media_tool_cli.py cut -f clip.mp4 --between 10 20

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
  python media_tool_cli.py convert -f photo.png -e webp
  python media_tool_cli.py convert -f music.flac -e mp3
  python media_tool_cli.py convert -f video.mkv -e mp4
  python media_tool_cli.py convert -f video.mp4 -e opus -o soundtrack.opus

Images can convert to images, audio to audio, and video to video or audio.
Without --output, the filename receives _converted and the selected extension.
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
        "-o",
        "--output",
        metavar="OUTPUT",
        help="Optional output file path.",
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
  python media_tool_cli.py compress -f photo.jpg
  python media_tool_cli.py compress -f music.mp3 -o music_small.mp3
  python media_tool_cli.py compress -f video.mp4
  python media_tool_cli.py compress -f video.mp4 -o video_small.webm

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
  python media_tool_cli.py cut -f video.mp4 --before 10
  python media_tool_cli.py cut -f video.mp4 --after 30 -o first_30_seconds.mp4
  python media_tool_cli.py cut -f video.mp4 --between 10 20 -o without_middle.mp4

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


def process_convert(input_path: str, output_path: str | None, desired_ext: str) -> None:
    _, input_kind = validate_common_input(input_path)
    desired_ext = desired_ext.lower().lstrip(".")
    if desired_ext not in SUPPORTED_OUTPUT_EXTENSIONS:
        raise ToolError(f"The output extension '.{desired_ext}' is not supported.")

    if not output_path:
        output_path = default_converted_output_path(input_path, desired_ext)
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
