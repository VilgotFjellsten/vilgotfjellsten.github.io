# Vision Focus Prototype

This is a beginner-friendly Python prototype for an AI vision cost-reduction idea.

The current version does one simple thing:

1. Reads an image.
2. Creates a cheap low-resolution version of the whole image.
3. Estimates which area is visually important.
4. Crops that area from the original high-resolution image.
5. Builds a full-frame foveated image where detail decreases farther from the focus area.
6. Saves a debug image with a box around the selected focus area.

The bigger product idea is:

> Send an AI model an eye-like version of the whole scene: sharp near the focus area, lower resolution farther away, and still aware of the full frame.

## Project files

```text
main.py                  Starts the command-line program
requirements.txt         Python packages this project needs
vision_focus/cli.py      Handles terminal commands and options
vision_focus/pipeline.py Core image-processing logic
docs/human-vision-baseline.md Researched starting numbers for eye-like resolution
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
foveated_frame.jpg
debug_focus_box.jpg
```

The terminal also prints two rough measurements:

- `Estimated crop-package pixel reduction`: the old overview-plus-crop idea.
- `Estimated foveated detail reduction`: a rough effective-detail estimate for the new eye-like full-frame idea.

You can change the low-resolution width:

```bash
python3 main.py path/to/image.jpg --low-res-width 256
```

You can change how much of the original image is kept as the high-resolution focus crop:

```bash
python3 main.py path/to/image.jpg --focus-fraction 0.10
```

`0.10` means 10% of the original image area.

You can also change the assumed camera/view width in visual degrees:

```bash
python3 main.py path/to/image.jpg --field-of-view-degrees 90
```

The default is `90`, meaning the full image width is treated as about 90 degrees of visual field. A phone camera or wide webcam may be around this range, but different lenses need different values.

You can change the sharpest foveal resolution target:

```bash
python3 main.py path/to/image.jpg --foveal-ppd 94
```

`ppd` means pixels per degree. The prototype starts with `94` because recent display/vision research measured about 94 pixels per degree for sharp foveal black-white detail. A more conservative older 20/20 estimate is about 60 pixels per degree.

## What this prototype is not yet

This is not yet a finished AI product. It does not call a large AI model yet.

Right now it proves the first technical loop:

```text
image
  -> low-res overview
  -> focus estimate
  -> high-res crop
  -> full-frame foveated image
```

## Why foveated images matter

The crop output is useful for testing, but the foveated output is closer to how an eye works.

Instead of hiding the rest of the image, the prototype keeps the full scene visible and reduces detail with distance from the focus center:

```text
0-2 degrees from focus: highest detail
farther away: progressively lower detail
periphery: much lower detail
```

This may be a better input for a main AI model because it keeps context while reducing unnecessary visual detail.

Future versions can add:

- video input
- multiple focus crops
- motion-based focus
- object detection
- benchmarks against full-resolution AI input
- integration with a vision-language model
