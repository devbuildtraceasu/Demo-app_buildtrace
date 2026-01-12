"""Prototype script to improve generate_addition_image and generate_deletion_image.

Problem: Current algorithm produces "false" diff pixels due to:
- Slight pixel shifts from alignment
- Line width variations
- Anti-aliasing artifacts

This script experiments with different approaches:
1. Morphological operations (erosion/dilation)
2. Connected component filtering (remove small regions)
3. Gaussian blur before comparison
4. Dilation of masks before XOR (to account for shifts)
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# Increase PIL's decompression bomb limit for large construction drawings
# Construction drawings at 300 DPI can be very large (e.g., 24x36 inch = 216M pixels)
Image.MAX_IMAGE_PIXELS = 250_000_000  # 250 million pixels

# Dataset paths
DATASET_DIR = Path(__file__).parent / "dataset"
ALIGNED_OLD_PATH = DATASET_DIR / "page_0_aligned_old.png"
NEW_PATH = DATASET_DIR / "page_0_new.png"
OUTPUT_DIR = Path(__file__).parent / "output_cropped"


def load_image(path: Path) -> np.ndarray:
    """Load image as RGB numpy array."""
    img = Image.open(path)
    return np.array(img.convert("RGB"), dtype=np.uint8)


def save_image(img: np.ndarray, name: str) -> None:
    """Save RGB numpy array as PNG."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    Image.fromarray(img, mode="RGB").save(OUTPUT_DIR / f"{name}.png")
    print(f"Saved: {OUTPUT_DIR / name}.png")


def add_label_and_border(img: np.ndarray, label: str, border_color: tuple) -> np.ndarray:
    """Add colored border and label text to image.

    Args:
        img: Input image (RGB)
        label: Text label to add in top-left corner
        border_color: RGB color tuple for border (e.g., (255, 0, 0) for red)

    Returns:
        Image with border and label
    """
    # Make a copy to avoid modifying original
    result = img.copy()

    # Add border (10 pixels thick)
    border_thickness = 10
    height, width = result.shape[:2]

    # Draw border rectangle
    cv2.rectangle(result, (0, 0), (width - 1, height - 1), border_color, thickness=border_thickness)

    # Add text label with background
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5
    font_thickness = 3
    text_padding = 10

    # Get text size
    (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)

    # Draw black background rectangle for text
    cv2.rectangle(
        result,
        (border_thickness, border_thickness),
        (
            border_thickness + text_width + 2 * text_padding,
            border_thickness + text_height + 2 * text_padding + baseline,
        ),
        (0, 0, 0),
        thickness=-1,  # Filled rectangle
    )

    # Draw white text on black background
    cv2.putText(
        result,
        label,
        (border_thickness + text_padding, border_thickness + text_height + text_padding),
        font,
        font_scale,
        (255, 255, 255),
        font_thickness,
        lineType=cv2.LINE_AA,
    )

    return result


def concatenate_vertical(
    img1: np.ndarray, img2: np.ndarray, label1: str = "CURRENT", label2: str = "NEW"
) -> np.ndarray:
    """Concatenate two images vertically with labels and borders.

    Args:
        img1: First image (top) - typically the baseline/current
        img2: Second image (bottom) - typically the new method
        label1: Label for first image (default: "CURRENT")
        label2: Label for second image (default: "NEW")

    Returns:
        Vertically concatenated image with labels and borders
    """
    # Ensure images have same width
    if img1.shape[1] != img2.shape[1]:
        raise ValueError(f"Images must have same width: {img1.shape[1]} != {img2.shape[1]}")

    # Add labels and borders
    # Current: Blue border
    img1_labeled = add_label_and_border(img1, label1, (0, 100, 255))
    # New method: Green border
    img2_labeled = add_label_and_border(img2, label2, (0, 200, 0))

    # Stack vertically
    return np.vstack([img1_labeled, img2_labeled])


def convert_to_grayscale(rgb_image: np.ndarray) -> np.ndarray:
    """Convert RGB to grayscale."""
    return cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)


# =============================================================================
# Current Implementation (baseline)
# =============================================================================


