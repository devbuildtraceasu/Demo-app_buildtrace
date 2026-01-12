"""
Extract foreground objects from an image and generate an alpha-masked PNG.

Supports common image formats including PNG, JPG, and WebP.

This script uses multiple techniques to isolate foreground content:
1. Threshold-based extraction for high-contrast images
2. GrabCut algorithm for more complex scenes
3. Edge-based refinement for cleaner boundaries

Usage:
    python extract_foreground.py --input image.webp --output foreground.png

    # Use GrabCut mode for complex images
    python extract_foreground.py --input photo.jpg --output result.png --mode grabcut

    # Specify background color (default: white)
    python extract_foreground.py --input image.png --output result.png --bg-color 255,255,255

    # Adjust threshold sensitivity (0-255, default: 240)
    python extract_foreground.py --input image.png --output result.png --threshold 230
"""

import argparse
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image

# Allow very large images
Image.MAX_IMAGE_PIXELS = 250_000_000

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "outputs"


def load_image_cv2(path: Path) -> np.ndarray:
    """Load image as BGR numpy array with broad format support (png, jpg, webp, etc)."""
    print(f"Loading {path}...")

    # Use PIL for broader format support (especially .webp)
    try:
        pil_img = Image.open(path).convert("RGB")
        # Convert RGB to BGR for OpenCV
        rgb = np.array(pil_img, dtype=np.uint8)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return bgr
    except Exception as e:
        raise FileNotFoundError(f"Could not load image: {path} - {e}")


def load_image_rgba(path: Path) -> np.ndarray:
    """Load image as RGBA numpy array."""
    print(f"Loading {path}...")
    img = Image.open(path).convert("RGBA")
    return np.array(img, dtype=np.uint8)


