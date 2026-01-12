"""SIFT-based image alignment with scipy L-BFGS-B constrained optimization.

This module provides SIFT feature matching with constrained optimization for aligning
construction drawing images. Uses scipy L-BFGS-B optimizer for enforcing scale and
rotation constraints during RANSAC, rather than post-hoc validation.

Key functions:
- sift_align(): Main entry point for SIFT-based alignment
- extract_sift_features(): Extract SIFT keypoints and descriptors
- match_features(): Match features with Lowe's ratio test
"""

import gc
from enum import Enum
from typing import Literal

import cv2
import numpy as np
import scipy.optimize
from PIL import Image
from pydantic import BaseModel, ConfigDict

# =============================================================================
# Pydantic Models
# =============================================================================


class AlignmentMethod(str, Enum):
    """Alignment method used for block overlay generation."""

    GRID = "grid"
    SIFT = "sift"


class AlignmentStats(BaseModel):
    """Statistics and parameters from alignment operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    method: Literal["grid", "sift"]
    scale: float | None = None  # Uniform scale for SIFT
    scale_x: float | None = None  # X-axis scale for grid
    scale_y: float | None = None  # Y-axis scale for grid
    rotation_deg: float | None = None  # Rotation in degrees (SIFT only)
    translate_x: float
    translate_y: float
    inlier_count: int | None = None
    inlier_ratio: float | None = None
    h_matches: int | None = None  # Horizontal grid matches
    v_matches: int | None = None  # Vertical grid matches
    expanded_width: int
    expanded_height: int
    offset_x: float
    offset_y: float
    matrix: list[list[float]]  # 2x3 affine matrix as nested list


# Increase PIL's decompression bomb limit for large construction drawings
# Construction drawings at 300 DPI can be very large (e.g., 24x36 inch = 216M pixels)
Image.MAX_IMAGE_PIXELS = 250_000_000  # 250 million pixels (~16,000 x 16,000)


def _load_image_from_bytes(png_bytes: bytes) -> np.ndarray:
    """Decode PNG bytes to NumPy array (RGB format).

    Args:
        png_bytes: PNG image as bytes

    Returns:
        NumPy array with shape (H, W, 3) in RGB format

    Raises:
        ValueError: If image decoding fails
    """
    try:
        import io

        img = Image.open(io.BytesIO(png_bytes))
        # Convert to RGB (handles RGBA, grayscale, etc.)
        img_rgb = img.convert("RGB")
        # Convert to numpy array
        return np.array(img_rgb, dtype=np.uint8)
    except Exception as e:
        raise ValueError(f"Failed to decode PNG bytes: {e}")


def _encode_image_to_png(image_array: np.ndarray) -> bytes:
    """Encode NumPy array to PNG bytes.

    Args:
        image_array: NumPy array with shape (H, W, 3) in RGB format

    Returns:
        PNG image as bytes

    Raises:
        ValueError: If image encoding fails
    """
    # Validate shape
    if len(image_array.shape) != 3 or image_array.shape[2] != 3:
        raise ValueError(f"Expected RGB image with shape (H, W, 3), got {image_array.shape}")

    try:
        import io

        # Convert numpy array to PIL Image
        img = Image.fromarray(image_array, mode="RGB")
        # Encode to PNG bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as e:
        raise ValueError(f"Failed to encode image to PNG: {e}")


def extract_sift_features(
    gray_image: np.ndarray,
    n_features: int = 10_000,
    exclude_margin: float = 0.2,
    contrast_threshold: float = 0.04,
    edge_threshold: float = 10,
) -> tuple[tuple, np.ndarray]:
    """Extract SIFT features from grayscale image with margin exclusion.

    Detects up to n_features keypoints, excluding a margin area (default 20% from each edge)
    to avoid edge artifacts and title blocks.

    Args:
        gray_image: Grayscale image (H, W) with dtype uint8
        n_features: Maximum number of SIFT features to detect (default: 10,000)
        exclude_margin: Margin exclusion ratio (default: 0.2 = 20%)
        contrast_threshold: Filter weak features (default: 0.04, lower = more features)
        edge_threshold: Filter edge-like features (default: 10, higher = more features)

    Returns:
        Tuple of (keypoints, descriptors):
            - keypoints: Tuple of cv2.KeyPoint objects
            - descriptors: NumPy array of shape (N, 128) where N <= n_features

    Raises:
        ValueError: If gray_image is not grayscale or margin is invalid
    """
    # Validate input
    if len(gray_image.shape) != 2:
        raise ValueError(f"Expected grayscale image with shape (H, W), got {gray_image.shape}")

    if not (0.0 <= exclude_margin < 0.5):
        raise ValueError(f"exclude_margin must be in [0.0, 0.5), got {exclude_margin}")

    height, width = gray_image.shape

    # Create margin exclusion mask
    mask = np.zeros((height, width), dtype=np.uint8)
    margin_y = int(height * exclude_margin)
    margin_x = int(width * exclude_margin)
    mask[margin_y : height - margin_y, margin_x : width - margin_x] = 255

    # Create SIFT detector
    sift = cv2.SIFT_create(
        nfeatures=n_features,
        contrastThreshold=contrast_threshold,
        edgeThreshold=edge_threshold,
    )

    # Detect features with mask
    keypoints, descriptors = sift.detectAndCompute(gray_image, mask=mask)

    # Convert keypoints list to tuple for immutability
    return tuple(keypoints), descriptors


def match_features(
    descriptors1: np.ndarray,
    descriptors2: np.ndarray,
    ratio_threshold: float = 0.75,
) -> list:
    """Match SIFT features using Brute-Force matcher and Lowe's ratio test.

    Args:
        descriptors1: Feature descriptors from first image (N1, 128)
        descriptors2: Feature descriptors from second image (N2, 128)
        ratio_threshold: Lowe's ratio test threshold (default: 0.75)

    Returns:
        List of cv2.DMatch objects representing good matches

    Raises:
        ValueError: If descriptors are empty or have incompatible shapes
    """
    # Validate inputs
    if descriptors1 is None or len(descriptors1) == 0:
        raise ValueError("descriptors1 cannot be empty")
    if descriptors2 is None or len(descriptors2) == 0:
        raise ValueError("descriptors2 cannot be empty")

    # Create Brute-Force matcher with L2 norm (for SIFT/SURF)
    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

    # Find k=2 nearest matches for each descriptor
    knn_matches = bf.knnMatch(descriptors1, descriptors2, k=2)

    # Apply Lowe's ratio test to filter good matches
    good_matches = []
    for match_pair in knn_matches:
        # Need at least 2 matches to apply ratio test
        if len(match_pair) == 2:
            m, n = match_pair
            # Keep match if best match is significantly better than second best
            if m.distance < ratio_threshold * n.distance:
                good_matches.append(m)

    return good_matches


def estimate_transformation(
    keypoints1: tuple,
    keypoints2: tuple,
    matches: list,
    reproj_threshold: float = 15.0,
    max_iters: int = 5_000,
    confidence: float = 0.95,
    scale_min: float = 0.2,
    scale_max: float = 5.0,
    rotation_deg_min: float = -30.0,
    rotation_deg_max: float = 30.0,
) -> tuple[np.ndarray | None, np.ndarray | None, int, int]:
    """Estimate constrained affine transformation using RANSAC.

    Finds the best affine transformation that aligns image1 to image2 while
    enforcing constraints on scale (0.3x to 2.5x) and rotation (±30 degrees).

    Args:
        keypoints1: Keypoints from first image (tuple of cv2.KeyPoint)
        keypoints2: Keypoints from second image (tuple of cv2.KeyPoint)
        matches: Good matches from match_features()
        reproj_threshold: RANSAC reprojection threshold in pixels (default: 15.0)
        max_iters: Maximum RANSAC iterations (default: 5,000)
        confidence: RANSAC confidence level (default: 0.95)
        scale_min: Minimum allowed scale factor (default: 0.3)
        scale_max: Maximum allowed scale factor (default: 2.5)
        rotation_deg_min: Minimum allowed rotation in degrees (default: -30.0)
        rotation_deg_max: Maximum allowed rotation in degrees (default: 30.0)

    Returns:
        Tuple of (transformation_matrix, mask, inlier_count, total_matches):
            - transformation_matrix: 2x3 affine matrix or None if failed
            - mask: Binary mask (N, 1) indicating inliers (1) vs outliers (0), or None
            - inlier_count: Number of inliers (features that fit transformation)
            - total_matches: Total number of matches before RANSAC

    Raises:
        ValueError: If insufficient matches (< 3) for transformation estimation
    """
    total_matches = len(matches)

    if total_matches < 3:
        raise ValueError(f"Insufficient matches for transformation estimation: {total_matches} < 3")

    # Extract matched point coordinates
    pts1 = np.float32([keypoints1[m.queryIdx].pt for m in matches])
    pts2 = np.float32([keypoints2[m.trainIdx].pt for m in matches])

    # Use cv2.estimateAffinePartial2D with RANSAC
    # This finds rotation + uniform scale + translation (4 DOF affine)
    matrix, mask = cv2.estimateAffinePartial2D(
        pts1,
        pts2,
        method=cv2.RANSAC,
        ransacReprojThreshold=reproj_threshold,
        maxIters=max_iters,
        confidence=confidence,
    )

    if matrix is None:
        # RANSAC failed to find a valid transformation
        return None, None, 0, total_matches

    # Validate constraints
    # Extract scale and rotation from transformation matrix
    # matrix = [[s*cos(θ), -s*sin(θ), tx],
    #           [s*sin(θ),  s*cos(θ), ty]]
    scale = np.sqrt(matrix[0, 0] ** 2 + matrix[1, 0] ** 2)
    rotation_rad = np.arctan2(matrix[1, 0], matrix[0, 0])
    rotation_deg = np.degrees(rotation_rad)

    # Check constraints
    if not (scale_min <= scale <= scale_max):
        # Scale out of bounds, reject transformation
        return None, None, 0, total_matches

    if not (rotation_deg_min <= rotation_deg <= rotation_deg_max):
        # Rotation out of bounds, reject transformation
        return None, None, 0, total_matches

    # Count inliers
    inlier_count = int(np.sum(mask)) if mask is not None else 0

    return matrix, mask, inlier_count, total_matches


def apply_transformation(
    image: np.ndarray,
    transformation_matrix: np.ndarray,
    output_shape: tuple[int, int],
) -> np.ndarray:
    """Apply affine transformation to warp image.

    Args:
        image: Input image (H1, W1, 3) in RGB format
        transformation_matrix: 2x3 affine transformation matrix
        output_shape: Desired output shape (width, height)

    Returns:
        Warped image with shape (height, width, 3) in RGB format

    Raises:
        ValueError: If transformation_matrix shape is not (2, 3)
    """
    # Validate matrix shape
    if transformation_matrix.shape != (2, 3):
        raise ValueError(
            f"Expected transformation_matrix shape (2, 3), got {transformation_matrix.shape}"
        )

    width, height = output_shape

    # Apply affine transformation using cv2.warpAffine
    # Note: cv2.warpAffine expects dsize=(width, height)
    warped = cv2.warpAffine(
        image,
        transformation_matrix,
        dsize=(width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),  # White background for missing areas
    )

    return warped


def _convert_to_grayscale(rgb_image: np.ndarray) -> np.ndarray:
    """Convert RGB image to grayscale for feature detection.

    Args:
        rgb_image: RGB image (H, W, 3) with dtype uint8

    Returns:
        Grayscale image (H, W) with dtype uint8

    Raises:
        ValueError: If image is not RGB format
    """
    if len(rgb_image.shape) != 3 or rgb_image.shape[2] != 3:
        raise ValueError(f"Expected RGB image with shape (H, W, 3), got {rgb_image.shape}")

    # Use cv2.cvtColor for consistent conversion (OpenCV uses BGR internally, but we handle RGB)
    # Convert RGB to grayscale using standard weights
    gray = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)
    return gray


def _apply_morphological_cleanup(
    mask: np.ndarray,
    morph_kernel_size: int = 3,
    morph_iterations: int = 1,
) -> np.ndarray:
    """Apply morphological opening to remove small isolated pixels (artifacts).

    Morphological opening (erosion followed by dilation) removes small isolated
    pixel clusters caused by sub-pixel alignment shifts, line width variations,
    and anti-aliasing differences, while preserving larger real changes.

    Args:
        mask: Binary mask (H, W) with dtype bool or uint8
        morph_kernel_size: Size of the elliptical kernel (default: 3)
        morph_iterations: Number of morphological iterations (default: 1)

    Returns:
        Cleaned binary mask (H, W) with dtype bool
    """
    # Convert to uint8 if boolean
    mask_uint8 = mask.astype(np.uint8) * 255 if mask.dtype == bool else mask

    # Create elliptical structuring element
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size))

    # Apply morphological opening (erosion then dilation)
    cleaned = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel, iterations=morph_iterations)

    return cleaned > 0


def _compute_change_masks(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    morph_kernel_size: int = 3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute deletion, addition, and unchanged masks from aligned images.

    This is the core diff algorithm used by generate_overlay, generate_deletion_image,
    and generate_addition_image to ensure consistent behavior across all three.

    Args:
        aligned_old: Aligned old image (H, W, 3) in RGB format
        new: New image (H, W, 3) in RGB format
        intensity_threshold: Minimum intensity difference (0-255) to classify as real change
        morph_kernel_size: Size of morphological cleanup kernel (default: 3)

    Returns:
        Tuple of (removed_mask, added_mask, unchanged_mask, old_gray):
            - removed_mask: Boolean mask (H, W) where True = deleted content
            - added_mask: Boolean mask (H, W) where True = added content
            - unchanged_mask: Boolean mask (H, W) where True = unchanged content
            - old_gray: Grayscale version of aligned_old for unchanged pixel values

    Raises:
        ValueError: If image dimensions don't match or images are not RGB
    """
    # Validate inputs
    if aligned_old.shape != new.shape:
        raise ValueError(
            f"Image dimensions must match: aligned_old {aligned_old.shape} != new {new.shape}"
        )

    if len(aligned_old.shape) != 3 or aligned_old.shape[2] != 3:
        raise ValueError(f"Expected RGB images with shape (H, W, 3), got {aligned_old.shape}")

    # Convert to grayscale for comparison
    old_gray = _convert_to_grayscale(aligned_old)
    new_gray = _convert_to_grayscale(new)

    # Apply threshold to create binary masks (pixels present vs absent)
    threshold = 250  # Close to white
    old_mask = old_gray < threshold
    new_mask = new_gray < threshold

    # Calculate absolute intensity difference to filter artifacts
    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > intensity_threshold

    # Compute raw change masks
    removed = old_mask & ~new_mask & strong_diff_mask
    added = new_mask & ~old_mask & strong_diff_mask

    # Apply morphological cleanup to remove small isolated artifact pixels
    removed_clean = _apply_morphological_cleanup(removed, morph_kernel_size)
    added_clean = _apply_morphological_cleanup(added, morph_kernel_size)

    # Unchanged = pixels in both images
    unchanged = old_mask & new_mask

    return removed_clean, added_clean, unchanged, old_gray