def generate_deletion_current(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
) -> np.ndarray:
    """Current implementation from alignment.py."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = old_gray < threshold
    new_mask = new_gray < threshold

    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold

    removed = old_mask & ~new_mask & strong_diff_mask

    deletion_img = np.full_like(aligned_old, 255, dtype=np.uint8)
    deletion_img[removed] = [0, 0, 0]

    return deletion_img


def generate_addition_current(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
) -> np.ndarray:
    """Current implementation from alignment.py."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = old_gray < threshold
    new_mask = new_gray < threshold

    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold

    added = new_mask & ~old_mask & strong_diff_mask

    addition_img = np.full_like(new, 255, dtype=np.uint8)
    addition_img[added] = [0, 0, 0]

    return addition_img


def generate_addition_morph(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    morph_kernel_size: int = 3,
    morph_iterations: int = 1,
) -> np.ndarray:
    """Use morphological opening to remove small isolated pixels."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = old_gray < threshold
    new_mask = new_gray < threshold

    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold

    added = new_mask & ~old_mask & strong_diff_mask

    # Apply morphological opening
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size))
    added_cleaned = (
        cv2.morphologyEx(
            added.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel, iterations=morph_iterations
        )
        > 0
    )

    addition_img = np.full_like(new, 255, dtype=np.uint8)
    addition_img[added_cleaned] = [0, 0, 0]

    return addition_img


def generate_addition_cc_filter(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    min_component_area: int = 50,
) -> np.ndarray:
    """Filter out small connected components."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = old_gray < threshold
    new_mask = new_gray < threshold

    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold

    added = (new_mask & ~old_mask & strong_diff_mask).astype(np.uint8) * 255

    # Find connected components
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(added, connectivity=8)

    # Filter out small components
    added_cleaned = np.zeros_like(added)
    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_component_area:
            added_cleaned[labels == label] = 255

    addition_img = np.full_like(new, 255, dtype=np.uint8)
    addition_img[added_cleaned > 0] = [0, 0, 0]

    return addition_img


def generate_addition_dilated_mask(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    dilation_size: int = 3,
) -> np.ndarray:
    """Dilate the old mask before XOR to account for pixel shifts."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = (old_gray < threshold).astype(np.uint8) * 255
    new_mask = (new_gray < threshold).astype(np.uint8) * 255

    # Dilate the old mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_size, dilation_size))
    old_mask_dilated = cv2.dilate(old_mask, kernel, iterations=1)

    # Addition = new but not in dilated old
    added = (new_mask > 0) & (old_mask_dilated == 0)

    # Still apply intensity threshold
    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold
    added = added & strong_diff_mask

    addition_img = np.full_like(new, 255, dtype=np.uint8)
    addition_img[added] = [0, 0, 0]

    return addition_img


def generate_addition_blur(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    blur_size: int = 3,
) -> np.ndarray:
    """Apply Gaussian blur before comparison."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    # Apply Gaussian blur
    old_gray_blur = cv2.GaussianBlur(old_gray, (blur_size, blur_size), 0)
    new_gray_blur = cv2.GaussianBlur(new_gray, (blur_size, blur_size), 0)

    threshold = 250
    old_mask = old_gray_blur < threshold
    new_mask = new_gray_blur < threshold

    diff = cv2.absdiff(old_gray_blur, new_gray_blur)
    strong_diff_mask = diff > intensity_threshold

    added = new_mask & ~old_mask & strong_diff_mask

    addition_img = np.full_like(new, 255, dtype=np.uint8)
    addition_img[added] = [0, 0, 0]

    return addition_img


