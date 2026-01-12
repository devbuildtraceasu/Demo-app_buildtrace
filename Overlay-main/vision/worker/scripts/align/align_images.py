"""
Standalone Image Alignment Script

This script aligns two input images (old and new) using SIFT feature matching
and outputs both images on an expanded canvas that fully contains both.

When the transformed old image extends beyond the new image boundaries,
the canvas is automatically expanded to contain both images fully, ensuring
no content is clipped.

Usage:
    python align_images.py --old path/to/old.png --new path/to/new.png --output-dir path/to/output

Outputs:
    - aligned_old.png: The old image aligned to match the new image (on expanded canvas)
    - aligned_new.png: The new image placed on the same expanded canvas
"""

import argparse
import gc
import os
import sys

import cv2
import numpy as np

# Add worker root to path for lib imports
worker_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(worker_root)

from lib.sift_alignment import (
    _convert_to_grayscale,
    _encode_image_to_png,
    _load_image_from_bytes,
    apply_transformation,
    estimate_transformation,
    extract_sift_features,
    match_features,
)


def load_image_from_file(path: str) -> np.ndarray:
    """Load image from file path to numpy array (RGB format)."""
    with open(path, "rb") as f:
        png_bytes = f.read()
    return _load_image_from_bytes(png_bytes)


def save_image_to_file(image: np.ndarray, path: str) -> None:
    """Save numpy array (RGB format) to PNG file."""
    png_bytes = _encode_image_to_png(image)
    with open(path, "wb") as f:
        f.write(png_bytes)
    print(f"Saved: {path}")