def generate_overlay(
    aligned_old: np.ndarray,
    new: np.ndarray,
    intensity_threshold: int = 40,
    morph_kernel_size: int = 3,
) -> np.ndarray:
    """Generate red/green/gray overlay image showing pixel differences.

    Replicates the proven pixel-difference algorithm from image_utils.create_overlay_image():
    - Red channel: Pixels only in old image (removed content)
    - Green channel: Pixels only in new image (added content)
    - Gray: Pixels in both images (unchanged content)

    Uses morphological opening to remove small isolated artifact pixels caused by
    sub-pixel alignment shifts and anti-aliasing differences.

    Args:
        aligned_old: Aligned old image (H, W, 3) in RGB format
        new: New image (H, W, 3) in RGB format
        intensity_threshold: Minimum intensity difference (0-255) to classify as real change.
                           Default: 40 (filters anti-aliasing artifacts)
        morph_kernel_size: Size of morphological cleanup kernel (default: 3)

    Returns:
        Overlay image (H, W, 3) in RGB format with red/green/gray encoding

    Raises:
        ValueError: If image dimensions don't match or images are not RGB
    """
    # Compute masks using shared algorithm
    removed, added, unchanged, old_gray = _compute_change_masks(
        aligned_old, new, intensity_threshold, morph_kernel_size
    )

    # Create overlay image (start with white background)
    overlay = np.full_like(aligned_old, 255, dtype=np.uint8)

    # Red channel: Pixels only in old (removed content)
    overlay[removed] = [255, 0, 0]  # Red

    # Green channel: Pixels only in new (added content)
    overlay[added] = [0, 255, 0]  # Green

    # Gray: Pixels in both (unchanged content)
    overlay[unchanged] = np.stack([old_gray[unchanged]] * 3, axis=-1)

    return overlay


