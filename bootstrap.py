import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from media_runtime import VENDOR_DIR


DEFAULT_VERSION_SPECS = {
    ("Windows", "x86_64"): "=8.1.1@essentials",
    ("Linux", "x86_64"): "=8.1.1.post2@gpl",
    ("Linux", "aarch64"): "=8.1.1.post2@gpl",
    ("Darwin", "x86_64"): "=8.1@static",
    ("Darwin", "aarch64"): "=8.1@static",
}


def normalized_machine() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x64"}:
        return "x86_64"
    if machine in {"arm64", "armv8", "armv8l"}:
        return "aarch64"
    return machine


def default_version_spec() -> str:
    target = (platform.system(), normalized_machine())
    try:
        return DEFAULT_VERSION_SPECS[target]
    except KeyError as exc:
        supported = ", ".join(f"{system}/{arch}" for system, arch in DEFAULT_VERSION_SPECS)
        raise RuntimeError(
            f"No default FFmpeg build is configured for {target[0]}/{target[1]}. "
            f"Supported targets: {supported}. You can try an explicit build with "
            "`python bootstrap.py --version <version@build-type>`."
        ) from exc


def binary_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def read_manifest() -> dict:
    manifest_path = VENDOR_DIR / "install.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def verify_binary(path: Path) -> str:
    result = subprocess.run(
        [str(path), "-version"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.splitlines()[0] if result.stdout else path.name


def atomic_copy(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def already_installed(version_spec: str) -> bool:
    ffmpeg = VENDOR_DIR / binary_name("ffmpeg")
    ffprobe = VENDOR_DIR / binary_name("ffprobe")
    manifest = read_manifest()
    if manifest.get("requested_version") != version_spec:
        return False
    if not ffmpeg.is_file() or not ffprobe.is_file():
        return False

    try:
        print(f"Already installed: {verify_binary(ffmpeg)}")
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def run_downloader(version_spec: str) -> None:
    try:
        import ffmpeg_downloader  
    except ImportError as exc:
        raise RuntimeError(
            "The bootstrap dependency is missing. Run "
            "`python -m pip install -r requirements.txt` first."
        ) from exc

    command = [sys.executable, "-m", "ffmpeg_downloader", "install", "-y"]
    if os.name != "nt":
        command.append("--no-simlinks")
    command.append(version_spec)
    subprocess.run(command, check=True)


def copy_installed_binaries(version_spec: str) -> None:
    import ffmpeg_downloader as ffdl

    sources = {
        "ffmpeg": Path(ffdl.ffmpeg_path) if ffdl.ffmpeg_path else None,
        "ffprobe": Path(ffdl.ffprobe_path) if ffdl.ffprobe_path else None,
    }
    missing = [name for name, path in sources.items() if path is None or not path.is_file()]
    if missing:
        raise RuntimeError(
            "ffmpeg-downloader completed but did not provide: " + ", ".join(missing)
        )

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    installed_versions = {}
    for name, source in sources.items():
        assert source is not None
        destination = VENDOR_DIR / binary_name(name)
        atomic_copy(source, destination)
        installed_versions[name] = verify_binary(destination)
        print(f"Installed {name}: {destination}")

    manifest = {
        "requested_version": version_spec,
        "platform": platform.system(),
        "architecture": normalized_machine(),
        "binaries": installed_versions,
        "source": "ffmpeg-downloader 0.5.2",
    }
    (VENDOR_DIR / "install.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download project-local FFmpeg and ffprobe executables."
    )
    parser.add_argument(
        "--version",
        help="Override the platform's pinned ffmpeg-downloader version specification.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-copy and verify the requested FFmpeg binaries.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        version_spec = args.version or default_version_spec()
        if not args.force and already_installed(version_spec):
            return 0

        print(f"Preparing FFmpeg build {version_spec} for {platform.system()}/{normalized_machine()}...")
        run_downloader(version_spec)
        copy_installed_binaries(version_spec)
        print("FFmpeg setup complete.")
        return 0
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