def generate_addition_distance(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    min_distance: int = 2,
) -> np.ndarray:
    """Use distance transform to filter pixels too close to old content."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    new_mask = new_gray < threshold
    old_mask = (old_gray < threshold).astype(np.uint8) * 255

    # Calculate distance from each pixel to nearest content in old image
    dist_to_old = cv2.distanceTransform(255 - old_mask, cv2.DIST_L2, 5)

    # Addition = new but not in old AND far enough from old content
    added = new_mask & ~(old_gray < threshold) & (dist_to_old > min_distance)

    # Apply intensity threshold
    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold
    added = added & strong_diff_mask

    addition_img = np.full_like(new, 255, dtype=np.uint8)
    addition_img[added] = [0, 0, 0]

    return addition_img


# =============================================================================
# Approach 1: Morphological Operations
# =============================================================================


def generate_deletion_morph(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    morph_kernel_size: int = 3,
    morph_iterations: int = 1,
) -> np.ndarray:
    """Use morphological opening to remove small isolated pixels."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = old_gray < threshold
    new_mask = new_gray < threshold

    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold

    removed = old_mask & ~new_mask & strong_diff_mask

    # Apply morphological opening (erosion then dilation)
    # This removes small isolated pixels while preserving larger structures
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size))
    removed_cleaned = (
        cv2.morphologyEx(
            removed.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel, iterations=morph_iterations
        )
        > 0
    )

    deletion_img = np.full_like(aligned_old, 255, dtype=np.uint8)
    deletion_img[removed_cleaned] = [0, 0, 0]

    return deletion_img


# =============================================================================
# Approach 2: Connected Component Filtering
# =============================================================================


def generate_deletion_cc_filter(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    min_component_area: int = 50,
) -> np.ndarray:
    """Filter out small connected components (isolated pixel clusters)."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = old_gray < threshold
    new_mask = new_gray < threshold

    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold

    removed = (old_mask & ~new_mask & strong_diff_mask).astype(np.uint8) * 255

    # Find connected components
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(removed, connectivity=8)

    # Filter out small components
    removed_cleaned = np.zeros_like(removed)
    for label in range(1, num_labels):  # Skip background (label 0)
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_component_area:
            removed_cleaned[labels == label] = 255

    deletion_img = np.full_like(aligned_old, 255, dtype=np.uint8)
    deletion_img[removed_cleaned > 0] = [0, 0, 0]

    return deletion_img


# =============================================================================
# Approach 3: Dilate masks before XOR (account for pixel shifts)
# =============================================================================


def generate_deletion_dilated_mask(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    dilation_size: int = 3,
) -> np.ndarray:
    """Dilate the new mask before XOR to account for pixel shifts."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = (old_gray < threshold).astype(np.uint8) * 255
    new_mask = (new_gray < threshold).astype(np.uint8) * 255

    # Dilate the new mask to "grow" it slightly
    # This will cover pixels that are slightly shifted
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_size, dilation_size))
    new_mask_dilated = cv2.dilate(new_mask, kernel, iterations=1)

    # Deletion = old but not in dilated new
    removed = (old_mask > 0) & (new_mask_dilated == 0)

    # Still apply intensity threshold
    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold
    removed = removed & strong_diff_mask

    deletion_img = np.full_like(aligned_old, 255, dtype=np.uint8)
    deletion_img[removed] = [0, 0, 0]

    return deletion_img


# =============================================================================
# Approach 4: Gaussian blur before comparison
# =============================================================================


def generate_deletion_blur(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    blur_size: int = 3,
) -> np.ndarray:
    """Apply Gaussian blur before comparison to reduce high-frequency noise."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    # Apply Gaussian blur
    old_gray_blur = cv2.GaussianBlur(old_gray, (blur_size, blur_size), 0)
    new_gray_blur = cv2.GaussianBlur(new_gray, (blur_size, blur_size), 0)

    threshold = 250
    old_mask = old_gray_blur < threshold
    new_mask = new_gray_blur < threshold

    diff = cv2.absdiff(old_gray_blur, new_gray_blur)
    strong_diff_mask = diff > intensity_threshold

    removed = old_mask & ~new_mask & strong_diff_mask

    deletion_img = np.full_like(aligned_old, 255, dtype=np.uint8)
    deletion_img[removed] = [0, 0, 0]

    return deletion_img


# =============================================================================
# Approach 5: Combined - Dilated mask + Morphological + CC filter
# =============================================================================


def generate_deletion_combined(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 30,
    dilation_size: int = 2,
    morph_kernel_size: int = 2,
    min_component_area: int = 20,
) -> np.ndarray:
    """Combined approach: dilated mask + morph opening + CC filter."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = (old_gray < threshold).astype(np.uint8) * 255
    new_mask = (new_gray < threshold).astype(np.uint8) * 255

    # Step 1: Dilate new mask to account for pixel shifts
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_size, dilation_size))
    new_mask_dilated = cv2.dilate(new_mask, kernel_dilate, iterations=1)

    # Deletion = old but not in dilated new
    removed = (old_mask > 0) & (new_mask_dilated == 0)

    # Step 2: Apply intensity threshold
    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold
    removed = (removed & strong_diff_mask).astype(np.uint8) * 255

    # Step 3: Morphological opening
    kernel_morph = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size)
    )
    removed = cv2.morphologyEx(removed, cv2.MORPH_OPEN, kernel_morph)

    # Step 4: Connected component filtering
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(removed, connectivity=8)
    removed_cleaned = np.zeros_like(removed)
    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_component_area:
            removed_cleaned[labels == label] = 255

    deletion_img = np.full_like(aligned_old, 255, dtype=np.uint8)
    deletion_img[removed_cleaned > 0] = [0, 0, 0]

    return deletion_img


