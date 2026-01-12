"""Overlay rendering functions for generating visual diff images.

This module provides functions for generating overlay images that visualize
differences between aligned image pairs. Supports two rendering modes:
- Merge mode: Red/green tinting with grayscale for unchanged areas
- Diff mode: Discrete difference detection with morphological cleanup

Key functions:
- generate_overlay_merge_mode(): Primary overlay with red/green tinting
- generate_overlay_diff_mode(): Alternative with discrete diff detection
"""

import gc

import cv2
import numpy as np


def _convert_to_grayscale(rgb_image: np.ndarray) -> np.ndarray:
    """Convert RGB image to grayscale.

    Args:
        rgb_image: RGB image (H, W, 3) with dtype uint8

    Returns:
        Grayscale image (H, W) with dtype uint8
    """
    if len(rgb_image.shape) != 3 or rgb_image.shape[2] != 3:
        raise ValueError(f"Expected RGB image with shape (H, W, 3), got {rgb_image.shape}")
    return cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)


def generate_overlay_merge_mode(
    aligned_a: np.ndarray,
    aligned_b: np.ndarray,
    *,
    tint_strength: float = 0.5,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None]:
    """Generate overlay image using merge-mode rendering.

    Merges both images with red/green tinting:
    - Red channel contains image B (new) - red where only new content
    - Green channel contains image A (old) - green where only old content
    - Overlapping unchanged areas appear in grayscale

    Args:
        aligned_a: Aligned image A in RGB format (old/source)
        aligned_b: Aligned image B in RGB format (new/target)
        tint_strength: Blend factor (0.0 = grayscale, 1.0 = pure color)

    Returns:
        (overlay, None, None)
        - overlay: RGB with red/green tinting
        - deletion: None (caller creates white image if needed)
        - addition: None (caller creates white image if needed)
    """
    if aligned_a.shape != aligned_b.shape:
        raise ValueError(f"Image dimensions must match: {aligned_a.shape} != {aligned_b.shape}")

    a_gray = _convert_to_grayscale(aligned_a)
    b_gray = _convert_to_grayscale(aligned_b)

    a_f = a_gray.astype(np.float32)
    b_f = b_gray.astype(np.float32)
    del a_gray, b_gray  # Release grayscale arrays

    # Base merge: R=new (B), G=old (A), B=min for neutral overlap
    b_base = np.minimum(a_f, b_f)

    # Apply tint_strength: blend between grayscale average and tinted
    gray_avg = (a_f + b_f) / 2
    r = b_f * tint_strength + gray_avg * (1 - tint_strength)
    g = a_f * tint_strength + gray_avg * (1 - tint_strength)
    b = b_base * tint_strength + gray_avg * (1 - tint_strength)
    del a_f, b_f, b_base, gray_avg  # Release intermediate arrays

    overlay = np.stack([r, g, b], axis=-1).astype(np.uint8)
    del r, g, b  # Release channel arrays
    gc.collect()

    # In merge mode, deletion/addition are empty (white) - return None
    # Caller can create white images lazily to reduce peak memory
    return overlay, None, None


def generate_overlay_diff_mode(
    aligned_a: np.ndarray,
    aligned_b: np.ndarray,
    *,
    ink_threshold: int = 200,
    diff_threshold: int = 40,
    morph_kernel_size: int = 1,
    skip_morph: bool = False,
    shift_tolerance: int = 3,
    tint_strength: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate overlay image using discrete diff detection.

    Compares two aligned images to detect additions and deletions:
    1. Content detection via ink_threshold (darker = content)
    2. Change detection: only differences > diff_threshold count as changes
    3. Removed = was ink in A, not in B, with significant difference
    4. Added = is ink in B, wasn't in A, with significant difference

    Args:
        aligned_a: Aligned image A in RGB format (old/source)
        aligned_b: Aligned image B in RGB format (new/target)
        ink_threshold: Pixels darker than this are "ink/content" (0-255)
        diff_threshold: Minimum pixel difference to count as change (0-255)
        morph_kernel_size: Kernel size for morphological cleanup
        skip_morph: If True, skip morphological cleaning
        shift_tolerance: Ignore changes within this distance of content in other image
        tint_strength: Blend factor for diff coloring

    Returns:
        (overlay, deletion, addition)
        - overlay: RGB with red (removed) and green (added)
        - deletion: Black pixels on white for removed content
        - addition: Black pixels on white for added content
    """
    if aligned_a.shape != aligned_b.shape:
        raise ValueError(f"Image dimensions must match: {aligned_a.shape} != {aligned_b.shape}")

    a_gray = _convert_to_grayscale(aligned_a)
    b_gray = _convert_to_grayscale(aligned_b)

    # Content detection: pixels darker than threshold are "ink"
    a_mask = a_gray < ink_threshold
    b_mask = b_gray < ink_threshold

    # Change detection: only count differences above threshold
    diff = cv2.absdiff(a_gray, b_gray)
    strong_diff_mask = diff > diff_threshold

    # Compute raw change masks
    removed = a_mask & ~b_mask & strong_diff_mask
    added = b_mask & ~a_mask & strong_diff_mask

    # Apply morphological cleanup
    if not skip_morph and morph_kernel_size > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size)
        )
        removed = cv2.morphologyEx(removed.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel) > 0
        added = cv2.morphologyEx(added.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel) > 0

    # Apply shift tolerance
    if shift_tolerance > 0:
        shift_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (shift_tolerance, shift_tolerance)
        )
        dilated_b = cv2.dilate(b_mask.astype(np.uint8), shift_kernel) > 0
        dilated_a = cv2.dilate(a_mask.astype(np.uint8), shift_kernel) > 0
        removed = removed & ~(removed & dilated_b)
        added = added & ~(added & dilated_a)

    unchanged = a_mask & b_mask

    # Build overlay image
    overlay = np.full_like(aligned_a, 255, dtype=np.uint8)

    # Removed areas: blend original grayscale with red tint
    if np.any(removed):
        removed_gray = a_gray[removed].astype(np.float32)
        removed_rgb = np.column_stack([removed_gray, removed_gray, removed_gray])
        red_tint = np.array([255.0, 0.0, 0.0])
        overlay[removed] = np.clip(
            removed_rgb * (1 - tint_strength) + red_tint * tint_strength, 0, 255
        ).astype(np.uint8)

    # Added areas: blend original grayscale with green tint
    if np.any(added):
        added_gray = b_gray[added].astype(np.float32)
        added_rgb = np.column_stack([added_gray, added_gray, added_gray])
        green_tint = np.array([0.0, 255.0, 0.0])
        overlay[added] = np.clip(
            added_rgb * (1 - tint_strength) + green_tint * tint_strength, 0, 255
        ).astype(np.uint8)

    # Unchanged areas: grayscale from image A
    overlay[unchanged] = np.stack([a_gray[unchanged]] * 3, axis=-1)

    # Build deletion and addition images
    deletion = np.full_like(aligned_a, 255, dtype=np.uint8)
    deletion[removed] = [0, 0, 0]

    addition = np.full_like(aligned_b, 255, dtype=np.uint8)
    addition[added] = [0, 0, 0]

    return overlay, deletion, addition
