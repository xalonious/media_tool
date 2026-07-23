from PIL import Image

from .errors import ToolError
from .format_registry import pillow_format_for
from .formats import extension_from_path
from .quality import DEFAULT_QUALITY, quality_value


def convert_image(input_path: str, output_path: str, output_format: str) -> None:
    pillow_format = pillow_format_for(output_format)
    try:
        with Image.open(input_path) as image:
            print(
                f"Opened image: {input_path} "
                f"(Format: {image.format}, Mode: {image.mode})"
            )
            if pillow_format == "JPEG" and image.mode in {"RGBA", "P", "LA"}:
                image = image.convert("RGB")
            if pillow_format == "PDF":
                image.save(output_path, "PDF", resolution=100.0)
            else:
                image.save(output_path, pillow_format)
    except (OSError, ValueError) as exc:
        raise ToolError(f"Image conversion failed: {exc}") from exc

    print(f"Successfully converted '{input_path}' to '{output_path}'.")


def compress_image(
    input_path: str,
    output_path: str,
    quality: str = DEFAULT_QUALITY,
) -> None:
    output_ext = extension_from_path(output_path)
    pillow_format = pillow_format_for(output_ext)
    try:
        with Image.open(input_path) as image:
            print(
                f"Opened image: {input_path} "
                f"(Format: {image.format}, Mode: {image.mode})"
            )
            if pillow_format == "JPEG":
                if image.mode in {"RGBA", "P", "LA"}:
                    image = image.convert("RGB")
                image.save(
                    output_path,
                    "JPEG",
                    quality=quality_value(
                        quality, {"high": 92, "medium": 85, "low": 70}
                    ),
                    optimize=True,
                    progressive=True,
                )
            elif pillow_format == "PNG":
                image.save(output_path, "PNG", optimize=True, compress_level=9)
            elif pillow_format == "WEBP":
                image.save(
                    output_path,
                    "WEBP",
                    quality=quality_value(
                        quality, {"high": 90, "medium": 82, "low": 65}
                    ),
                    method=6,
                )
            else:
                try:
                    image.save(output_path, pillow_format, optimize=True)
                except TypeError:
                    image.save(output_path, pillow_format)
    except (OSError, ValueError) as exc:
        raise ToolError(f"Image compression failed: {exc}") from exc
