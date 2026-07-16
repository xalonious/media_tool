# Media Tool

A cross-platform command-line tool for converting and compressing images,
audio, and video, as well as cutting sections from videos. Media Tool keeps a
single, predictable interface across each media type: Pillow handles images,
while a project-local FFmpeg runtime handles audio and video.

## Overview

Media Tool is designed for quick local conversions without requiring users to
configure FFmpeg themselves. Its bootstrap script downloads a pinned FFmpeg
build into the project, and the main CLI chooses format-appropriate encoders
and compression settings automatically.

## Features

- Image conversion and compression through Pillow
- Audio conversion between common lossy and lossless formats
- Video conversion with container-appropriate video and audio codecs
- Audio extraction from video files
- Frame-accurate video cuts before, after, or between timestamps
- Sensible compression presets for each output format
- Lossless WAV and AIFF compression to FLAC by default
- Original size, output size, and space-saved reporting
- Project-local FFmpeg and ffprobe installation
- System FFmpeg fallback when a local runtime is unavailable
- Windows and Linux executable packaging with PyInstaller

## Setup

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

On systems where Python 3 is exposed as `python3`, use that command instead.

On Windows, invoke the source file through Python rather than launching the
`.py` file directly:

```powershell
python .\media_tool.py --help
```

Running `.\media_tool.py` depends on the machine's Windows file association;
some configurations route it through `pythonw.exe` and hide console output.

Download the pinned FFmpeg build for your platform:

```bash
python bootstrap.py
```

The bootstrap downloads `ffmpeg` and `ffprobe` into `vendor/ffmpeg`, verifies
both executables, and leaves the system `PATH` unchanged. Downloaded binaries
are ignored by Git.

To replace or repair the local FFmpeg installation:

```bash
python bootstrap.py --force
```

## Commands

### Convert

```text
python media_tool.py convert -f INPUT -e OUTPUT_EXTENSION -o OUTPUT
```

Convert an image:

```bash
python media_tool.py convert -f photo.webp -e png -o photo.png
```

Convert audio:

```bash
python media_tool.py convert -f recording.wav -e mp3 -o recording.mp3
```

Convert video:

```bash
python media_tool.py convert -f recording.mov -e mp4 -o recording.mp4
```

Extract or convert a video's audio track:

```bash
python media_tool.py convert -f recording.mp4 -e flac -o soundtrack.flac
```

Image-to-audio, image-to-video, and audio-to-video conversion are not exposed
because they require additional inputs such as a duration, audio track, or
video source.

### Compress

```text
python media_tool.py compress -f INPUT [-o OUTPUT]
```

Compress an image, audio file, or video:

```bash
python media_tool.py compress -f photo.png
python media_tool.py compress -f recording.mp3
python media_tool.py compress -f recording.mp4
```

The default output filename ends in `_compressed`. An explicit path can also
change the output format:

```bash
python media_tool.py compress -f recording.mp4 -o smaller.webm
```

WAV and AIFF inputs default to FLAC, preserving their audio losslessly while
applying real compression. Explicit WAV or AIFF outputs remain uncompressed
PCM.

Compression cannot guarantee a smaller result when an input is already
aggressively compressed. Media Tool reports when the output grows rather than
silently discarding it.

### Cut video

Remove everything before a timestamp:

```bash
python media_tool.py cut -f recording.mp4 --before 10
```

Remove everything after a timestamp:

```bash
python media_tool.py cut -f recording.mp4 --after 30 -o first_30_seconds.mp4
```

Remove the section between two timestamps and join the remaining pieces:

```bash
python media_tool.py cut -f recording.mp4 --between 10 20 -o without_middle.mp4
```

Timestamps are measured in seconds and may contain decimals. If `--output` is
omitted, the output keeps the input format and receives `_cut` in its filename.
You may select another supported video format with the output extension. Cuts
are re-encoded so the requested timestamps are frame-accurate.

## Supported formats

| Type | Formats |
| --- | --- |
| Images | PNG, JPEG, BMP, GIF, ICO, TIFF, EPS, PSD input, PCX, WebP, PPM/PGM/PBM, XBM, TGA, MSP, PDF |
| Audio | MP3, WAV, FLAC, AAC, M4A, Ogg/Vorbis, Opus, WMA, AIFF, AC-3 |
| Video | MP4/M4V, MOV, MKV, WebM, AVI, WMV, MPEG, FLV, MPEG-TS/M2TS, Ogg Video |

Actual encoder availability depends on the selected FFmpeg build. The pinned
bootstrap builds include the encoders used by Media Tool's presets, including
H.264 through `libx264`.

## Build an executable

[PyInstaller](https://pyinstaller.org/) can package Media Tool so the target
machine does not need Python or a separate FFmpeg installation.

Build on each target operating system separately; PyInstaller does not produce
Windows executables from Linux or Linux executables from Windows.

Install PyInstaller after completing the normal setup and bootstrap steps:

```bash
python -m pip install pyinstaller
```

The commands below create a single-file executable containing Media Tool,
Python, and FFmpeg.

### Windows build

Run from PowerShell in the project directory:

```powershell
python -m PyInstaller --noconfirm --clean --onefile `
  --name media-tool `
  --add-binary "vendor/ffmpeg/ffmpeg.exe;vendor/ffmpeg" `
  --add-binary "vendor/ffmpeg/ffprobe.exe;vendor/ffmpeg" `
  --add-data "THIRD_PARTY_NOTICES.md;." `
  media_tool.py
```

Output: `dist\media-tool.exe`

### Linux build

Run from the project directory:

```bash
python3 -m PyInstaller --noconfirm --clean --onefile \
  --name media-tool \
  --add-binary "vendor/ffmpeg/ffmpeg:vendor/ffmpeg" \
  --add-binary "vendor/ffmpeg/ffprobe:vendor/ffmpeg" \
  --add-data "THIRD_PARTY_NOTICES.md:." \
  media_tool.py
```

Output: `dist/media-tool`

## Run it from anywhere

### Windows

Copy the executable to a stable per-user location:

```powershell
$installDir = "$env:LOCALAPPDATA\Programs\media-tool"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Copy-Item ".\dist\media-tool.exe" "$installDir\media-tool.exe" -Force
```

Add that directory to the user `PATH` without changing the system-wide path:

```powershell
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$entries = @($userPath -split ";" | Where-Object { $_ })
if ($entries -notcontains $installDir) {
    [Environment]::SetEnvironmentVariable(
        "Path",
        (($entries + $installDir) -join ";"),
        "User"
    )
}
```

Open a new terminal and verify the installation:

```powershell
media-tool --help
```

The same directory can be added manually through **Environment Variables →
User variables → Path**.

### Linux

Install the executable directly into `/usr/local/bin`:

```bash
sudo install -m 0755 dist/media-tool /usr/local/bin/media-tool
```

Verify the installation:

```bash
media-tool --help
```

## FFmpeg and licensing

The `libx264` encoder makes the selected FFmpeg runtime a GPL build on platforms
where build variants are offered. Media Tool launches FFmpeg as a separate
process, but any FFmpeg binary distributed with an executable retains its own
license obligations. Review [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
and the license information for the exact FFmpeg build before publishing a
release.
