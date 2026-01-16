import argparse
import os
import sys
from PIL import Image

SUPPORTED_EXTENSIONS = [
    'png', 'jpg', 'jpeg', 'bmp', 'gif', 'ico', 'tiff', 'tif', 'eps', 'psd', 'pcx',
    'webp', 'ppm', 'pgm', 'pbm', 'xbm', 'tga', 'msp', 'pdf',
]

def human_bytes(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    size = float(n)
    for u in units:
        if size < 1024.0 or u == units[-1]:
            if u == "B":
                return f"{int(size)} {u}"
            return f"{size:.2f} {u}"
        size /= 1024.0
    return f"{n} B"

def default_compressed_output_path(input_path: str) -> str:
    base, ext = os.path.splitext(input_path)
    return f"{base}_compressed{ext}"

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert or compress image files.")
    sub = parser.add_subparsers(dest="action", required=True)
    p_convert = sub.add_parser("convert", help="Convert an image to a different format.")
    p_convert.add_argument("-f", "--file", required=True, help="Path to the input file.")
    p_convert.add_argument(
        "-e", "--extension",
        required=True,
        help=f"Desired output file extension ({', '.join(SUPPORTED_EXTENSIONS)}).",
    )
    p_convert.add_argument("-o", "--output", required=True, help="Output file path.")

    p_compress = sub.add_parser("compress", help="Compress an image with sensible defaults.")
    p_compress.add_argument("-f", "--file", required=True, help="Path to the input file.")
    p_compress.add_argument(
        "-o", "--output",
        required=False,
        help="Output file path. If omitted, defaults to <input>_compressed.<ext>."
    )

    return parser

def validate_common_input(path: str):
    if not os.path.isfile(path):
        print(f"Error: The file '{path}' does not exist.")
        sys.exit(1)

    source_ext = os.path.splitext(path)[1].lower().lstrip(".")
    if source_ext not in SUPPORTED_EXTENSIONS:
        print(f"Error: The source file '{path}' is not a supported image format.")
        print(f"Supported formats are: {', '.join(SUPPORTED_EXTENSIONS)}.")
        sys.exit(1)

def validate_output_dir(output_path: str):
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        print(f"Error: The directory '{output_dir}' does not exist.")
        sys.exit(1)

def normalize_output_extension(output_path: str, desired_ext: str) -> str:
    out_ext = os.path.splitext(output_path)[1].lower().lstrip(".")
    if out_ext != desired_ext:
        return os.path.splitext(output_path)[0] + "." + desired_ext
    return output_path

def convert_image(input_path: str, output_path: str, output_format: str):
    try:
        with Image.open(input_path) as img:
            print(f"Opened image: {input_path} (Format: {img.format}, Mode: {img.mode})")

            if output_format in ["jpg", "jpeg"] and img.mode in ("RGBA", "P"):
                print("Converting image mode to RGB for JPEG format.")
                img = img.convert("RGB")

            if output_format == "pdf":
                img.save(output_path, "PDF", resolution=100.0)
            elif output_format == "eps":
                img.save(output_path, "EPS")
            elif output_format == "psd":
                img.save(output_path, "PSD")
            else:
                img.save(output_path, output_format.upper())

        print(f"Successfully converted '{input_path}' to '{output_path}'.")
    except Exception as e:
        print(f"Error during conversion: {e}")
        sys.exit(1)

def compress_image(input_path: str, output_path: str | None):
    try:
        if not output_path:
            output_path = default_compressed_output_path(input_path)

        src_ext = os.path.splitext(input_path)[1].lower().lstrip(".")
        out_ext = os.path.splitext(output_path)[1].lower().lstrip(".")

        if not out_ext:
            output_path = output_path + "." + src_ext
            out_ext = src_ext

        if out_ext not in SUPPORTED_EXTENSIONS:
            print(f"Error: Unsupported output extension '{out_ext}'.")
            sys.exit(1)

        validate_output_dir(output_path)

        before_size = os.path.getsize(input_path)

        with Image.open(input_path) as img:
            print(f"Opened image: {input_path} (Format: {img.format}, Mode: {img.mode})")

            if out_ext in ("jpg", "jpeg"):
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(output_path, "JPEG", quality=85, optimize=True, progressive=True)

            elif out_ext == "png":
                img.save(output_path, "PNG", optimize=True, compress_level=9)

            elif out_ext == "webp":
                img.save(output_path, "WEBP", lossless=True, method=6)

            else:
                try:
                    img.save(output_path, out_ext.upper(), optimize=True)
                except TypeError:
                    img.save(output_path, out_ext.upper())

        after_size = os.path.getsize(output_path)
        saved = before_size - after_size
        pct = (saved / before_size) * 100.0 if before_size > 0 else 0.0

        if saved >= 0:
            print(f"Successfully compressed '{input_path}' to '{output_path}'.")
            print(f"Original: {human_bytes(before_size)}")
            print(f"New:      {human_bytes(after_size)}")
            print(f"Saved:    {human_bytes(saved)} ({pct:.2f}%)")
        else:
            grew = -saved
            print("Compression completed but file got larger:")
            print(f"Original: {human_bytes(before_size)}")
            print(f"New:      {human_bytes(after_size)}")
            print(f"Increase: {human_bytes(grew)} ({(-pct):.2f}%)")
            print(f"Output:   '{output_path}'")

    except Exception as e:
        print(f"Error during compression: {e}")
        sys.exit(1)

def main():
    parser = build_parser()
    args = parser.parse_args()

    validate_common_input(args.file)

    if args.action == "convert":
        desired_ext = args.extension.lower().lstrip(".")
        if desired_ext not in SUPPORTED_EXTENSIONS:
            print(f"Error: Unsupported extension '{args.extension}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}.")
            sys.exit(1)

        output_path = normalize_output_extension(args.output, desired_ext)
        validate_output_dir(output_path)
        convert_image(args.file, output_path, desired_ext)

    elif args.action == "compress":
        compress_image(args.file, args.output)

if __name__ == "__main__":
    main()
