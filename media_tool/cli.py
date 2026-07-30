import argparse
import os
import sys

from .batch import (
    PlannedFile,
    SkippedFile,
    discover_inputs,
    output_in_directory,
    raise_preflight_errors,
    run_planned_batch,
    validate_output_collisions,
)
from .compression import process_compress
from .cutting import process_cut
from .errors import ToolError
from .formats import (
    SUPPORTED_OUTPUT_EXTENSIONS,
    default_converted_output_path,
    default_compressed_output_path,
    default_cut_output_path,
    extension_from_path,
    media_kind_from_extension,
    non_negative_seconds,
    normalize_output_extension,
    validate_common_input,
    validate_distinct_paths,
    validate_output_dir,
)
from .images import convert_image
from .quality import DEFAULT_QUALITY, QUALITY_LEVELS
from .video import convert_audio_video


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert and compress media, and cut sections from audio and video, with "
            "Pillow and FFmpeg."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  Convert images:         python media_tool_cli.py convert *.webp -e png
  Convert audio:          python media_tool_cli.py convert -f song.wav -e mp3
  Convert video:          python media_tool_cli.py convert -f clip.mov -e mp4
  Extract video audio:    python media_tool_cli.py convert -f clip.mp4 -e flac
  Compress a folder:      python media_tool_cli.py compress media/
  Compress to WebM:       python media_tool_cli.py compress -f clip.mp4 -o smaller.webm
  Remove first 10 sec:    python media_tool_cli.py cut clip.mp4 --before 10
  Remove after 30 sec:    python media_tool_cli.py cut -f clip.mp4 --after 30
  Remove 10 through 20:   python media_tool_cli.py cut -f clip.mp4 --between 10 20
  Keep only 10 to 15:     python media_tool_cli.py cut -f clip.mp4 --keep 10 15

