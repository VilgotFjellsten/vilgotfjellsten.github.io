# Vision Focus Prototype

This is a beginner-friendly Python prototype for an AI vision cost-reduction idea.

The first version does one simple thing:

1. Reads an image.
2. Creates a cheap low-resolution version of the whole image.
3. Estimates which area is visually important.
4. Crops that area from the original high-resolution image.
5. Saves a debug image with a box around the selected focus area.

The bigger product idea is:

> Send an AI model a cheap full-scene overview plus a smaller high-detail region, instead of sending the whole frame in high resolution.

## Project files

```text
main.py                  Starts the command-line program
requirements.txt         Python packages this project needs
vision_focus/cli.py      Handles terminal commands and options
vision_focus/pipeline.py Core image-processing logic
docs/product-notes.md    Product and patent-thinking notes
```

## Setup

From this folder:

```bash
cd vision-focus-prototype
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Run the prototype

Use any image file:

```bash
python3 main.py path/to/image.jpg
```

Generated files are saved in `outputs/`:

```text
low_res_overview.jpg
high_res_focus_crop.jpg
debug_focus_box.jpg
```

You can change the low-resolution width:

```bash
python3 main.py path/to/image.jpg --low-res-width 256
```

You can change how much of the original image is kept as the high-resolution focus crop:

```bash
python3 main.py path/to/image.jpg --focus-fraction 0.10
```

`0.10` means 10% of the original image area.

## What this prototype is not yet

This is not yet a finished AI product. It does not call a large AI model yet.

Right now it proves the first technical loop:

```text
image -> low-res overview -> focus estimate -> high-res crop
```

Future versions can add:

- video input
- multiple focus crops
- motion-based focus
- object detection
- benchmarks against full-resolution AI input
- integration with a vision-language model
