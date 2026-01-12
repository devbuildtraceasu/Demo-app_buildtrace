"""
Manual Image Alignment Script

Aligns an old image to a new image using manually specified coordinate pairs.
The transformation scales and translates the old image so that:
- old (x1, y1) aligns with new (x1, y1)
- old (x2, y2) aligns with new (x2, y2)

Usage:
    python manual_align.py --old path/to/old.png --new path/to/new.png \
        --old-x1 855 --old-x2 9119 --old-y1 540 --old-y2 6222 \
        --new-x1 4853 --new-x2 8978 --new-y1 1323 --new-y2 4164

Outputs:
    outputs/aligned_old.png - Old image transformed to align with new
    outputs/aligned_new.png - New image on the same expanded canvas
"""

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# Increase PIL's decompression bomb limit for large construction drawings
Image.MAX_IMAGE_PIXELS = 250_000_000

# Add worker root to path for lib imports
worker_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(worker_root)

from lib.sift_alignment import _load_image_from_bytes

# Script directories
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "outputs"
DATASET_DIR = SCRIPT_DIR / "dataset"

# Default input images
DEFAULT_OLD = DATASET_DIR / "M201_old.png"
DEFAULT_NEW = DATASET_DIR / "M201_new.png"


def load_image(path: Path) -> np.ndarray:
    """Load image as RGB numpy array."""
    print(f"Loading {path}...")
    with open(path, "rb") as f:
        png_bytes = f.read()
    return _load_image_from_bytes(png_bytes)


def save_image(img: np.ndarray, path: Path) -> None:
    """Save RGB numpy array as PNG."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pil_img = Image.fromarray(img, mode="RGB")
    pil_img.save(path)
    print(f"Saved: {path}")


def compute_transform(
    old_x1: int,
    old_y1: int,
    old_x2: int,
    old_y2: int,
    new_x1: int,
    new_y1: int,
    new_x2: int,
    new_y2: int,
) -> tuple[float, float, float, float]:
    """
    Compute scale and translation to map old coordinates to new coordinates.

    Returns:
        (scale_x, scale_y, translate_x, translate_y)
    """
    # Calculate widths and heights
    old_width = old_x2 - old_x1
    old_height = old_y2 - old_y1
    new_width = new_x2 - new_x1
    new_height = new_y2 - new_y1

    # Calculate scale factors
    scale_x = new_width / old_width
    scale_y = new_height / old_height

    # Calculate translation (after scaling)
    # new_x1 = old_x1 * scale_x + translate_x
    # translate_x = new_x1 - old_x1 * scale_x
    translate_x = new_x1 - (old_x1 * scale_x)
    translate_y = new_y1 - (old_y1 * scale_y)

    return scale_x, scale_y, translate_x, translate_y


def apply_transform(
    image: np.ndarray,
    scale_x: float,
    scale_y: float,
    translate_x: float,
    translate_y: float,
    output_size: tuple[int, int],
) -> np.ndarray:
    """
    Apply scale and translation transform to image.

    Args:
        image: Input RGB image (H, W, 3)
        scale_x, scale_y: Scale factors
        translate_x, translate_y: Translation after scaling
        output_size: (width, height) of output canvas

    Returns:
        Transformed image on output canvas
    """
    # Build 2x3 affine transformation matrix
    # [x']   [scale_x    0      translate_x] [x]
    # [y'] = [0       scale_y   translate_y] [y]
    matrix = np.array([[scale_x, 0, translate_x], [0, scale_y, translate_y]], dtype=np.float64)

    # Apply transformation
    output_w, output_h = output_size

    # Convert RGB to BGR for OpenCV
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    # Apply affine warp with white background
    transformed = cv2.warpAffine(
        bgr,
        matrix,
        (output_w, output_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )

    # Convert back to RGB
    return cv2.cvtColor(transformed, cv2.COLOR_BGR2RGB)


def manual_align(
    old_img: np.ndarray,
    new_img: np.ndarray,
    old_x1: int,
    old_y1: int,
    old_x2: int,
    old_y2: int,
    new_x1: int,
    new_y1: int,
    new_x2: int,
    new_y2: int,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Align old image to new image using manual coordinate pairs.

    Returns:
        (aligned_old, aligned_new, stats)
    """
    print(f"\nOld image shape: {old_img.shape}")
    print(f"New image shape: {new_img.shape}")

    # Compute transformation
    scale_x, scale_y, tx, ty = compute_transform(
        old_x1,
        old_y1,
        old_x2,
        old_y2,
        new_x1,
        new_y1,
        new_x2,
        new_y2,
    )

    print("\nTransformation:")
    print(f"  Scale X: {scale_x:.4f}")
    print(f"  Scale Y: {scale_y:.4f}")
    print(f"  Translate X: {tx:.1f}")
    print(f"  Translate Y: {ty:.1f}")

    # Calculate bounding box for transformed old image
    old_h, old_w = old_img.shape[:2]
    new_h, new_w = new_img.shape[:2]

    # Transform corners of old image
    old_corners = np.array([[0, 0], [old_w, 0], [old_w, old_h], [0, old_h]], dtype=np.float64)

    transformed_corners = old_corners * [scale_x, scale_y] + [tx, ty]

    # Find bounding box
    trans_x_min = np.min(transformed_corners[:, 0])
    trans_x_max = np.max(transformed_corners[:, 0])
    trans_y_min = np.min(transformed_corners[:, 1])
    trans_y_max = np.max(transformed_corners[:, 1])

    print("\nTransformed old bounds:")
    print(f"  X: [{trans_x_min:.1f}, {trans_x_max:.1f}]")
    print(f"  Y: [{trans_y_min:.1f}, {trans_y_max:.1f}]")

    # Calculate expanded canvas that contains both images
    combined_x_min = min(0, trans_x_min)
    combined_y_min = min(0, trans_y_min)
    combined_x_max = max(new_w, trans_x_max)
    combined_y_max = max(new_h, trans_y_max)

    # Offset to shift origin to (0, 0)
    offset_x = -combined_x_min if combined_x_min < 0 else 0
    offset_y = -combined_y_min if combined_y_min < 0 else 0

    # Expanded canvas size
    expanded_w = int(np.ceil(combined_x_max - combined_x_min))
    expanded_h = int(np.ceil(combined_y_max - combined_y_min))

    print(f"\nExpanded canvas: {expanded_w}x{expanded_h}")
    print(f"Offset: ({offset_x:.1f}, {offset_y:.1f})")

    # Adjust translation for offset
    adjusted_tx = tx + offset_x
    adjusted_ty = ty + offset_y

    # Apply transformation to old image
    print("\nApplying transformation...")
    aligned_old = apply_transform(
        old_img, scale_x, scale_y, adjusted_tx, adjusted_ty, (expanded_w, expanded_h)
    )

    # Place new image on expanded canvas
    aligned_new = np.full((expanded_h, expanded_w, 3), 255, dtype=np.uint8)
    new_x_start = int(offset_x)
    new_y_start = int(offset_y)
    aligned_new[new_y_start : new_y_start + new_h, new_x_start : new_x_start + new_w] = new_img

    print(f"Output shapes: aligned_old={aligned_old.shape}, aligned_new={aligned_new.shape}")

    stats = {
        "scale_x": scale_x,
        "scale_y": scale_y,
        "translate_x": tx,
        "translate_y": ty,
        "expanded_width": expanded_w,
        "expanded_height": expanded_h,
        "offset_x": offset_x,
        "offset_y": offset_y,
    }

    return aligned_old, aligned_new, stats


