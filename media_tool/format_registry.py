from dataclasses import dataclass

from .errors import ToolError
from .quality import DEFAULT_QUALITY, validate_quality


@dataclass(frozen=True)
class QualitySetting:
    conversion: str
    high: str
    medium: str
    low: str

    def resolve(self, compress: bool, quality: str) -> str:
        if not compress:
            return self.conversion
        quality = validate_quality(quality)
        return {
            "high": self.high,
            "medium": self.medium,
            "low": self.low,
        }[quality]


@dataclass(frozen=True)
class EncoderPreset:
    arguments: tuple[str, ...]
    settings: tuple[tuple[str, QualitySetting], ...] = ()

    def build(self, compress: bool, quality: str) -> list[str]:
        values = {
            name: setting.resolve(compress, quality)
            for name, setting in self.settings
        }
        return [argument.format_map(values) for argument in self.arguments]


@dataclass(frozen=True)
class FormatSpec:
    media_kind: str
    canonical_extension: str
    output_supported: bool = True
    pillow_format: str | None = None
    encoder_preset: str | None = None
    muxer: str | None = None
    default_compression_extension: str | None = None


def _setting(
    conversion: str,
    high: str,
    medium: str,
    low: str,
) -> QualitySetting:
    return QualitySetting(conversion, high, medium, low)


