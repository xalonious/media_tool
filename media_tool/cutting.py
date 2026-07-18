from .errors import ToolError
from .formats import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    default_cut_output_path,
    extension_from_path,
    validate_common_input,
    validate_distinct_paths,
    validate_output_dir,
)
from .audio import audio_codec_arguments
from .video import (
    ffmpeg_seconds,
    probe_media_duration,
    probe_video,
    run_ffmpeg,
    video_codec_arguments,
)


def build_cut_arguments(
    input_path: str,
    output_path: str,
    input_kind: str,
    mode: str,
    start: float,
    end: float | None,
    has_audio: bool,
) -> list[str]:
    output_ext = extension_from_path(output_path)
    codecs = (
        video_codec_arguments(output_ext, False)
        if input_kind == "video"
        else audio_codec_arguments(output_ext, False)
    )
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
    if input_kind == "audio":
        filter_graph = (
            f"[0:a:0]atrim=end={start_text},asetpts=PTS-STARTPTS[a0];"
            f"[0:a:0]atrim=start={end_text},asetpts=PTS-STARTPTS[a1];"
            "[a0][a1]concat=n=2:v=0:a=1[outa]"
        )
        maps = ["-map", "[outa]"]
    elif has_audio:
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
    if input_kind not in {"audio", "video"}:
        raise ToolError("The cut command only accepts audio and video files.")

    if not output_path:
        output_path = default_cut_output_path(input_path)
    elif not extension_from_path(output_path):
        output_path = f"{output_path}.{source_ext}"
    output_ext = extension_from_path(output_path)
    allowed_extensions = VIDEO_EXTENSIONS if input_kind == "video" else AUDIO_EXTENSIONS
    if output_ext not in allowed_extensions:
        raise ToolError(
            f"The output extension '.{output_ext}' is not an {input_kind} format."
        )
    validate_output_dir(output_path)
    validate_distinct_paths(input_path, output_path)

    if input_kind == "video":
        duration, has_audio = probe_video(input_path)
    else:
        duration, has_audio = probe_media_duration(input_path), True
    tolerance = 0.001
    if before is not None:
        mode, start, end = "before", before, None
        if start <= 0 or start >= duration - tolerance:
            raise ToolError(
                f"--before must be greater than 0 and less than the media "
                f"duration ({ffmpeg_seconds(duration)} seconds)."
            )
    elif after is not None:
        mode, start, end = "after", after, None
        if start <= 0 or start >= duration - tolerance:
            raise ToolError(
                f"--after must be greater than 0 and less than the media "
                f"duration ({ffmpeg_seconds(duration)} seconds)."
            )
    elif between is not None:
        start, end = between
        if start >= end:
            raise ToolError("The --between START timestamp must be before END.")
        if end > duration + tolerance:
            raise ToolError(
                f"The --between END timestamp exceeds the media duration "
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

    if mode == "before":
        progress_total = duration - start
    elif mode == "after":
        progress_total = start
    else:
        assert end is not None
        progress_total = duration - (end - start)

    run_ffmpeg(
        build_cut_arguments(
            input_path, output_path, input_kind, mode, start, end, has_audio
        ),
        progress_total,
    )
    print(f"Successfully cut '{input_path}' to '{output_path}'.")
