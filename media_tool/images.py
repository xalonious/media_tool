from PIL import Image

from .errors import ToolError
from .formats import extension_from_path


PILLOW_FORMATS = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "tif": "TIFF",
    "tiff": "TIFF",
    "pgm": "PPM",
    "pbm": "PPM",
    "ppm": "PPM",
}


def pillow_format(extension: str) -> str:
    return PILLOW_FORMATS.get(extension, extension.upper())


def convert_image(input_path: str, output_path: str, output_format: str) -> None:
    try:
        with Image.open(input_path) as image:
            print(
                f"Opened image: {input_path} "
                f"(Format: {image.format}, Mode: {image.mode})"
            )
            if output_format in {"jpg", "jpeg"} and image.mode in {"RGBA", "P", "LA"}:
                image = image.convert("RGB")
            if output_format == "pdf":
                image.save(output_path, "PDF", resolution=100.0)
            else:
                image.save(output_path, pillow_format(output_format))
    except (OSError, ValueError) as exc:
        raise ToolError(f"Image conversion failed: {exc}") from exc

    print(f"Successfully converted '{input_path}' to '{output_path}'.")


def compress_image(input_path: str, output_path: str) -> None:
    output_ext = extension_from_path(output_path)
    try:
        with Image.open(input_path) as image:
            print(
                f"Opened image: {input_path} "
                f"(Format: {image.format}, Mode: {image.mode})"
            )
            if output_ext in {"jpg", "jpeg"}:
                if image.mode in {"RGBA", "P", "LA"}:
                    image = image.convert("RGB")
                image.save(
                    output_path,
                    "JPEG",
                    quality=85,
                    optimize=True,
                    progressive=True,
                )
            elif output_ext == "png":
                image.save(output_path, "PNG", optimize=True, compress_level=9)
            elif output_ext == "webp":
                image.save(output_path, "WEBP", quality=82, method=6)
            else:
                try:
                    image.save(output_path, pillow_format(output_ext), optimize=True)
                except TypeError:
                    image.save(output_path, pillow_format(output_ext))
    except (OSError, ValueError) as exc:
        raise ToolError(f"Image compression failed: {exc}") from exc
