"""
Mask green pixels in the manual-align overlay image based on coordinate rules.

Rules (defaults baked in for this project):
- Any green pixel with x < 4846 becomes black
- Any green pixel with y > 4203 becomes black

The script is configured by default to operate on `dataset/overlay.png` and
write the result to `outputs/overlay_masked.png`.

Usage (from this directory):
    python mask_green_overlay.py

Optional arguments:
    python mask_green_overlay.py \
        --input dataset/overlay.png \
        --output outputs/overlay_masked.png \
        --x-threshold 4846 \
        --y-threshold 4203
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

# Allow very large construction drawings
Image.MAX_IMAGE_PIXELS = 250_000_000

SCRIPT_DIR = Path(__file__).parent
DATASET_DIR = SCRIPT_DIR / "dataset"
OUTPUT_DIR = SCRIPT_DIR / "outputs"

DEFAULT_INPUT = DATASET_DIR / "overlay.png"
DEFAULT_OUTPUT = OUTPUT_DIR / "overlay_masked.png"


def load_image(path: Path) -> np.ndarray:
    """Load image as RGB numpy array."""
    print(f"Loading {path}...")
    img = Image.open(path).convert("RGB")
    return np.array(img, dtype=np.uint8)


def save_image(img: np.ndarray, path: Path) -> None:
    """Save RGB numpy array as PNG."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = Image.fromarray(img, mode="RGB")
    out.save(path)
    print(f"Saved: {path}")


def build_green_mask(img: np.ndarray) -> np.ndarray:
    """
    Build a boolean mask for "green" pixels.

    We treat a pixel as green if:
        G is high and R/B are low.
    The thresholds are chosen to be a bit robust to antialiasing.
    """
    r = img[:, :, 0].astype(np.int16)
    g = img[:, :, 1].astype(np.int16)
    b = img[:, :, 2].astype(np.int16)

    # Tune these if needed to better match your overlay color
    green_mask = (g >= 200) & (r <= 60) & (b <= 60)
    return green_mask


def mask_green_regions(
    img: np.ndarray,
    x_threshold: int,
    y_threshold: int,
) -> np.ndarray:
    """
    Turn selected green pixels black based on coordinate rules.

    - Pixels with x < x_threshold AND green -> black
    - Pixels with y > y_threshold AND green -> black

    (Union of the two conditions.)
    """
    h, w = img.shape[:2]

    green_mask = build_green_mask(img)

    # Coordinate masks
    xs = np.arange(w, dtype=np.int32)[None, :]  # shape (1, W)
    ys = np.arange(h, dtype=np.int32)[:, None]  # shape (H, 1)

    x_mask = xs < x_threshold
    y_mask = ys > y_threshold

    coord_mask = x_mask | y_mask

    # Apply to green pixels only
    full_mask = green_mask & coord_mask

    # Copy to avoid modifying in-place if caller reuses original
    out = img.copy()
    out[full_mask] = np.array([0, 0, 0], dtype=np.uint8)

    affected = int(full_mask.sum())
    print(f"Green pixels turned black: {affected}")

    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Turn specific green pixels in dataset/overlay.png black based on "
            "x/y coordinate thresholds."
        )
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(DEFAULT_INPUT),
        help="Input PNG (default: dataset/overlay.png)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help="Output PNG (default: outputs/overlay_masked.png)",
    )
    parser.add_argument(
        "--x-threshold",
        type=int,
        default=4846,
        help="All green pixels with x < this value become black (default: 4846)",
    )
    parser.add_argument(
        "--y-threshold",
        type=int,
        default=4203,
        help="All green pixels with y > this value become black (default: 4203)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    img = load_image(input_path)
    masked = mask_green_regions(
        img,
        x_threshold=args.x_threshold,
        y_threshold=args.y_threshold,
    )
    save_image(masked, output_path)


if __name__ == "__main__":
    main()