supported formats:
  Images: png, jpg/jpeg/jpe/jfif, bmp/dib, gif, ico, tif/tiff, eps,
          pcx, webp, ppm/pgm/pbm, xbm, tga, msp, pdf (PSD is input-only)
  Audio:  mp3, wav, flac, aac, m4a, ogg/oga, opus, wma, aif/aiff,
          ac3/eac3, caf, tta, wv
  Video:  mp4/m4v, mov, mkv, webm, avi, wmv, mpg/mpeg, flv,
          ts/m2ts/mts, ogv, 3gp/3g2, vob

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
        help="Convert one or more media files to another format.",
        description=(
            "Convert within a media type, or extract audio from a video. "
            "The output extension selects the encoder and container."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python media_tool_cli.py convert photo.png -e webp
  python media_tool_cli.py convert photos/ -e webp --output-dir converted/
  python media_tool_cli.py convert -f music.flac -e mp3
  python media_tool_cli.py convert -f video.mkv -e mp4
  python media_tool_cli.py convert -f video.mp4 -e opus -o soundtrack.opus

Images can convert to images, audio to audio, and video to video or audio.
Without --output, the filename receives _converted and the selected extension.
""",
    )
    _add_input_arguments(convert)
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
        help="Optional output file path; only valid for a single input file.",
    )
    _add_batch_arguments(convert)

    compress = subparsers.add_parser(
        "compress",
        help="Compress one or more files with format-specific defaults.",
        description=(
            "Compress an image, audio file, or video with sensible defaults. "
            "The result may be larger when the source is already highly compressed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python media_tool_cli.py compress photo.jpg
  python media_tool_cli.py compress photo.jpg --quality high
  python media_tool_cli.py compress media/ --recursive --output-dir compressed/
  python media_tool_cli.py compress -f music.mp3 -o music_small.mp3
  python media_tool_cli.py compress -f video.mp4 --quality low
  python media_tool_cli.py compress -f video.mp4 -o video_small.webm

Without --output, the filename receives _compressed. WAV and AIFF inputs
use FLAC as the default output so their PCM audio is compressed losslessly.
High quality favors fidelity, while low quality favors a smaller output.
""",
    )
    _add_input_arguments(compress)
    compress.add_argument(
        "-q",
        "--quality",
        choices=QUALITY_LEVELS,
        default=DEFAULT_QUALITY,
        metavar="LEVEL",
        help=(
            "Compression quality: high, medium, or low (default: medium). "
            "High favors fidelity; low favors smaller files."
        ),
    )
    compress.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        help="Optional output path or alternate format; single-file inputs only.",
    )
    _add_batch_arguments(compress)

    cut = subparsers.add_parser(
        "cut",
        help="Remove a section from one or more audio or video files.",
        description=(
            "Remove everything before or after a timestamp, or remove the "
            "section between two timestamps and join the remaining pieces. "
            "A selected range can also be kept while removing everything else."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python media_tool_cli.py cut video.mp4 --before 10
  python media_tool_cli.py cut media/ --after 30 --output-dir cut/
  python media_tool_cli.py cut -f video.mp4 --after 30 -o first_30_seconds.mp4
  python media_tool_cli.py cut -f video.mp4 --between 10 20 -o without_middle.mp4
  python media_tool_cli.py cut -f video.mp4 --keep 10 15 -o excerpt.mp4

Timestamps are seconds and may contain decimals. Without --output, the output
filename receives _cut. Cuts are re-encoded for frame-accurate results.
""",
    )
    _add_input_arguments(cut)
    cut.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        help="Optional output path or alternate format; single-file inputs only.",
    )
    _add_batch_arguments(cut)
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
    cut_mode.add_argument(
        "--keep",
        type=non_negative_seconds,
        nargs=2,
        metavar=("START", "END"),
        help="Keep only this time range and remove everything else.",
    )

    return parser


def _add_input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "inputs",
        nargs="*",
        metavar="INPUT",
        help="Input files, glob patterns, or directories.",
    )
    parser.add_argument(
        "-f",
        "--file",
        dest="file_inputs",
        action="append",
        default=[],
        metavar="INPUT",
        help="Input path (legacy alias; may be repeated).",
    )


def _add_batch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search input directories recursively.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Abort if a discovered file is unsupported or incompatible.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIRECTORY",
        help="Write outputs beneath this directory, preserving subdirectories.",
    )


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
    elif (
        input_kind == "audio" and output_kind == "audio"
    ) or (
        input_kind == "video" and output_kind in {"audio", "video"}
    ):
        convert_audio_video(input_path, input_kind, output_path)
    else:
        raise ToolError(
            f"Conversion from {input_kind} to {output_kind or 'unknown media'} is not supported."
        )


def _requested_inputs(args: argparse.Namespace) -> list[str]:
    return [*args.inputs, *args.file_inputs]


def _validate_batch_output_options(
    batch_mode: bool,
    output_path: str | None,
    output_directory: str | None,
) -> None:
    if output_path and output_directory:
        raise ToolError("Use either --output or --output-dir, not both.")
    if output_path and batch_mode:
        raise ToolError(
            "--output names one file and cannot be used with a glob, directory, "
            "or multiple inputs. Use --output-dir instead."
        )
    if output_directory and os.path.exists(output_directory) and not os.path.isdir(
        output_directory
    ):
        raise ToolError(f"The output directory '{output_directory}' is not a directory.")


def _planned_output(
    input_file,
    explicit_output: str | None,
    output_directory: str | None,
    default_output,
) -> str:
    if explicit_output:
        return explicit_output
    if output_directory:
        return output_in_directory(input_file, output_directory, default_output)
    return default_output(input_file.path)


def _handle_ineligible(
    input_file,
    reason: str,
    errors: list[str],
    skipped: list[SkippedFile],
) -> None:
    if input_file.explicit:
        errors.append(f"{input_file.path} — {reason}")
    else:
        skipped.append(SkippedFile(input_file.path, reason))


def _source_kind(input_file) -> tuple[str, str | None]:
    source_ext = extension_from_path(input_file.path)
    return source_ext, media_kind_from_extension(source_ext)


def _plan_convert(args: argparse.Namespace):
    desired_ext = args.extension.lower().lstrip(".")
    if desired_ext not in SUPPORTED_OUTPUT_EXTENSIONS:
        raise ToolError(f"The output extension '.{desired_ext}' is not supported.")
    output_kind = media_kind_from_extension(desired_ext)
    selection = discover_inputs(_requested_inputs(args), args.recursive)
    _validate_batch_output_options(selection.batch_mode, args.output, args.output_dir)

    planned: list[PlannedFile] = []
    skipped: list[SkippedFile] = []
    errors: list[str] = []
    for input_file in selection.files:
        source_ext, source_kind = _source_kind(input_file)
        if source_kind is None:
            _handle_ineligible(
                input_file,
                f"the source extension '.{source_ext}' is not supported",
                errors,
                skipped,
            )
            continue
        if not input_file.explicit and os.path.splitext(input_file.path)[0].lower().endswith(
            "_converted"
        ):
            skipped.append(SkippedFile(input_file.path, "already appears converted"))
            continue
        compatible = (
            source_kind == "image" and output_kind == "image"
        ) or (
            source_kind == "audio" and output_kind == "audio"
        ) or (
            source_kind == "video" and output_kind in {"audio", "video"}
        )
        if not compatible:
            _handle_ineligible(
                input_file,
                f"cannot convert {source_kind} to {output_kind}",
                errors,
                skipped,
            )
            continue
        output_path = _planned_output(
            input_file,
            args.output,
            args.output_dir,
            lambda path: default_converted_output_path(path, desired_ext),
        )
        output_path = normalize_output_extension(output_path, desired_ext)
        planned.append(PlannedFile(input_file, output_path))

    raise_preflight_errors(errors)
    validate_output_collisions(planned)
    return selection, planned, skipped, desired_ext


def _plan_compress(args: argparse.Namespace):
    selection = discover_inputs(_requested_inputs(args), args.recursive)
    _validate_batch_output_options(selection.batch_mode, args.output, args.output_dir)

    planned: list[PlannedFile] = []
    skipped: list[SkippedFile] = []
    errors: list[str] = []
    for input_file in selection.files:
        source_ext, source_kind = _source_kind(input_file)
        if source_kind is None:
            _handle_ineligible(
                input_file,
                f"the source extension '.{source_ext}' is not supported",
                errors,
                skipped,
            )
            continue
        if not input_file.explicit and os.path.splitext(input_file.path)[0].lower().endswith(
            "_compressed"
        ):
            skipped.append(SkippedFile(input_file.path, "already appears compressed"))
            continue
        output_path = _planned_output(
            input_file,
            args.output,
            args.output_dir,
            default_compressed_output_path,
        )
        if args.output and not extension_from_path(output_path):
            output_path = f"{output_path}.{source_ext}"
        output_ext = extension_from_path(output_path)
        output_kind = media_kind_from_extension(output_ext)
        if output_ext not in SUPPORTED_OUTPUT_EXTENSIONS:
            _handle_ineligible(
                input_file,
                f"the output extension '.{output_ext}' is not supported",
                errors,
                skipped,
            )
            continue
        if output_kind != source_kind:
            _handle_ineligible(
                input_file,
                f"compression cannot change {source_kind} to {output_kind}",
                errors,
                skipped,
            )
            continue
        planned.append(PlannedFile(input_file, output_path))

    raise_preflight_errors(errors)
    validate_output_collisions(planned)
    return selection, planned, skipped


def _plan_cut(args: argparse.Namespace):
    selection = discover_inputs(_requested_inputs(args), args.recursive)
    _validate_batch_output_options(selection.batch_mode, args.output, args.output_dir)

    planned: list[PlannedFile] = []
    skipped: list[SkippedFile] = []
    errors: list[str] = []
    for input_file in selection.files:
        source_ext, source_kind = _source_kind(input_file)
        if source_kind not in {"audio", "video"}:
            reason = (
                f"the source extension '.{source_ext}' is not supported"
                if source_kind is None
                else "cut only accepts audio and video"
            )
            _handle_ineligible(input_file, reason, errors, skipped)
            continue
        if not input_file.explicit and os.path.splitext(input_file.path)[0].lower().endswith(
            "_cut"
        ):
            skipped.append(SkippedFile(input_file.path, "already appears cut"))
            continue
        output_path = _planned_output(
            input_file,
            args.output,
            args.output_dir,
            default_cut_output_path,
        )
        if args.output and not extension_from_path(output_path):
            output_path = f"{output_path}.{source_ext}"
        output_ext = extension_from_path(output_path)
        output_kind = media_kind_from_extension(output_ext)
        if output_kind != source_kind:
            _handle_ineligible(
                input_file,
                f"cut output must remain {source_kind}, not {output_kind or 'unknown media'}",
                errors,
                skipped,
            )
            continue
        planned.append(PlannedFile(input_file, output_path))

    raise_preflight_errors(errors)
    validate_output_collisions(planned)
    return selection, planned, skipped


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.action == "convert":
            selection, planned, skipped, desired_ext = _plan_convert(args)
            return run_planned_batch(
                planned,
                skipped,
                lambda source, output: process_convert(source, output, desired_ext),
                selection.batch_mode,
                args.strict,
            )
        elif args.action == "compress":
            selection, planned, skipped = _plan_compress(args)
            return run_planned_batch(
                planned,
                skipped,
                lambda source, output: process_compress(
                    source, output, args.quality
                ),
                selection.batch_mode,
                args.strict,
            )
        else:
            selection, planned, skipped = _plan_cut(args)
            return run_planned_batch(
                planned,
                skipped,
                lambda source, output: process_cut(
                    source, output, args.before, args.after, args.between, args.keep
                ),
                selection.batch_mode,
                args.strict,
            )
    except ToolError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
