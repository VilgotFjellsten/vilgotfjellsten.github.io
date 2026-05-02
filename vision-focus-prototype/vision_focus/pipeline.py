from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class FocusResult:
    """Paths and measurements produced by one focus-processing run."""

    low_res_path: Path
    focus_crop_path: Path
    debug_path: Path
    focus_box: tuple[int, int, int, int]
    original_size: tuple[int, int]
    low_res_size: tuple[int, int]
    estimated_pixel_reduction: float


def process_image(
    input_path: Path,
    output_dir: Path,
    low_res_width: int = 320,
    focus_fraction: float = 0.10,
) -> FocusResult:
    """Create a low-res overview, a high-res focus crop, and a debug image."""

    image = cv2.imread(str(input_path))
    if image is None:
        raise ValueError(f"Could not read image: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    height, width = image.shape[:2]
    low_res = _resize_to_width(image, low_res_width)
    saliency_map = _build_saliency_map(low_res)
    focus_box = _choose_focus_box(
        saliency_map=saliency_map,
        original_width=width,
        original_height=height,
        focus_fraction=focus_fraction,
    )

    crop = _crop_box(image, focus_box)
    debug_image = _draw_focus_box(image, focus_box)

    low_res_path = output_dir / "low_res_overview.jpg"
    focus_crop_path = output_dir / "high_res_focus_crop.jpg"
    debug_path = output_dir / "debug_focus_box.jpg"

    cv2.imwrite(str(low_res_path), low_res)
    cv2.imwrite(str(focus_crop_path), crop)
    cv2.imwrite(str(debug_path), debug_image)

    low_h, low_w = low_res.shape[:2]
    original_pixels = width * height
    transmitted_pixels = (low_w * low_h) + (crop.shape[1] * crop.shape[0])
    estimated_pixel_reduction = original_pixels / transmitted_pixels

    return FocusResult(
        low_res_path=low_res_path,
        focus_crop_path=focus_crop_path,
        debug_path=debug_path,
        focus_box=focus_box,
        original_size=(width, height),
        low_res_size=(low_w, low_h),
        estimated_pixel_reduction=estimated_pixel_reduction,
    )


def _resize_to_width(image: np.ndarray, target_width: int) -> np.ndarray:
    if target_width <= 0:
        raise ValueError("low_res_width must be greater than 0")

    height, width = image.shape[:2]
    scale = target_width / width
    target_height = max(1, int(height * scale))
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


def _build_saliency_map(image: np.ndarray) -> np.ndarray:
    """Estimate visually important areas using edges, contrast, and brightness."""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 0)

    edges = cv2.Canny(blurred, threshold1=40, threshold2=120)
    contrast = cv2.absdiff(gray, blurred)

    saliency = cv2.addWeighted(edges, 0.65, contrast, 0.35, 0)
    saliency = cv2.GaussianBlur(saliency, (15, 15), 0)
    return saliency


def _choose_focus_box(
    saliency_map: np.ndarray,
    original_width: int,
    original_height: int,
    focus_fraction: float,
) -> tuple[int, int, int, int]:
    if not 0 < focus_fraction <= 1:
        raise ValueError("focus_fraction must be between 0 and 1")

    low_height, low_width = saliency_map.shape[:2]
    box_area = original_width * original_height * focus_fraction
    aspect_ratio = original_width / original_height
    box_height = int((box_area / aspect_ratio) ** 0.5)
    box_width = int(box_height * aspect_ratio)

    box_width = min(max(1, box_width), original_width)
    box_height = min(max(1, box_height), original_height)

    low_box_width = max(1, int(box_width * low_width / original_width))
    low_box_height = max(1, int(box_height * low_height / original_height))

    heat = cv2.boxFilter(
        saliency_map.astype(np.float32),
        ddepth=-1,
        ksize=(low_box_width, low_box_height),
        normalize=False,
    )
    _, _, _, max_location = cv2.minMaxLoc(heat)
    heat_x, heat_y = max_location

    center_x_low = heat_x + low_box_width // 2
    center_y_low = heat_y + low_box_height // 2
    center_x = int(center_x_low * original_width / low_width)
    center_y = int(center_y_low * original_height / low_height)

    left = _clamp(center_x - box_width // 2, 0, original_width - box_width)
    top = _clamp(center_y - box_height // 2, 0, original_height - box_height)
    right = left + box_width
    bottom = top + box_height
    return left, top, right, bottom


def _crop_box(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    left, top, right, bottom = box
    return image[top:bottom, left:right]


def _draw_focus_box(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    left, top, right, bottom = box
    debug_image = image.copy()
    cv2.rectangle(debug_image, (left, top), (right, bottom), color=(0, 255, 255), thickness=3)
    return debug_image


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))
