from __future__ import annotations

import argparse
from pathlib import Path

from vision_focus.pipeline import process_image


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a low-resolution overview plus a high-resolution focus crop "
            "from an input image."
        )
    )
    parser.add_argument("input", type=Path, help="Path to an input image.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Folder where generated images will be saved.",
    )
    parser.add_argument(
        "--low-res-width",
        type=int,
        default=320,
        help="Width of the cheap full-frame overview image.",
    )
    parser.add_argument(
        "--focus-fraction",
        type=float,
        default=0.10,
        help="Fraction of the original image area to keep as a high-res crop.",
    )

    args = parser.parse_args()
    result = process_image(
        input_path=args.input,
        output_dir=args.output_dir,
        low_res_width=args.low_res_width,
        focus_fraction=args.focus_fraction,
    )

    print("Focus processing complete.")
    print(f"Original size: {result.original_size[0]}x{result.original_size[1]}")
    print(f"Low-res size: {result.low_res_size[0]}x{result.low_res_size[1]}")
    print(f"Focus box: {result.focus_box}")
    print(f"Estimated pixel reduction: {result.estimated_pixel_reduction:.2f}x")
    print(f"Low-res overview: {result.low_res_path}")
    print(f"High-res crop: {result.focus_crop_path}")
    print(f"Debug image: {result.debug_path}")
