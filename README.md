# Image tool

A simple Python command-line tool for **converting** and **compressing** image files using Pillow.  
It supports many common image formats and provides sensible default compression settings that can significantly reduce file size with little or no visible quality loss.

---

## Requirements

Install Pillow before using the tool:

```sh
pip install pillow
```


## Usage

The tool supports two actions: `convert` and `compress`.

### Convert an image

Convert an image to a different format.

```sh
python image_tool.py convert -f input.webp -e png -o output.png
```

### Compress an image

Compress an image using default settings that reduce file size with minimal or no visible quality loss.

```sh
python image_tool.py compress -f input.png
```

If no output file is provided, the tool will automatically create one using `_compressed`.

You can also specify a custom output file:

```sh
python image_tool.py compress -f input.jpg -o input_small.jpg
```

enjoy