def generate_addition_combined(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 30,
    dilation_size: int = 2,
    morph_kernel_size: int = 2,
    min_component_area: int = 20,
) -> np.ndarray:
    """Combined approach for additions: dilated mask + morph opening + CC filter."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = (old_gray < threshold).astype(np.uint8) * 255
    new_mask = (new_gray < threshold).astype(np.uint8) * 255

    # Step 1: Dilate OLD mask to account for pixel shifts
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_size, dilation_size))
    old_mask_dilated = cv2.dilate(old_mask, kernel_dilate, iterations=1)

    # Addition = new but not in dilated old
    added = (new_mask > 0) & (old_mask_dilated == 0)

    # Step 2: Apply intensity threshold
    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold
    added = (added & strong_diff_mask).astype(np.uint8) * 255

    # Step 3: Morphological opening
    kernel_morph = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size)
    )
    added = cv2.morphologyEx(added, cv2.MORPH_OPEN, kernel_morph)

    # Step 4: Connected component filtering
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(added, connectivity=8)
    added_cleaned = np.zeros_like(added)
    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_component_area:
            added_cleaned[labels == label] = 255

    addition_img = np.full_like(new, 255, dtype=np.uint8)
    addition_img[added_cleaned > 0] = [0, 0, 0]

    return addition_img


# =============================================================================
# Approach 6: Distance transform based filtering
# =============================================================================


def generate_deletion_distance(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    min_distance: int = 2,
) -> np.ndarray:
    """Use distance transform to filter pixels too close to new content."""
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    threshold = 250
    old_mask = old_gray < threshold
    new_mask = (new_gray < threshold).astype(np.uint8) * 255

    # Calculate distance from each pixel to nearest content in new image
    # Invert because distanceTransform measures distance to black (0)
    dist_to_new = cv2.distanceTransform(255 - new_mask, cv2.DIST_L2, 5)

    # Deletion = old but not in new AND far enough from new content
    removed = old_mask & ~(new_gray < threshold) & (dist_to_new > min_distance)

    # Apply intensity threshold
    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold
    removed = removed & strong_diff_mask

    deletion_img = np.full_like(aligned_old, 255, dtype=np.uint8)
    deletion_img[removed] = [0, 0, 0]

    return deletion_img


# =============================================================================
# Main - Run all approaches and compare
# =============================================================================


def count_pixels(img: np.ndarray) -> int:
    """Count black pixels (changes) in a white-background image."""
    gray = convert_to_grayscale(img)
    return np.sum(gray < 128)


def main():
    print("Loading images...")
    aligned_old = load_image(ALIGNED_OLD_PATH)
    new = load_image(NEW_PATH)
    print(f"  Original aligned_old: {aligned_old.shape}")
    print(f"  Original new: {new.shape}")

    # Crop to specific bounding box for faster analysis
    # Bounding box: (xmin, ymin), (xmax, ymax)
    xmin, ymin = 7700, 3524
    xmax, ymax = 10000, 4882
    print(f"\nCropping to bounding box: ({xmin}, {ymin}), ({xmax}, {ymax})")

    aligned_old = aligned_old[ymin:ymax, xmin:xmax]
    new = new[ymin:ymax, xmin:xmax]

    print(f"  Cropped aligned_old: {aligned_old.shape}")
    print(f"  Cropped new: {new.shape}")

    print("\n" + "=" * 60)
    print("DELETION IMAGE COMPARISON")
    print("=" * 60)

    # Current implementation (baseline)
    print("\n1. Current implementation (intensity_threshold=40):")
    del_current = generate_deletion_current(aligned_old, new, intensity_threshold=40)
    save_image(del_current, "deletion_current")
    print(f"   Black pixels: {count_pixels(del_current):,}")

    # Helper function to save comparison
    def save_comparison(result_img, name, description, pixel_count):
        # Save individual image
        save_image(result_img, name)
        # Save concatenated comparison (current on top, new result on bottom)
        comparison = concatenate_vertical(del_current, result_img, "CURRENT", description)
        save_image(comparison, f"{name}_vs_current")
        print(f"   Black pixels: {pixel_count:,}")

    # Higher threshold
    print("\n2. Current with higher threshold (intensity_threshold=80):")
    del_high_thresh = generate_deletion_current(aligned_old, new, intensity_threshold=80)
    save_comparison(
        del_high_thresh, "deletion_high_thresh", "THRESHOLD=80", count_pixels(del_high_thresh)
    )

    # Morphological opening
    print("\n3. Morphological opening (kernel=3, iterations=1):")
    del_morph = generate_deletion_morph(aligned_old, new, morph_kernel_size=3)
    save_comparison(del_morph, "deletion_morph_k3", "MORPH K=3", count_pixels(del_morph))

    print("\n4. Morphological opening (kernel=5, iterations=1):")
    del_morph5 = generate_deletion_morph(aligned_old, new, morph_kernel_size=5)
    save_comparison(del_morph5, "deletion_morph_k5", "MORPH K=5", count_pixels(del_morph5))

    # Connected component filtering
    print("\n5. Connected component filter (min_area=50):")
    del_cc50 = generate_deletion_cc_filter(aligned_old, new, min_component_area=50)
    save_comparison(del_cc50, "deletion_cc_50", "CC MIN=50", count_pixels(del_cc50))

    print("\n6. Connected component filter (min_area=100):")
    del_cc100 = generate_deletion_cc_filter(aligned_old, new, min_component_area=100)
    save_comparison(del_cc100, "deletion_cc_100", "CC MIN=100", count_pixels(del_cc100))

    # Dilated mask
    print("\n7. Dilated mask (dilation_size=3):")
    del_dilated3 = generate_deletion_dilated_mask(aligned_old, new, dilation_size=3)
    save_comparison(del_dilated3, "deletion_dilated_3", "DILATED=3", count_pixels(del_dilated3))

    print("\n8. Dilated mask (dilation_size=5):")
    del_dilated5 = generate_deletion_dilated_mask(aligned_old, new, dilation_size=5)
    save_comparison(del_dilated5, "deletion_dilated_5", "DILATED=5", count_pixels(del_dilated5))

    # Blur
    print("\n9. Gaussian blur (blur_size=5):")
    del_blur = generate_deletion_blur(aligned_old, new, blur_size=5)
    save_comparison(del_blur, "deletion_blur_5", "BLUR=5", count_pixels(del_blur))

    # Combined approach
    print("\n10. Combined (dilate=2, morph=2, cc_min=20):")
    del_combined = generate_deletion_combined(aligned_old, new)
    save_comparison(del_combined, "deletion_combined", "COMBINED", count_pixels(del_combined))

    print("\n11. Combined aggressive (dilate=3, morph=3, cc_min=50):")
    del_combined_agg = generate_deletion_combined(
        aligned_old, new, dilation_size=3, morph_kernel_size=3, min_component_area=50
    )
    save_comparison(
        del_combined_agg,
        "deletion_combined_aggressive",
        "COMBINED AGGRESSIVE",
        count_pixels(del_combined_agg),
    )

    # Distance transform
    print("\n12. Distance transform (min_distance=2):")
    del_dist = generate_deletion_distance(aligned_old, new, min_distance=2)
    save_comparison(del_dist, "deletion_distance_2", "DISTANCE=2", count_pixels(del_dist))

    print("\n" + "=" * 60)
    print("ADDITION IMAGE COMPARISON")
    print("=" * 60)

    # Current implementation (baseline)
    print("\n1. Current implementation (intensity_threshold=40):")
    add_current = generate_addition_current(aligned_old, new)
    save_image(add_current, "addition_current")
    print(f"   Black pixels: {count_pixels(add_current):,}")

    # Helper function to save addition comparison
    def save_addition_comparison(result_img, name, description, pixel_count):
        # Save individual image
        save_image(result_img, name)
        # Save concatenated comparison
        comparison = concatenate_vertical(add_current, result_img, "CURRENT", description)
        save_image(comparison, f"{name}_vs_current")
        print(f"   Black pixels: {pixel_count:,}")

    # Higher threshold
    print("\n2. Current with higher threshold (intensity_threshold=80):")
    add_high_thresh = generate_addition_current(aligned_old, new, intensity_threshold=80)
    save_addition_comparison(
        add_high_thresh, "addition_high_thresh", "THRESHOLD=80", count_pixels(add_high_thresh)
    )

    # Morphological opening
    print("\n3. Morphological opening (kernel=3, iterations=1):")
    add_morph = generate_addition_morph(aligned_old, new, morph_kernel_size=3)
    save_addition_comparison(add_morph, "addition_morph_k3", "MORPH K=3", count_pixels(add_morph))

    print("\n4. Morphological opening (kernel=5, iterations=1):")
    add_morph5 = generate_addition_morph(aligned_old, new, morph_kernel_size=5)
    save_addition_comparison(add_morph5, "addition_morph_k5", "MORPH K=5", count_pixels(add_morph5))

    # Connected component filtering
    print("\n5. Connected component filter (min_area=50):")
    add_cc50 = generate_addition_cc_filter(aligned_old, new, min_component_area=50)
    save_addition_comparison(add_cc50, "addition_cc_50", "CC MIN=50", count_pixels(add_cc50))

    print("\n6. Connected component filter (min_area=100):")
    add_cc100 = generate_addition_cc_filter(aligned_old, new, min_component_area=100)
    save_addition_comparison(add_cc100, "addition_cc_100", "CC MIN=100", count_pixels(add_cc100))

    # Dilated mask
    print("\n7. Dilated mask (dilation_size=3):")
    add_dilated3 = generate_addition_dilated_mask(aligned_old, new, dilation_size=3)
    save_addition_comparison(
        add_dilated3, "addition_dilated_3", "DILATED=3", count_pixels(add_dilated3)
    )

    print("\n8. Dilated mask (dilation_size=5):")
    add_dilated5 = generate_addition_dilated_mask(aligned_old, new, dilation_size=5)
    save_addition_comparison(
        add_dilated5, "addition_dilated_5", "DILATED=5", count_pixels(add_dilated5)
    )

    # Blur
    print("\n9. Gaussian blur (blur_size=5):")
    add_blur = generate_addition_blur(aligned_old, new, blur_size=5)
    save_addition_comparison(add_blur, "addition_blur_5", "BLUR=5", count_pixels(add_blur))

    # Combined approach
    print("\n10. Combined (dilate=2, morph=2, cc_min=20):")
    add_combined = generate_addition_combined(aligned_old, new)
    save_addition_comparison(
        add_combined, "addition_combined", "COMBINED", count_pixels(add_combined)
    )

    print("\n11. Combined aggressive (dilate=3, morph=3, cc_min=50):")
    add_combined_agg = generate_addition_combined(
        aligned_old, new, dilation_size=3, morph_kernel_size=3, min_component_area=50
    )
    save_addition_comparison(
        add_combined_agg,
        "addition_combined_aggressive",
        "COMBINED AGGRESSIVE",
        count_pixels(add_combined_agg),
    )

    # Distance transform
    print("\n12. Distance transform (min_distance=2):")
    add_dist = generate_addition_distance(aligned_old, new, min_distance=2)
    save_addition_comparison(add_dist, "addition_distance_2", "DISTANCE=2", count_pixels(add_dist))

    print("\n" + "=" * 60)
    print(f"Output saved to: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