def main():
    parser = argparse.ArgumentParser(description="Manually align two images using coordinate pairs")
    parser.add_argument("--old", default=str(DEFAULT_OLD), help="Path to old image")
    parser.add_argument("--new", default=str(DEFAULT_NEW), help="Path to new image")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument("--prefix", default="", help="Prefix for output filenames")

    # Old image coordinates
    parser.add_argument("--old-x1", type=int, default=855, help="Old image X1 coordinate")
    parser.add_argument("--old-y1", type=int, default=540, help="Old image Y1 coordinate")
    parser.add_argument("--old-x2", type=int, default=9119, help="Old image X2 coordinate")
    parser.add_argument("--old-y2", type=int, default=6222, help="Old image Y2 coordinate")

    # New image coordinates
    parser.add_argument("--new-x1", type=int, default=4853, help="New image X1 coordinate")
    parser.add_argument("--new-y1", type=int, default=1322, help="New image Y1 coordinate")
    parser.add_argument("--new-x2", type=int, default=8978, help="New image X2 coordinate")
    parser.add_argument("--new-y2", type=int, default=4163, help="New image Y2 coordinate")

    args = parser.parse_args()

    old_path = Path(args.old)
    new_path = Path(args.new)
    output_dir = Path(args.output_dir)

    # Validate inputs
    if not old_path.exists():
        print(f"Error: Old image not found: {old_path}")
        sys.exit(1)
    if not new_path.exists():
        print(f"Error: New image not found: {new_path}")
        sys.exit(1)

    print("=" * 60)
    print("Manual Image Alignment")
    print("=" * 60)
    print(f"\nOld coordinates: ({args.old_x1}, {args.old_y1}) -> ({args.old_x2}, {args.old_y2})")
    print(f"New coordinates: ({args.new_x1}, {args.new_y1}) -> ({args.new_x2}, {args.new_y2})")

    # Load images
    old_img = load_image(old_path)
    new_img = load_image(new_path)

    # Align
    aligned_old, aligned_new, stats = manual_align(
        old_img,
        new_img,
        args.old_x1,
        args.old_y1,
        args.old_x2,
        args.old_y2,
        args.new_x1,
        args.new_y1,
        args.new_x2,
        args.new_y2,
    )

    # Save outputs
    prefix = f"{args.prefix}_" if args.prefix else ""
    aligned_old_path = output_dir / f"{prefix}aligned_old.png"
    aligned_new_path = output_dir / f"{prefix}aligned_new.png"

    save_image(aligned_old, aligned_old_path)
    save_image(aligned_new, aligned_new_path)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Scale: ({stats['scale_x']:.4f}, {stats['scale_y']:.4f})")
    print(f"Translation: ({stats['translate_x']:.1f}, {stats['translate_y']:.1f})")
    print(f"Canvas: {stats['expanded_width']}x{stats['expanded_height']}")
    print(f"\nOutput saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