# =============================================================================
# New SIFT Alignment with Constrained Optimization
# =============================================================================


def _normalize_image_sizes(
    img_a: np.ndarray,
    img_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Prescale images to have similar diagonal lengths for better SIFT matching.

    Args:
        img_a: First image (H, W, 3)
        img_b: Second image (H, W, 3)

    Returns:
        (scaled_a, scaled_b, scale_factor_a, scale_factor_b)
    """
    h_a, w_a = img_a.shape[:2]
    h_b, w_b = img_b.shape[:2]
    diag_a = np.sqrt(h_a**2 + w_a**2)
    diag_b = np.sqrt(h_b**2 + w_b**2)

    scale_a = 1.0
    scale_b = 1.0

    # Scale larger image down to match smaller
    if diag_a > diag_b * 1.5:
        scale_a = diag_b / diag_a
    elif diag_b > diag_a * 1.5:
        scale_b = diag_a / diag_b

    if scale_a < 1.0:
        img_a = cv2.resize(img_a, None, fx=scale_a, fy=scale_a, interpolation=cv2.INTER_AREA)
    if scale_b < 1.0:
        img_b = cv2.resize(img_b, None, fx=scale_b, fy=scale_b, interpolation=cv2.INTER_AREA)

    return img_a, img_b, scale_a, scale_b


def _run_constrained_optimizer(
    from_points: np.ndarray,
    to_points: np.ndarray,
    scale_min: float | None = None,
    scale_max: float | None = None,
    rotation_deg_min: float | None = None,
    rotation_deg_max: float | None = None,
) -> np.ndarray:
    """Run constrained L-BFGS-B optimization to find best affine transform.

    Args:
        from_points: Source points (N, 2)
        to_points: Target points (N, 2)
        scale_min: Minimum allowed scale
        scale_max: Maximum allowed scale
        rotation_deg_min: Minimum rotation in degrees
        rotation_deg_max: Maximum rotation in degrees

    Returns:
        2x3 affine matrix

    Raises:
        RuntimeError: If optimization fails
    """
    if from_points.shape[0] < 2:
        raise RuntimeError("At least 2 points required for optimization")

    def objective_func(params):
        scale, theta_rad, tx, ty = params
        cos_theta, sin_theta = np.cos(theta_rad), np.sin(theta_rad)
        m = np.array(
            [
                [scale * cos_theta, -scale * sin_theta, tx],
                [scale * sin_theta, scale * cos_theta, ty],
            ]
        )
        from_hom = np.hstack([from_points, np.ones((from_points.shape[0], 1))])
        transformed = (m @ from_hom.T).T
        return np.sum((to_points - transformed) ** 2)

    # Initial estimate using OpenCV
    initial_m, _ = cv2.estimateAffinePartial2D(
        from_points.astype(np.float32), to_points.astype(np.float32)
    )
    if initial_m is not None:
        s_init = np.sqrt(initial_m[0, 0] ** 2 + initial_m[1, 0] ** 2)
        theta_init = np.arctan2(initial_m[1, 0], initial_m[0, 0])
        tx_init, ty_init = initial_m[0, 2], initial_m[1, 2]
    else:
        s_init, theta_init = 1.0, 0.0
        tx_init = np.mean(to_points[:, 0] - from_points[:, 0])
        ty_init = np.mean(to_points[:, 1] - from_points[:, 1])

    initial_guess = [s_init, theta_init, tx_init, ty_init]
    rot_min = np.deg2rad(rotation_deg_min) if rotation_deg_min is not None else -np.inf
    rot_max = np.deg2rad(rotation_deg_max) if rotation_deg_max is not None else np.inf
    bounds = [(scale_min, scale_max), (rot_min, rot_max), (None, None), (None, None)]

    result = scipy.optimize.minimize(
        objective_func, initial_guess, bounds=bounds, method="L-BFGS-B"
    )

    if not result.success:
        raise RuntimeError(f"Optimization failed: {result.message}")

    scale_opt, theta_opt, tx_opt, ty_opt = result.x
    cos_opt, sin_opt = np.cos(theta_opt), np.sin(theta_opt)
    return np.array(
        [
            [scale_opt * cos_opt, -scale_opt * sin_opt, tx_opt],
            [scale_opt * sin_opt, scale_opt * cos_opt, ty_opt],
        ]
    )


def _estimate_affine_constrained(
    from_points: np.ndarray,
    to_points: np.ndarray,
    ransac_threshold: float = 3.0,
    max_iters: int = 2000,
    confidence: float = 0.99,
    scale_min: float | None = None,
    scale_max: float | None = None,
    rotation_deg_min: float | None = None,
    rotation_deg_max: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate constrained affine transformation using RANSAC with optimization.

    Args:
        from_points: Source points (N, 2)
        to_points: Target points (N, 2)
        ransac_threshold: RANSAC reprojection threshold
        max_iters: Maximum RANSAC iterations
        confidence: RANSAC confidence level
        scale_min: Minimum allowed scale
        scale_max: Maximum allowed scale
        rotation_deg_min: Minimum rotation in degrees
        rotation_deg_max: Maximum rotation in degrees

    Returns:
        (matrix, inlier_mask)

    Raises:
        RuntimeError: If estimation fails
    """
    num_points = from_points.shape[0]
    if num_points < 2:
        raise RuntimeError("Need at least 2 points")

    rot_min = np.deg2rad(rotation_deg_min) if rotation_deg_min is not None else -np.inf
    rot_max = np.deg2rad(rotation_deg_max) if rotation_deg_max is not None else np.inf

    hypotheses = []
    best_inlier_count = -1
    from_hom = np.hstack([from_points, np.ones((num_points, 1))])
    current_max_iters = max_iters

    for iteration in range(max_iters):
        if iteration >= current_max_iters:
            break

        # Sample 2 points
        idx = np.random.choice(num_points, 2, replace=False)
        p1, p2 = from_points[idx]
        q1, q2 = to_points[idx]

        # Compute candidate
        v_from, v_to = p2 - p1, q2 - q1
        len_from = np.linalg.norm(v_from)
        if np.isclose(len_from, 0):
            continue

        # Check scale constraint
        scale = np.linalg.norm(v_to) / len_from
        if (scale_min is not None and scale < scale_min) or (
            scale_max is not None and scale > scale_max
        ):
            continue

        # Check rotation constraint
        angle_from = np.arctan2(v_from[1], v_from[0])
        angle_to = np.arctan2(v_to[1], v_to[0])
        theta = angle_to - angle_from
        # Normalize theta to [-pi, pi]
        theta = np.arctan2(np.sin(theta), np.cos(theta))
        if not (rot_min <= theta <= rot_max):
            continue

        # Form candidate matrix
        cos_t, sin_t = np.cos(theta), np.sin(theta)
        tx = q1[0] - (p1[0] * scale * cos_t - p1[1] * scale * sin_t)
        ty = q1[1] - (p1[0] * scale * sin_t + p1[1] * scale * cos_t)
        m_cand = np.array([[scale * cos_t, -scale * sin_t, tx], [scale * sin_t, scale * cos_t, ty]])

        # Count inliers
        transformed = (m_cand @ from_hom.T).T
        errors = np.linalg.norm(to_points - transformed, axis=1)
        inlier_mask = errors < ransac_threshold
        inlier_count = np.sum(inlier_mask)

        hypotheses.append((inlier_count, inlier_mask))

        if inlier_count > best_inlier_count:
            best_inlier_count = inlier_count
            inlier_ratio = inlier_count / num_points
            if inlier_ratio > 0:
                new_max = int(np.log(1 - confidence) / np.log(max(1 - inlier_ratio**2, 1e-10)))
                if new_max < current_max_iters:
                    current_max_iters = new_max

    if not hypotheses:
        raise RuntimeError("No valid hypotheses found")

    # Sort by inlier count and try optimization on best candidates
    hypotheses.sort(key=lambda x: x[0], reverse=True)

    for _, inlier_mask in hypotheses[:10]:  # Try top 10
        from_inliers = from_points[inlier_mask]
        to_inliers = to_points[inlier_mask]

        if len(from_inliers) < 2:
            continue

        try:
            final_matrix = _run_constrained_optimizer(
                from_inliers, to_inliers, scale_min, scale_max, rotation_deg_min, rotation_deg_max
            )
            return final_matrix, inlier_mask.astype(np.uint8).reshape(-1, 1)
        except RuntimeError:
            pass

    raise RuntimeError("All optimization attempts failed")


def _expand_canvas(
    img_a: np.ndarray,
    img_b: np.ndarray,
    matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Expand canvas to fit both transformed img_a and img_b.

    Args:
        img_a: Image A to be transformed
        img_b: Image B (reference)
        matrix: 2x3 affine transformation matrix

    Returns:
        (aligned_a, aligned_b, adjusted_matrix, offset_x, offset_y)
    """
    h_a, w_a = img_a.shape[:2]
    h_b, w_b = img_b.shape[:2]

    # Calculate bounding box of transformed img_a
    corners = np.array([[0, 0, 1], [w_a, 0, 1], [w_a, h_a, 1], [0, h_a, 1]], dtype=np.float64).T
    transformed_corners = matrix @ corners

    x_min = min(0, np.min(transformed_corners[0]))
    y_min = min(0, np.min(transformed_corners[1]))
    x_max = max(w_b, np.max(transformed_corners[0]))
    y_max = max(h_b, np.max(transformed_corners[1]))

    offset_x = -x_min if x_min < 0 else 0
    offset_y = -y_min if y_min < 0 else 0
    output_w = int(np.ceil(x_max - x_min))
    output_h = int(np.ceil(y_max - y_min))

    # Adjust matrix for offset
    adjusted_matrix = matrix.copy()
    adjusted_matrix[0, 2] += offset_x
    adjusted_matrix[1, 2] += offset_y

    # Apply transformation to img_a
    aligned_a = apply_transformation(img_a, adjusted_matrix, output_shape=(output_w, output_h))

    # Place img_b on expanded canvas
    aligned_b = np.full((output_h, output_w, 3), 255, dtype=img_b.dtype)
    x_start, y_start = int(offset_x), int(offset_y)
    aligned_b[y_start : y_start + h_b, x_start : x_start + w_b] = img_b

    return aligned_a, aligned_b, adjusted_matrix, offset_x, offset_y


def sift_align(
    img_a: np.ndarray,
    img_b: np.ndarray,
    *,
    downsample_scale: float = 0.5,
    n_features: int = 20000,
    ratio_threshold: float = 0.75,
    ransac_threshold: float = 15.0,
    max_iters: int = 10000,
    scale_min: float = 0.2,
    scale_max: float = 5.0,
    rotation_deg_min: float = -3.0,
    rotation_deg_max: float = 3.0,
    normalize_size: bool = True,
    contrast_threshold: float = 0.02,
    expand_canvas: bool = True,
) -> tuple[np.ndarray, np.ndarray, AlignmentStats]:
    """Perform SIFT-based alignment with scipy L-BFGS-B constrained optimization.

    Args:
        img_a: Image A in RGB format (to be transformed)
        img_b: Image B in RGB format (reference)
        downsample_scale: Scale factor for SIFT processing
        n_features: Maximum SIFT features to extract
        ratio_threshold: Lowe's ratio test threshold
        ransac_threshold: RANSAC reprojection threshold
        max_iters: RANSAC maximum iterations
        scale_min: Minimum allowed scale factor
        scale_max: Maximum allowed scale factor
        rotation_deg_min: Minimum rotation in degrees
        rotation_deg_max: Maximum rotation in degrees
        normalize_size: Whether to prescale images to similar size
        contrast_threshold: SIFT contrast threshold
        expand_canvas: Whether to expand output to fit both images

    Returns:
        (aligned_a, aligned_b, stats)

    Raises:
        RuntimeError: If alignment fails (insufficient features/matches)
    """
    h_a, w_a = img_a.shape[:2]
    h_b, w_b = img_b.shape[:2]

    # Optional size normalization
    prescale_a = 1.0
    prescale_b = 1.0
    if normalize_size:
        diag_a = np.sqrt(h_a**2 + w_a**2)
        diag_b = np.sqrt(h_b**2 + w_b**2)
        if diag_a > diag_b * 1.5:
            prescale_a = diag_b / diag_a
        elif diag_b > diag_a * 1.5:
            prescale_b = diag_a / diag_b

    # Downsample for SIFT (combined with prescale)
    scale_a = downsample_scale * prescale_a
    scale_b = downsample_scale * prescale_b
    small_a = cv2.resize(img_a, None, fx=scale_a, fy=scale_a, interpolation=cv2.INTER_AREA)
    small_b = cv2.resize(img_b, None, fx=scale_b, fy=scale_b, interpolation=cv2.INTER_AREA)

    gray_a = _convert_to_grayscale(small_a)
    gray_b = _convert_to_grayscale(small_b)

    del small_a, small_b
    gc.collect()

    # Extract features
    kp_a, desc_a = extract_sift_features(
        gray_a, n_features=n_features, exclude_margin=0.1, contrast_threshold=contrast_threshold
    )
    kp_b, desc_b = extract_sift_features(
        gray_b, n_features=n_features, exclude_margin=0.1, contrast_threshold=contrast_threshold
    )

    if len(kp_a) < 10 or len(kp_b) < 10:
        raise RuntimeError(f"Insufficient SIFT features: a={len(kp_a)}, b={len(kp_b)}")

    # Match features
    matches = match_features(desc_a, desc_b, ratio_threshold=ratio_threshold)

    if len(matches) < 10:
        raise RuntimeError(f"Insufficient SIFT matches: {len(matches)}")

    # Convert to point arrays
    pts_a = np.array([kp_a[m.queryIdx].pt for m in matches], dtype=np.float32)
    pts_b = np.array([kp_b[m.trainIdx].pt for m in matches], dtype=np.float32)

    del gray_a, gray_b, kp_a, kp_b, desc_a, desc_b, matches
    gc.collect()

    # Run constrained estimation
    matrix, mask = _estimate_affine_constrained(
        pts_a,
        pts_b,
        ransac_threshold=ransac_threshold,
        max_iters=max_iters,
        scale_min=scale_min,
        scale_max=scale_max,
        rotation_deg_min=rotation_deg_min,
        rotation_deg_max=rotation_deg_max,
    )

    inlier_count = int(np.sum(mask))
    total_matches = len(pts_a)

    # Scale matrix back to full resolution
    # Matrix transforms small_a coords to small_b coords
    # Need to adjust for different scale factors
    matrix[:, :2] *= scale_a / scale_b  # Scale/rotation components
    matrix[:, 2] /= scale_b  # Translation components

    # Extract transformation parameters
    scale = np.sqrt(matrix[0, 0] ** 2 + matrix[1, 0] ** 2)
    rotation_deg = np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0]))
    tx, ty = matrix[0, 2], matrix[1, 2]

    # Apply transformation
    if expand_canvas:
        aligned_a, aligned_b, adjusted_matrix, offset_x, offset_y = _expand_canvas(
            img_a, img_b, matrix
        )
        output_w, output_h = aligned_a.shape[1], aligned_a.shape[0]
        final_matrix = adjusted_matrix
    else:
        output_w, output_h = w_b, h_b
        aligned_a = apply_transformation(img_a, matrix, output_shape=(output_w, output_h))
        aligned_b = img_b
        final_matrix = matrix
        offset_x, offset_y = 0.0, 0.0

    gc.collect()

    stats = AlignmentStats(
        method="sift",
        scale=scale,
        rotation_deg=rotation_deg,
        translate_x=tx,
        translate_y=ty,
        inlier_count=inlier_count,
        inlier_ratio=inlier_count / total_matches if total_matches > 0 else 0.0,
        expanded_width=output_w,
        expanded_height=output_h,
        offset_x=offset_x,
        offset_y=offset_y,
        matrix=final_matrix.tolist(),
    )

    return aligned_a, aligned_b, stats