ENCODER_PRESETS = {
    "mp3": EncoderPreset(
        ("-c:a", "libmp3lame", "-q:a", "{audio_quality}"),
        (("audio_quality", _setting("2", "2", "5", "7")),),
    ),
    "aac": EncoderPreset(
        ("-c:a", "aac", "-b:a", "{audio_bitrate}"),
        (("audio_bitrate", _setting("192k", "192k", "128k", "96k")),),
    ),
    "flac": EncoderPreset(
        ("-c:a", "flac", "-compression_level", "{compression_level}"),
        (("compression_level", _setting("5", "8", "8", "8")),),
    ),
    "vorbis": EncoderPreset(
        ("-c:a", "libvorbis", "-q:a", "{audio_quality}"),
        (("audio_quality", _setting("6", "6", "4", "2")),),
    ),
    "opus": EncoderPreset(
        ("-c:a", "libopus", "-b:a", "{audio_bitrate}"),
        (("audio_bitrate", _setting("128k", "128k", "96k", "64k")),),
    ),
    "wma": EncoderPreset(
        ("-c:a", "wmav2", "-b:a", "{audio_bitrate}"),
        (("audio_bitrate", _setting("192k", "192k", "128k", "96k")),),
    ),
    "ac3": EncoderPreset(
        ("-c:a", "ac3", "-b:a", "{audio_bitrate}"),
        (("audio_bitrate", _setting("256k", "256k", "192k", "128k")),),
    ),
    "eac3": EncoderPreset(
        ("-c:a", "eac3", "-b:a", "{audio_bitrate}"),
        (("audio_bitrate", _setting("384k", "384k", "256k", "192k")),),
    ),
    "pcm_wav": EncoderPreset(("-c:a", "pcm_s16le")),
    "pcm_aiff": EncoderPreset(("-c:a", "pcm_s16be")),
    "alac": EncoderPreset(("-c:a", "alac")),
    "tta": EncoderPreset(("-c:a", "tta")),
    "wavpack": EncoderPreset(("-c:a", "wavpack")),
    "h264_aac": EncoderPreset(
        (
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "{video_quality}",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "{audio_bitrate}",
        ),
        (
            ("video_quality", _setting("20", "23", "28", "33")),
            ("audio_bitrate", _setting("192k", "192k", "128k", "96k")),
        ),
    ),
    "h264_aac_faststart": EncoderPreset(
        (
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "{video_quality}",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "{audio_bitrate}",
            "-movflags", "+faststart",
        ),
        (
            ("video_quality", _setting("20", "23", "28", "33")),
            ("audio_bitrate", _setting("192k", "192k", "128k", "96k")),
        ),
    ),
    "vp9_opus": EncoderPreset(
        (
            "-c:v", "libvpx-vp9",
            "-crf", "{video_quality}",
            "-b:v", "0",
            "-c:a", "libopus",
            "-b:a", "{audio_bitrate}",
        ),
        (
            ("video_quality", _setting("28", "28", "34", "40")),
            ("audio_bitrate", _setting("128k", "128k", "96k", "64k")),
        ),
    ),
    "mpeg4_mp3": EncoderPreset(
        (
            "-c:v", "mpeg4",
            "-q:v", "{video_quality}",
            "-c:a", "libmp3lame",
            "-b:a", "{audio_bitrate}",
        ),
        (
            ("video_quality", _setting("3", "3", "6", "9")),
            ("audio_bitrate", _setting("192k", "192k", "128k", "96k")),
        ),
    ),
    "wmv": EncoderPreset(
        (
            "-c:v", "wmv2",
            "-b:v", "{video_bitrate}",
            "-c:a", "wmav2",
            "-b:a", "{audio_bitrate}",
        ),
        (
            ("video_bitrate", _setting("2M", "2M", "1M", "600k")),
            ("audio_bitrate", _setting("192k", "192k", "128k", "96k")),
        ),
    ),
    "mpeg2_mp2": EncoderPreset(
        (
            "-c:v", "mpeg2video",
            "-q:v", "{video_quality}",
            "-c:a", "mp2",
            "-b:a", "{audio_bitrate}",
        ),
        (
            ("video_quality", _setting("3", "3", "6", "9")),
            ("audio_bitrate", _setting("192k", "192k", "128k", "96k")),
        ),
    ),
    "mpeg2_ac3": EncoderPreset(
        (
            "-c:v", "mpeg2video",
            "-q:v", "{video_quality}",
            "-c:a", "ac3",
            "-b:a", "{audio_bitrate}",
        ),
        (
            ("video_quality", _setting("3", "3", "6", "9")),
            ("audio_bitrate", _setting("256k", "256k", "192k", "128k")),
        ),
    ),
    "flv": EncoderPreset(
        (
            "-c:v", "flv1",
            "-q:v", "{video_quality}",
            "-c:a", "aac",
            "-b:a", "{audio_bitrate}",
        ),
        (
            ("video_quality", _setting("4", "4", "7", "10")),
            ("audio_bitrate", _setting("192k", "192k", "128k", "96k")),
        ),
    ),
    "theora_vorbis": EncoderPreset(
        (
            "-c:v", "libtheora",
            "-q:v", "{video_quality}",
            "-c:a", "libvorbis",
            "-q:a", "{audio_quality}",
        ),
        (
            ("video_quality", _setting("7", "7", "5", "3")),
            ("audio_quality", _setting("6", "6", "4", "2")),
        ),
    ),
}


FORMAT_REGISTRY: dict[str, FormatSpec] = {}


def _register(
    extensions: tuple[str, ...],
    media_kind: str,
    *,
    output_supported: bool = True,
    pillow_format: str | None = None,
    encoder_preset: str | None = None,
    muxer: str | None = None,
    default_compression_extension: str | None = None,
) -> None:
    canonical_extension = extensions[0]
    for extension in extensions:
        if extension in FORMAT_REGISTRY:
            raise RuntimeError(f"Duplicate media extension in registry: {extension}")
        FORMAT_REGISTRY[extension] = FormatSpec(
            media_kind=media_kind,
            canonical_extension=canonical_extension,
            output_supported=output_supported,
            pillow_format=pillow_format,
            encoder_preset=encoder_preset,
            muxer=muxer,
            default_compression_extension=default_compression_extension,
        )