def save_rgba_image(img: np.ndarray, path: Path) -> None:
    """Save RGBA numpy array as PNG with transparency."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = Image.fromarray(img, mode="RGBA")
    out.save(path, "PNG")
    print(f"Saved: {path}")


def extract_foreground_threshold(
    img: np.ndarray,
    bg_color: tuple[int, int, int] = (255, 255, 255),
    threshold: int = 240,
    tolerance: int = 15,
) -> np.ndarray:
    """
    Extract foreground using threshold-based background detection.

    Works well for images with solid/uniform backgrounds (white, black, etc).

    Args:
        img: BGR image
        bg_color: Background color as (B, G, R)
        threshold: Brightness threshold for white background detection
        tolerance: Color tolerance for background matching

    Returns:
        RGBA image with transparent background
    """
    h, w = img.shape[:2]

    # Convert BGR to RGB for output
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Create alpha channel (fully opaque by default)
    alpha = np.ones((h, w), dtype=np.uint8) * 255

    # Method 1: Distance from background color
    bg_color_bgr = np.array(bg_color, dtype=np.float32)
    dist = np.sqrt(np.sum((img.astype(np.float32) - bg_color_bgr) ** 2, axis=2))
    bg_mask_color = dist < tolerance * np.sqrt(3)

    # Method 2: Near-white detection (for white backgrounds)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bg_mask_bright = gray > threshold

    # Combine masks - pixel is background if it matches either criterion
    bg_mask = bg_mask_color | bg_mask_bright

    # Refine mask using morphological operations
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    # Clean up small holes in foreground
    fg_mask = ~bg_mask
    fg_mask = fg_mask.astype(np.uint8) * 255
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Apply to alpha channel
    alpha = fg_mask

    # Create RGBA output
    rgba = np.dstack([rgb, alpha])

    fg_pixels = np.sum(alpha > 0)
    total_pixels = h * w
    print(f"Foreground pixels: {fg_pixels:,} ({100 * fg_pixels / total_pixels:.1f}%)")

    return rgba


def extract_foreground_grabcut(
    img: np.ndarray,
    margin: int = 10,
    iterations: int = 5,
) -> np.ndarray:
    """
    Extract foreground using GrabCut algorithm.

    Better for complex images with non-uniform backgrounds.

    Args:
        img: BGR image
        margin: Pixel margin to assume as background around edges
        iterations: Number of GrabCut iterations

    Returns:
        RGBA image with transparent background
    """
    h, w = img.shape[:2]

    # Initialize mask - assume everything is probably foreground except edges
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[:] = cv2.GC_PR_FGD  # Probable foreground

    # Mark edges as probable background
    mask[:margin, :] = cv2.GC_PR_BGD
    mask[-margin:, :] = cv2.GC_PR_BGD
    mask[:, :margin] = cv2.GC_PR_BGD
    mask[:, -margin:] = cv2.GC_PR_BGD

    # Define rectangle for initial GrabCut (excluding margins)
    rect = (margin, margin, w - 2 * margin, h - 2 * margin)

    # Temporary arrays for GrabCut
    bgd_model = np.zeros((1, 65), dtype=np.float64)
    fgd_model = np.zeros((1, 65), dtype=np.float64)

    print(f"Running GrabCut with {iterations} iterations...")
    cv2.grabCut(img, mask, rect, bgd_model, fgd_model, iterations, cv2.GC_INIT_WITH_RECT)

    # Create binary mask (foreground = 1, background = 0)
    fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(
        np.uint8
    )

    # Refine edges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Convert BGR to RGB
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Create RGBA output
    rgba = np.dstack([rgb, fg_mask])

    fg_pixels = np.sum(fg_mask > 0)
    total_pixels = h * w
    print(f"Foreground pixels: {fg_pixels:,} ({100 * fg_pixels / total_pixels:.1f}%)")

    return rgba


def extract_foreground_contour(
    img: np.ndarray,
    threshold: int = 240,
    min_area_ratio: float = 0.001,
) -> np.ndarray:
    """
    Extract foreground by finding and filling contours.

    Good for images with distinct objects on uniform backgrounds.

    Args:
        img: BGR image
        threshold: Brightness threshold for background
        min_area_ratio: Minimum contour area as ratio of image size

    Returns:
        RGBA image with transparent background
    """
    h, w = img.shape[:2]
    total_area = h * w
    min_area = int(total_area * min_area_ratio)

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Threshold to find non-background pixels
    _, thresh = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Create mask from significant contours
    fg_mask = np.zeros((h, w), dtype=np.uint8)

    valid_contours = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area >= min_area:
            valid_contours.append(cnt)

    print(f"Found {len(valid_contours)} foreground regions")

    # Fill contours on mask
    cv2.drawContours(fg_mask, valid_contours, -1, 255, -1)

    # Dilate slightly to capture edges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    fg_mask = cv2.dilate(fg_mask, kernel, iterations=1)

    # Convert BGR to RGB
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Create RGBA output
    rgba = np.dstack([rgb, fg_mask])

    fg_pixels = np.sum(fg_mask > 0)
    print(f"Foreground pixels: {fg_pixels:,} ({100 * fg_pixels / total_area:.1f}%)")

    return rgba


def extract_foreground_adaptive(
    img: np.ndarray,
    block_size: int = 51,
    c_value: int = 10,
) -> np.ndarray:
    """
    Extract foreground using adaptive thresholding.

    Better for images with varying lighting or gradient backgrounds.

    Args:
        img: BGR image
        block_size: Size of neighborhood for adaptive threshold (must be odd)
        c_value: Constant subtracted from mean

    Returns:
        RGBA image with transparent background
    """
    h, w = img.shape[:2]

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold
    fg_mask = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block_size, c_value
    )

    # Clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Convert BGR to RGB
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Create RGBA output
    rgba = np.dstack([rgb, fg_mask])

    fg_pixels = np.sum(fg_mask > 0)
    total_pixels = h * w
    print(f"Foreground pixels: {fg_pixels:,} ({100 * fg_pixels / total_pixels:.1f}%)")

    return rgba


def parse_color(color_str: str) -> tuple[int, int, int]:
    """Parse color string 'R,G,B' to tuple, returns as BGR for OpenCV."""
    parts = color_str.split(",")
    if len(parts) != 3:
        raise ValueError(f"Invalid color format: {color_str}. Use 'R,G,B' format.")
    r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
    return (b, g, r)  # BGR for OpenCV


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract foreground objects from an image with alpha masking.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  threshold  - Fast, works best with solid backgrounds (default)
  grabcut    - Slower, better for complex scenes
  contour    - Find and extract distinct objects
  adaptive   - Handle varying lighting conditions

Examples:
  %(prog)s --input photo.png --output result.png
  %(prog)s --input scan.jpg --output clean.png --mode grabcut
  %(prog)s --input diagram.png --output fg.png --threshold 230
        """,
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Input image path",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output PNG path (default: outputs/<input>_foreground.png)",
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        choices=["threshold", "grabcut", "contour", "adaptive"],
        default="threshold",
        help="Extraction mode (default: threshold)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=240,
        help="Brightness threshold for background (0-255, default: 240)",
    )
    parser.add_argument(
        "--bg-color",
        type=str,
        default="255,255,255",
        help="Background color as R,G,B (default: 255,255,255 for white)",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=15,
        help="Color tolerance for background matching (default: 15)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="GrabCut iterations (default: 5)",
    )
    parser.add_argument(
        "--margin",
        type=int,
        default=10,
        help="Edge margin for GrabCut (default: 10)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    # If path doesn't exist, try relative to script directory
    if not input_path.exists():
        input_path_rel = SCRIPT_DIR / args.input
        if input_path_rel.exists():
            input_path = input_path_rel
        else:
            raise FileNotFoundError(f"Input image not found: {args.input}")

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_DIR / f"{input_path.stem}_foreground.png"

    # Load image
    img = load_image_cv2(input_path)
    print(f"Image size: {img.shape[1]}x{img.shape[0]}")

    # Extract foreground based on mode
    if args.mode == "threshold":
        bg_color = parse_color(args.bg_color)
        rgba = extract_foreground_threshold(
            img,
            bg_color=bg_color,
            threshold=args.threshold,
            tolerance=args.tolerance,
        )
    elif args.mode == "grabcut":
        rgba = extract_foreground_grabcut(
            img,
            margin=args.margin,
            iterations=args.iterations,
        )
    elif args.mode == "contour":
        rgba = extract_foreground_contour(
            img,
            threshold=args.threshold,
        )
    elif args.mode == "adaptive":
        rgba = extract_foreground_adaptive(img)
    else:
        raise ValueError(f"Unknown mode: {args.mode}")

    # Save result
    save_rgba_image(rgba, output_path)
    print("Done!")


if __name__ == "__main__":
    main()
