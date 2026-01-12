"""
Polygon-based segmentation using cv2.approxPolyDP for tighter region isolation.

Instead of rectangular bounding boxes, this extracts polygon contours that
follow the actual shape of content regions, reducing wasted whitespace and
preventing unrelated regions from being merged.
"""

import os
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PolygonRegion:
    """Represents a detected region as a polygon."""

    polygon: np.ndarray  # Shape (N, 1, 2) - OpenCV contour format
    bounding_box: tuple[int, int, int, int]  # (x, y, w, h)
    area: float  # Actual polygon area
    centroid: tuple[int, int]  # (cx, cy)

    @property
    def bbox_area(self) -> int:
        return self.bounding_box[2] * self.bounding_box[3]

    @property
    def fill_ratio(self) -> float:
        """Ratio of polygon area to bounding box area (1.0 = rectangle)."""
        return self.area / self.bbox_area if self.bbox_area > 0 else 0


def compute_centroid(contour: np.ndarray) -> tuple[int, int]:
    """Compute centroid of a contour using moments."""
    M = cv2.moments(contour)
    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
    else:
        # Fallback to bounding box center
        x, y, w, h = cv2.boundingRect(contour)
        cx, cy = x + w // 2, y + h // 2
    return (cx, cy)


def extract_polygon_regions(
    image_path: str, epsilon_factor: float = 0.005, min_area_ratio: float = 0.001
) -> tuple[list[PolygonRegion], np.ndarray]:
    """
    Extract polygon regions from an image using approximate polygon simplification.

    Args:
        image_path: Path to input image
        epsilon_factor: Controls polygon simplification (0.005 = 0.5% of perimeter)
                       Lower = more points, tighter fit
                       Higher = fewer points, more simplified
        min_area_ratio: Minimum region area as ratio of image area

    Returns:
        Tuple of (list of PolygonRegion, content mask for reference)
    """
    img = cv2.imread(image_path)
    if img is None:
        return [], None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    h, w = img.shape[:2]

    # 1. Line Removal (50% threshold for very long lines only)
    h_kernel_len = int(w * 0.50)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)

    v_kernel_len = int(h * 0.50)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)

    lines = cv2.add(h_lines, v_lines)
    content = cv2.subtract(thresh, lines)

    # 2. Dilation to group nearby content (same as tight version)
    k_w = max(3, int(w * 0.015))
    k_h = max(3, int(h * 0.015))

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, 1))
    dilated_h = cv2.dilate(content, kernel_h, iterations=1)

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_h))
    dilated = cv2.dilate(dilated_h, kernel_v, iterations=3)

    # 3. Find contours from dilated mask
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 4. Filter and convert to polygon regions
    min_area = (w * h) * min_area_ratio
    regions = []

    for cnt in contours:
        # Get bounding box for initial filtering
        x, y, cw, ch = cv2.boundingRect(cnt)
        bbox_area = cw * ch

        if bbox_area < min_area:
            continue

        # Refine using original content mask (same as tight)
        roi = content[y : y + ch, x : x + cw]
        roi_contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not roi_contours:
            continue

        # Use the DILATED contour directly (not the fine-grained ROI contours)
        # This preserves the concave shape created by dilation-based grouping
        # Extract the portion of the dilated mask for this region
        dilated_roi = dilated[y : y + ch, x : x + cw]
        dilated_contours, _ = cv2.findContours(
            dilated_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not dilated_contours:
            continue

        # Take the largest dilated contour (should be the grouped region)
        largest_dilated = max(dilated_contours, key=cv2.contourArea)

        # Apply polygon approximation for simplification
        perimeter = cv2.arcLength(largest_dilated, True)
        epsilon = epsilon_factor * perimeter
        approx_poly = cv2.approxPolyDP(largest_dilated, epsilon, True)

        # Offset polygon back to image coordinates
        approx_poly_global = approx_poly.copy()
        approx_poly_global[:, 0, 0] += x
        approx_poly_global[:, 0, 1] += y

        # Compute polygon properties
        poly_area = cv2.contourArea(approx_poly_global)
        if poly_area < min_area:
            continue

        bbox = cv2.boundingRect(approx_poly_global)
        centroid = compute_centroid(approx_poly_global)

        region = PolygonRegion(
            polygon=approx_poly_global, bounding_box=bbox, area=poly_area, centroid=centroid
        )
        regions.append(region)

    # Sort by area (largest first)
    regions.sort(key=lambda r: r.area, reverse=True)

    return regions, content


def segment_polygon(image_path: str, output_path: str, epsilon_factor: float = 0.005):
    """
    Main segmentation function with polygon visualization.

    Args:
        image_path: Input image path
        output_path: Output image path
        epsilon_factor: Polygon simplification factor (default 0.005 = 0.5% of perimeter)
    """
    print(f"Processing {image_path} polygon (epsilon={epsilon_factor})...")

    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read {image_path}")
        return []

    regions, _ = extract_polygon_regions(image_path, epsilon_factor=epsilon_factor)

    if not regions:
        print("No regions found")
        return []

    output_img = img.copy()

    # Colors for visualization
    poly_color = (0, 0, 255)  # Red for polygon outline
    fill_color = (0, 0, 255, 50)  # Semi-transparent red fill
    bbox_color = (255, 200, 0)  # Cyan for bounding box (for comparison)

    for i, region in enumerate(regions):
        # Draw filled polygon with transparency
        overlay = output_img.copy()
        cv2.fillPoly(overlay, [region.polygon], poly_color)
        cv2.addWeighted(overlay, 0.15, output_img, 0.85, 0, output_img)

        # Draw polygon outline (thick)
        cv2.polylines(output_img, [region.polygon], True, poly_color, 3)

        # Draw bounding box (thin, dashed effect via short segments)
        x, y, w, h = region.bounding_box
        cv2.rectangle(output_img, (x, y), (x + w, y + h), bbox_color, 1)

        # Draw centroid
        cx, cy = region.centroid
        cv2.circle(output_img, (cx, cy), 5, (0, 255, 0), -1)

        # Label with region info
        label = f"R{i + 1}: {region.polygon.shape[0]}pts, fill={region.fill_ratio:.1%}"
        cv2.putText(output_img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, poly_color, 2)

    cv2.imwrite(output_path, output_img)
    print(f"Saved result to {output_path}")
    print(f"Found {len(regions)} polygon regions:")

    for i, r in enumerate(regions):
        print(f"  Region {i + 1}:")
        print(f"    Polygon: {r.polygon.shape[0]} vertices")
        print(
            f"    BBox: ({r.bounding_box[0]}, {r.bounding_box[1]}) - {r.bounding_box[2]}x{r.bounding_box[3]}"
        )
        print(f"    Area: {r.area:.0f} px (bbox: {r.bbox_area} px)")
        print(f"    Fill ratio: {r.fill_ratio:.1%}")
        print(f"    Centroid: {r.centroid}")

    return regions


def create_masked_crop(
    image: np.ndarray,
    region: PolygonRegion,
    background_color: tuple[int, int, int] = (255, 255, 255),
) -> np.ndarray:
    """
    Create a cropped image with only the polygon region visible.
    Areas outside the polygon are filled with background_color.

    Args:
        image: Source image
        region: PolygonRegion to extract
        background_color: Color for areas outside polygon (default white)

    Returns:
        Cropped image with masked content
    """
    h, w = image.shape[:2]

    # Create mask from polygon
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [region.polygon], 255)

    # Create output with background color
    result = np.full_like(image, background_color)

    # Copy only masked region
    result[mask == 255] = image[mask == 255]

    # Crop to bounding box
    x, y, bw, bh = region.bounding_box

    # Add small padding
    pad = 5
    x = max(0, x - pad)
    y = max(0, y - pad)
    bw = min(w - x, bw + 2 * pad)
    bh = min(h - y, bh + 2 * pad)

    cropped = result[y : y + bh, x : x + bw]

    return cropped


if __name__ == "__main__":
    # Test on dataset images
    base_dir = "/Users/kevin/Documents/deprecated/odin/apps/vision/worker/scripts/segmentation"
    dataset_dir = os.path.join(base_dir, "dataset")
    output_dir = os.path.join(base_dir, "predicted")

    # Test on page_0_addition
    test_image = os.path.join(dataset_dir, "page_0_addition.png")
    if os.path.exists(test_image):
        output_path = os.path.join(output_dir, "page_0_addition_polygon.png")
        regions = segment_polygon(test_image, output_path)
