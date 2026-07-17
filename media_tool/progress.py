import math
import sys


def parse_ffmpeg_time(value: str) -> float | None:
    parts = value.split(":")
    if len(parts) != 3:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    except ValueError:
        return None
    return (hours * 3600.0) + (minutes * 60.0) + seconds


def progress_seconds(key: str, value: str) -> float | None:
    try:
        if key in {"out_time_ms", "out_time_us"}:
            return int(value) / 1_000_000.0
    except ValueError:
        return None
    if key == "out_time":
        return parse_ffmpeg_time(value)
    return None


def render_progress(done_seconds: float, total_seconds: float, speed: str | None) -> None:
    if not math.isfinite(total_seconds) or total_seconds <= 0:
        return

    width = 32
    ratio = min(max(done_seconds / total_seconds, 0.0), 1.0)
    filled = round(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    suffix = f" {speed}" if speed and speed != "N/A" else ""
    sys.stderr.write(f"\r[{bar}] {ratio * 100:5.1f}%{suffix}")
    sys.stderr.flush()


def finish_progress(total_seconds: float) -> None:
    render_progress(total_seconds, total_seconds, None)
    sys.stderr.write("\n")
    sys.stderr.flush()