_register(("png",), "image", pillow_format="PNG")
_register(("jpg", "jpeg", "jpe", "jfif"), "image", pillow_format="JPEG")
_register(("bmp",), "image", pillow_format="BMP")
_register(("dib",), "image", pillow_format="DIB")
_register(("gif",), "image", pillow_format="GIF")
_register(("ico",), "image", pillow_format="ICO")
_register(("tif", "tiff"), "image", pillow_format="TIFF")
_register(("eps",), "image", pillow_format="EPS")
_register(("psd",), "image", output_supported=False, pillow_format="PSD")
_register(("pcx",), "image", pillow_format="PCX")
_register(("webp",), "image", pillow_format="WEBP")
_register(("ppm", "pgm", "pbm"), "image", pillow_format="PPM")
_register(("xbm",), "image", pillow_format="XBM")
_register(("tga",), "image", pillow_format="TGA")
_register(("msp",), "image", pillow_format="MSP")
_register(("pdf",), "image", pillow_format="PDF")

_register(("mp3",), "audio", encoder_preset="mp3")
_register(
    ("wav",),
    "audio",
    encoder_preset="pcm_wav",
    default_compression_extension="flac",
)
_register(("flac",), "audio", encoder_preset="flac")
_register(("aac", "m4a"), "audio", encoder_preset="aac")
_register(("ogg", "oga"), "audio", encoder_preset="vorbis")
_register(("opus",), "audio", encoder_preset="opus")
_register(("wma",), "audio", encoder_preset="wma")
_register(
    ("aif", "aiff"),
    "audio",
    encoder_preset="pcm_aiff",
    default_compression_extension="flac",
)
_register(("ac3",), "audio", encoder_preset="ac3")
_register(("eac3",), "audio", encoder_preset="eac3")
_register(("caf",), "audio", encoder_preset="alac", muxer="caf")
_register(("tta",), "audio", encoder_preset="tta", muxer="tta")
_register(("wv",), "audio", encoder_preset="wavpack", muxer="wv")

_register(
    ("mp4", "m4v", "mov"),
    "video",
    encoder_preset="h264_aac_faststart",
)
_register(("mkv",), "video", encoder_preset="h264_aac")
_register(("webm",), "video", encoder_preset="vp9_opus")
_register(("avi",), "video", encoder_preset="mpeg4_mp3")
_register(("wmv",), "video", encoder_preset="wmv")
_register(("mpg", "mpeg"), "video", encoder_preset="mpeg2_mp2")
_register(("flv",), "video", encoder_preset="flv")
_register(
    ("ts", "m2ts", "mts"),
    "video",
    encoder_preset="h264_aac",
    muxer="mpegts",
)
_register(("ogv",), "video", encoder_preset="theora_vorbis")
_register(("3gp",), "video", encoder_preset="h264_aac", muxer="3gp")
_register(("3g2",), "video", encoder_preset="h264_aac", muxer="3g2")
_register(("vob",), "video", encoder_preset="mpeg2_ac3", muxer="vob")


def format_spec(extension: str) -> FormatSpec | None:
    return FORMAT_REGISTRY.get(extension.lower().lstrip("."))


def extensions_for(
    media_kind: str,
    *,
    output_only: bool = False,
) -> set[str]:
    return {
        extension
        for extension, spec in FORMAT_REGISTRY.items()
        if spec.media_kind == media_kind
        and (not output_only or spec.output_supported)
    }


def pillow_format_for(extension: str) -> str:
    spec = format_spec(extension)
    if spec is None or spec.media_kind != "image" or spec.pillow_format is None:
        raise ToolError(f"No Pillow format is configured for '.{extension}'.")
    return spec.pillow_format


def encoder_arguments(
    extension: str,
    media_kind: str,
    compress: bool,
    quality: str = DEFAULT_QUALITY,
) -> list[str]:
    spec = format_spec(extension)
    if (
        spec is None
        or spec.media_kind != media_kind
        or not spec.output_supported
        or spec.encoder_preset is None
    ):
        raise ToolError(
            f"No {media_kind} encoder preset is configured for '.{extension}'."
        )
    try:
        preset = ENCODER_PRESETS[spec.encoder_preset]
    except KeyError as exc:
        raise RuntimeError(
            f"Unknown encoder preset in format registry: {spec.encoder_preset}"
        ) from exc
    arguments = preset.build(compress, quality)
    if spec.muxer:
        arguments.extend(["-f", spec.muxer])
    return arguments