def align_images(
    old_img: np.ndarray,
    new_img: np.ndarray,
    sift_downsample_scale: float = 0.2,
    n_features: int = 10000,
    exclude_margin: float = 0.2,
    ratio_threshold: float = 0.75,
    reproj_threshold: float = 15.0,
    max_iters: int = 5000,
    confidence: float = 0.95,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Align old image to new image using SIFT feature matching.

    The output canvas is automatically expanded to fully contain both images.
    Both output images share the same coordinate system and dimensions.

    Args:
        old_img: Old image (H, W, 3) RGB
        new_img: New image (H, W, 3) RGB
        sift_downsample_scale: Scale for SIFT processing (default: 0.2 = 20%)
        n_features: Max SIFT features to detect
        exclude_margin: Margin exclusion ratio for SIFT
        ratio_threshold: Lowe's ratio test threshold
        reproj_threshold: RANSAC reprojection threshold
        max_iters: RANSAC max iterations
        confidence: RANSAC confidence

    Returns:
        Tuple of (aligned_old, aligned_new, stats_dict) on expanded canvas
    """
    print(f"Old image shape: {old_img.shape}")
    print(f"New image shape: {new_img.shape}")

    # Downsample for SIFT (reduce memory footprint)
    print(f"\nDownsampling for SIFT ({sift_downsample_scale * 100:.0f}% scale)...")
    old_small = cv2.resize(
        old_img,
        None,
        fx=sift_downsample_scale,
        fy=sift_downsample_scale,
        interpolation=cv2.INTER_AREA,
    )
    new_small = cv2.resize(
        new_img,
        None,
        fx=sift_downsample_scale,
        fy=sift_downsample_scale,
        interpolation=cv2.INTER_AREA,
    )
    print(f"Downsampled shapes: old={old_small.shape}, new={new_small.shape}")

    # Convert to grayscale for feature detection
    old_gray = _convert_to_grayscale(old_small)
    new_gray = _convert_to_grayscale(new_small)

    # Free downsampled RGB
    del old_small, new_small
    gc.collect()

    # Extract SIFT features
    print("\nExtracting SIFT features...")
    kp1, desc1 = extract_sift_features(
        old_gray, n_features=n_features, exclude_margin=exclude_margin
    )
    kp2, desc2 = extract_sift_features(
        new_gray, n_features=n_features, exclude_margin=exclude_margin
    )
    print(f"Features: old={len(kp1)}, new={len(kp2)}")

    # Match features
    print("\nMatching features...")
    matches = match_features(desc1, desc2, ratio_threshold=ratio_threshold)
    print(f"Good matches: {len(matches)}")

    # Estimate transformation
    print("\nEstimating transformation...")
    matrix, mask, inlier_count, total_matches = estimate_transformation(
        kp1,
        kp2,
        matches,
        reproj_threshold=reproj_threshold,
        max_iters=max_iters,
        rotation_deg_min=-3,
        rotation_deg_max=3,
        confidence=confidence,
    )

    if matrix is None:
        raise RuntimeError(
            "Failed to estimate transformation: insufficient inliers or constraint violation"
        )

    # Extract scale and rotation from matrix
    scale = np.sqrt(matrix[0, 0] ** 2 + matrix[1, 0] ** 2)
    rotation_rad = np.arctan2(matrix[1, 0], matrix[0, 0])
    rotation_deg = np.degrees(rotation_rad)

    print(f"Transformation: scale={scale:.4f}, rotation={rotation_deg:.2f}°")
    print(f"Inliers: {inlier_count}/{total_matches} ({inlier_count / total_matches * 100:.1f}%)")

    # Scale transformation matrix back to full resolution
    scale_factor = 1.0 / sift_downsample_scale
    matrix[0, 2] *= scale_factor  # Scale tx
    matrix[1, 2] *= scale_factor  # Scale ty

    # Free intermediate data
    del old_gray, new_gray, kp1, kp2, desc1, desc2, matches, mask
    gc.collect()

    # Calculate bounding box that contains both transformed old and new images
    print("\nCalculating expanded canvas size...")
    old_h, old_w = old_img.shape[:2]
    new_h, new_w = new_img.shape[:2]

    # Get corners of old image
    old_corners = np.array(
        [[0, 0, 1], [old_w, 0, 1], [old_w, old_h, 1], [0, old_h, 1]], dtype=np.float64
    ).T

    # Transform old corners using the affine matrix
    # matrix is 2x3, so we compute: [x', y'] = matrix @ [x, y, 1]
    transformed_corners = matrix @ old_corners  # Shape: (2, 4)

    # Find bounding box of transformed old image
    old_x_min = np.min(transformed_corners[0])
    old_x_max = np.max(transformed_corners[0])
    old_y_min = np.min(transformed_corners[1])
    old_y_max = np.max(transformed_corners[1])

    # New image corners are at (0,0) to (new_w, new_h)
    # Combined bounding box
    combined_x_min = min(0, old_x_min)
    combined_y_min = min(0, old_y_min)
    combined_x_max = max(new_w, old_x_max)
    combined_y_max = max(new_h, old_y_max)

    # Calculate offset to shift origin to (0, 0)
    offset_x = -combined_x_min if combined_x_min < 0 else 0
    offset_y = -combined_y_min if combined_y_min < 0 else 0

    # Expanded canvas size
    expanded_w = int(np.ceil(combined_x_max - combined_x_min))
    expanded_h = int(np.ceil(combined_y_max - combined_y_min))

    print(f"Original new image: {new_w}x{new_h}")
    print(
        f"Transformed old bounds: x=[{old_x_min:.1f}, {old_x_max:.1f}], y=[{old_y_min:.1f}, {old_y_max:.1f}]"
    )
    print(f"Expanded canvas: {expanded_w}x{expanded_h}, offset=({offset_x:.1f}, {offset_y:.1f})")

    # Adjust transformation matrix to account for offset
    adjusted_matrix = matrix.copy()
    adjusted_matrix[0, 2] += offset_x
    adjusted_matrix[1, 2] += offset_y

    # Apply transformation at full resolution with expanded canvas
    print("\nApplying transformation at full resolution...")
    aligned_old_out = apply_transformation(
        old_img, adjusted_matrix, output_shape=(expanded_w, expanded_h)
    )

    # Place new image on expanded canvas (white background)
    new_expanded = np.full((expanded_h, expanded_w, 3), 255, dtype=new_img.dtype)
    new_x_start = int(offset_x)
    new_y_start = int(offset_y)
    new_expanded[new_y_start : new_y_start + new_h, new_x_start : new_x_start + new_w] = new_img

    print(f"Output shapes: aligned_old={aligned_old_out.shape}, new_aligned={new_expanded.shape}")

    stats = {
        "inlier_count": inlier_count,
        "total_matches": total_matches,
        "inlier_ratio": inlier_count / total_matches if total_matches > 0 else 0,
        "scale": scale,
        "rotation_deg": rotation_deg,
        "expanded_width": expanded_w,
        "expanded_height": expanded_h,
        "offset_x": offset_x,
        "offset_y": offset_y,
    }

    return aligned_old_out, new_expanded, stats


def main():
    # Default output directory: 'output' folder at script level
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_output_dir = os.path.join(script_dir, "output")

    parser = argparse.ArgumentParser(description="Align two images using SIFT feature matching")
    parser.add_argument("--old", required=True, help="Path to old image")
    parser.add_argument("--new", required=True, help="Path to new image")
    parser.add_argument(
        "--output-dir", default=default_output_dir, help="Output directory (default: ./output)"
    )
    parser.add_argument("--output-prefix", default="", help="Prefix for output filenames")
    parser.add_argument(
        "--sift-scale", type=float, default=0.2, help="SIFT downsample scale (default: 0.2)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.old):
        print(f"Error: Old image not found: {args.old}")
        sys.exit(1)
    if not os.path.exists(args.new):
        print(f"Error: New image not found: {args.new}")
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Load images
    print("Loading images...")
    old_img = load_image_from_file(args.old)
    new_img = load_image_from_file(args.new)

    # Align
    aligned_old, aligned_new, stats = align_images(
        old_img,
        new_img,
        sift_downsample_scale=args.sift_scale,
    )

    # Save outputs
    prefix = f"{args.output_prefix}_" if args.output_prefix else ""
    aligned_old_path = os.path.join(args.output_dir, f"{prefix}aligned_old.png")
    aligned_new_path = os.path.join(args.output_dir, f"{prefix}aligned_new.png")

    save_image_to_file(aligned_old, aligned_old_path)
    save_image_to_file(aligned_new, aligned_new_path)

    print("\nAlignment complete!")
    print(f"  Inlier ratio: {stats['inlier_ratio']:.1%}")
    print(f"  Scale: {stats['scale']:.4f}")
    print(f"  Rotation: {stats['rotation_deg']:.2f}°")
    print(f"  Expanded canvas: {stats['expanded_width']}x{stats['expanded_height']}")
    print(f"  Offset: ({stats['offset_x']:.1f}, {stats['offset_y']:.1f})")


if __name__ == "__main__":
    main()
