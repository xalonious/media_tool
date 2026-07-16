import os
import shutil
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
VENDOR_DIR = PROJECT_DIR / "vendor" / "ffmpeg"


class MediaRuntimeError(RuntimeError):
    """Raised when a required media executable cannot be found."""


def _executable_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def find_media_executable(name: str) -> Path | None:
    bundled = VENDOR_DIR / _executable_name(name)
    if bundled.is_file():
        return bundled

    system_path = shutil.which(name)
    return Path(system_path) if system_path else None


def require_media_executable(name: str) -> Path:
    executable = find_media_executable(name)
    if executable is None:
        raise MediaRuntimeError(
            f"{name} was not found. Run `python bootstrap.py` to install the "
            "project-local FFmpeg tools."
        )
    return executable


def require_ffmpeg() -> Path:
    return require_media_executable("ffmpeg")


def require_ffprobe() -> Path:
    return require_media_executable("ffprobe")
