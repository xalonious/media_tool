from .errors import ToolError
from .formats import (
    VIDEO_EXTENSIONS,
    default_cut_output_path,
    extension_from_path,
    validate_common_input,
    validate_distinct_paths,
    validate_output_dir,
)
from .video import ffmpeg_seconds, probe_video, run_ffmpeg, video_codec_arguments


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
