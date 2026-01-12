"""
Grid-Based Image Alignment Script

Aligns two construction drawings using architectural grid lines and callout labels.
Produces intermediate visualizations for debugging and validation.

Usage:
    python grid_align.py --old dataset/old.png --new dataset/new.png

Outputs:
    outputs/aligned_old.png - Old image transformed to align with new
    outputs/aligned_new.png - New image on same canvas
    intermediates/01_*.png - Grid line detection visualizations
    intermediates/02_*.png - Callout detection visualizations
    intermediates/03_*.png - Label association visualizations
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# Increase PIL's decompression bomb limit for large construction drawings
Image.MAX_IMAGE_PIXELS = 250_000_000

# Script directories
SCRIPT_DIR = Path(__file__).parent
DATASET_DIR = SCRIPT_DIR / "dataset"
OUTPUT_DIR = SCRIPT_DIR / "outputs"
INTERMEDIATE_DIR = SCRIPT_DIR / "intermediates"

# Colors for visualization (BGR format for OpenCV)
COLORS = {
    "horizontal": (255, 0, 0),  # Blue for horizontal grid lines
    "vertical": (0, 255, 0),  # Green for vertical grid lines
    "circle": (0, 255, 255),  # Yellow for detected circles
    "callout": (255, 0, 255),  # Magenta for validated callouts
    "label": (0, 165, 255),  # Orange for labels
    "match": (0, 255, 0),  # Green for matched grids
}


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class GridLine:
    """A detected grid line."""

    position: float  # Y for horizontal, X for vertical
    orientation: str  # 'horizontal' or 'vertical'
    extent_start: float  # Start of line extent
    extent_end: float  # End of line extent
    segments: list = field(default_factory=list)  # Original line segments
    label: str | None = None
    confidence: float = 0.0


@dataclass
class Callout:
    """A detected circular callout."""

    center: tuple[int, int]
    radius: int
    edge_region: list[str]  # 'left', 'right', 'top', 'bottom'
    label: str | None = None
    confidence: float = 0.0
    associated_line: GridLine | None = None


@dataclass
class GridSystem:
    """Complete detected grid system."""

    horizontal_grids: list[GridLine]
    vertical_grids: list[GridLine]
    image_width: int
    image_height: int
    rotation_angle: float = 0.0


# =============================================================================
# Image I/O
# =============================================================================


def load_image(path: Path) -> np.ndarray:
    """Load image as RGB numpy array."""
    print(f"Loading {path}...")
    img = Image.open(path)
    img_rgb = img.convert("RGB")
    return np.array(img_rgb, dtype=np.uint8)


def save_image(img: np.ndarray, path: Path, is_bgr: bool = False) -> None:
    """Save image to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if is_bgr:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img, mode="RGB")
    pil_img.save(path)
    print(f"  Saved: {path}")


# =============================================================================
# Phase 1: Rotation Detection
# =============================================================================


def detect_rotation_angle(
    gray: np.ndarray, visualize: bool = True
) -> tuple[float, np.ndarray | None]:
    """
    Detect the rotation angle of the drawing from dominant line orientations.

    Returns:
        (angle_degrees, visualization_image)
    """
    print("\n[Phase 1] Detecting rotation angle...")

    # Edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Use standard Hough Transform to get line angles
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=200)

    if lines is None:
        print("  No lines detected for rotation estimation")
        return 0.0, None

    # Collect angles
    angles = []
    for line in lines:
        rho, theta = line[0]
        angle_deg = np.degrees(theta)
        # Normalize to [-45, 45] range (we expect near 0 or 90)
        if angle_deg > 45:
            angle_deg -= 90
        if angle_deg < -45:
            angle_deg += 90
        angles.append(angle_deg)

    # Find dominant angle near 0 (horizontal lines) or 90 (vertical lines)
    # Filter to angles within 10 degrees of horizontal
    horizontal_angles = [a for a in angles if abs(a) < 10]

    if horizontal_angles:
        rotation = np.median(horizontal_angles)
    else:
        rotation = 0.0

    print(f"  Detected rotation: {rotation:.2f} degrees")
    print(f"  Total lines analyzed: {len(lines)}")

    # Visualization
    vis = None
    if visualize:
        vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        for line in lines[:100]:  # Draw first 100 lines
            rho, theta = line[0]
            a = np.cos(theta)
            b = np.sin(theta)
            x0 = a * rho
            y0 = b * rho
            x1 = int(x0 + 3000 * (-b))
            y1 = int(y0 + 3000 * (a))
            x2 = int(x0 - 3000 * (-b))
            y2 = int(y0 - 3000 * (a))
            cv2.line(vis, (x1, y1), (x2, y2), (0, 0, 255), 1)

        # Add text
        cv2.putText(
            vis,
            f"Rotation: {rotation:.2f} deg",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )

    return rotation, vis


def rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotate image by given angle (degrees) around center."""
    if abs(angle) < 0.1:
        return image.copy()

    h, w = image.shape[:2]
    center = (w / 2, h / 2)

    # Get rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # Calculate new image size to contain rotated image
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)

    # Adjust rotation matrix for new size
    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2

    # Apply rotation
    rotated = cv2.warpAffine(
        image, M, (new_w, new_h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255)
    )
    return rotated


# =============================================================================
# Phase 2: Grid Line Detection
# =============================================================================


def preprocess_for_grid_detection(gray: np.ndarray) -> np.ndarray:
    """Preprocess image for line detection."""
    # Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Adaptive threshold for varying line weights
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, blockSize=11, C=2
    )
    return binary


def detect_line_segments(binary: np.ndarray) -> list:
    """
    Detect line segments using Probabilistic Hough Transform.
    Parameters tuned for dashed/dotted grid lines.
    """
    lines = cv2.HoughLinesP(
        binary,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=30,  # Short to catch dash segments
        maxLineGap=20,  # Moderate gap tolerance
    )
    return lines if lines is not None else []


def classify_line_segments(lines: list, angle_tolerance_deg: float = 5.0) -> tuple[list, list]:
    """Classify line segments as horizontal or vertical."""
    horizontal = []
    vertical = []

    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))

        # Horizontal: angle near 0 or 180
        if abs(angle) < angle_tolerance_deg or abs(abs(angle) - 180) < angle_tolerance_deg:
            horizontal.append((x1, y1, x2, y2))
        # Vertical: angle near 90 or -90
        elif abs(abs(angle) - 90) < angle_tolerance_deg:
            vertical.append((x1, y1, x2, y2))

    return horizontal, vertical


def cluster_segments_into_grid_lines(
    segments: list,
    is_horizontal: bool,
    position_tolerance: int = 15,
    min_total_length_ratio: float = 0.25,
    image_dimension: int = 1000,
) -> list[GridLine]:
    """
    Cluster collinear segments into grid lines.

    For horizontal segments: cluster by y-coordinate
    For vertical segments: cluster by x-coordinate
    """
    if not segments:
        return []

    # Extract position (y for horizontal, x for vertical)
    if is_horizontal:
        positions = [(s, (s[1] + s[3]) / 2) for s in segments]
    else:
        positions = [(s, (s[0] + s[2]) / 2) for s in segments]

    # Sort by position
    positions.sort(key=lambda x: x[1])

    # Cluster using simple grouping
    clusters = []
    current_cluster = [positions[0][0]]
    current_pos = positions[0][1]

    for seg, pos in positions[1:]:
        if abs(pos - current_pos) <= position_tolerance:
            current_cluster.append(seg)
            # Update position as running average
            current_pos = (current_pos * (len(current_cluster) - 1) + pos) / len(current_cluster)
        else:
            clusters.append((current_cluster, current_pos))
            current_cluster = [seg]
            current_pos = pos
    clusters.append((current_cluster, current_pos))

    # Filter clusters by total length
    min_length = image_dimension * min_total_length_ratio
    grid_lines = []

    for cluster, avg_pos in clusters:
        # Calculate total length
        total_length = sum(np.sqrt((s[2] - s[0]) ** 2 + (s[3] - s[1]) ** 2) for s in cluster)

        if total_length >= min_length:
            if is_horizontal:
                min_x = min(min(s[0], s[2]) for s in cluster)
                max_x = max(max(s[0], s[2]) for s in cluster)
                grid_lines.append(
                    GridLine(
                        position=avg_pos,
                        orientation="horizontal",
                        extent_start=min_x,
                        extent_end=max_x,
                        segments=cluster,
                    )
                )
            else:
                min_y = min(min(s[1], s[3]) for s in cluster)
                max_y = max(max(s[1], s[3]) for s in cluster)
                grid_lines.append(
                    GridLine(
                        position=avg_pos,
                        orientation="vertical",
                        extent_start=min_y,
                        extent_end=max_y,
                        segments=cluster,
                    )
                )

    return grid_lines


def validate_grid_lines(
    grid_lines: list[GridLine],
    image_width: int,
    image_height: int,
    min_span_ratio: float = 0.3,
    edge_margin_ratio: float = 0.15,
) -> list[GridLine]:
    """Filter to only valid grid lines that span enough and reach edges."""
    valid = []

    for line in grid_lines:
        if line.orientation == "horizontal":
            span = line.extent_end - line.extent_start
            if span < image_width * min_span_ratio:
                continue
            # Check if reaches near left or right edge
            edge_margin = image_width * edge_margin_ratio
            reaches_edge = (
                line.extent_start < edge_margin or line.extent_end > image_width - edge_margin
            )
            if reaches_edge:
                valid.append(line)
        else:
            span = line.extent_end - line.extent_start
            if span < image_height * min_span_ratio:
                continue
            edge_margin = image_height * edge_margin_ratio
            reaches_edge = (
                line.extent_start < edge_margin or line.extent_end > image_height - edge_margin
            )
            if reaches_edge:
                valid.append(line)

    return valid


def visualize_grid_lines(
    image: np.ndarray,
    horizontal_segments: list,
    vertical_segments: list,
    grid_lines: list[GridLine],
    title: str = "",
) -> np.ndarray:
    """Create visualization of detected grid lines."""
    vis = image.copy()
    if len(vis.shape) == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    # Draw all segments (thin, semi-transparent)
    for seg in horizontal_segments:
        cv2.line(vis, (seg[0], seg[1]), (seg[2], seg[3]), (200, 200, 0), 1)
    for seg in vertical_segments:
        cv2.line(vis, (seg[0], seg[1]), (seg[2], seg[3]), (0, 200, 200), 1)

    # Draw validated grid lines (thick)
    for line in grid_lines:
        color = COLORS[line.orientation]
        if line.orientation == "horizontal":
            y = int(line.position)
            cv2.line(vis, (int(line.extent_start), y), (int(line.extent_end), y), color, 3)
            # Add position label
            cv2.putText(
                vis,
                f"y={y}",
                (int(line.extent_start) + 10, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )
        else:
            x = int(line.position)
            cv2.line(vis, (x, int(line.extent_start)), (x, int(line.extent_end)), color, 3)
            cv2.putText(
                vis,
                f"x={x}",
                (x + 10, int(line.extent_start) + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

    # Add title and stats
    h_count = sum(1 for l in grid_lines if l.orientation == "horizontal")
    v_count = sum(1 for l in grid_lines if l.orientation == "vertical")
    cv2.putText(
        vis,
        f"{title} - H:{h_count} V:{v_count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
    )

    return vis


# =============================================================================
# Phase 3: Callout Detection
# =============================================================================


def detect_callout_circles(
    gray: np.ndarray, min_radius: int = 20, max_radius: int = 80, edge_region_ratio: float = 0.12
) -> list[Callout]:
    """Detect circular callout bubbles at image edges."""
    h, w = gray.shape

    # Apply blur for circle detection
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Detect circles
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_radius * 2,
        param1=100,
        param2=30,
        minRadius=min_radius,
        maxRadius=max_radius,
    )

    if circles is None:
        return []

    circles = np.uint16(np.around(circles[0]))

    # Filter to edge regions
    edge_margin = int(min(w, h) * edge_region_ratio)
    callouts = []

    for x, y, r in circles:
        edge_regions = []
        if x < edge_margin:
            edge_regions.append("left")
        if x > w - edge_margin:
            edge_regions.append("right")
        if y < edge_margin:
            edge_regions.append("top")
        if y > h - edge_margin:
            edge_regions.append("bottom")

        if edge_regions:
            callouts.append(
                Callout(center=(int(x), int(y)), radius=int(r), edge_region=edge_regions)
            )

    return callouts


def filter_grid_lines_by_callouts(
    grid_lines: list[GridLine], callouts: list[Callout], tolerance: int = 40
) -> tuple[list[GridLine], list[GridLine]]:
    """
    Filter grid lines to only those passing through callout centers.

    A grid line is valid if it passes within `tolerance` pixels of at least
    one callout center.

    Args:
        grid_lines: Candidate grid lines
        callouts: Detected callout circles
        tolerance: Max distance from callout center to line (pixels)

    Returns:
        (valid_lines, rejected_lines)
    """
    valid = []
    rejected = []

    for line in grid_lines:
        passes_through_callout = False
        associated_callouts = []

        for callout in callouts:
            cx, cy = callout.center

            if line.orientation == "horizontal":
                # For horizontal line, check if callout center y is close to line y
                if abs(cy - line.position) <= tolerance:
                    # Also check callout is within line's x extent (with some margin)
                    if line.extent_start - tolerance <= cx <= line.extent_end + tolerance:
                        passes_through_callout = True
                        associated_callouts.append(callout)
            else:  # vertical
                # For vertical line, check if callout center x is close to line x
                if abs(cx - line.position) <= tolerance:
                    # Also check callout is within line's y extent (with some margin)
                    if line.extent_start - tolerance <= cy <= line.extent_end + tolerance:
                        passes_through_callout = True
                        associated_callouts.append(callout)

        if passes_through_callout:
            # Associate callouts with this line
            for callout in associated_callouts:
                callout.associated_line = line
            valid.append(line)
        else:
            rejected.append(line)

    return valid, rejected


def filter_callouts_near_grid_lines(
    callouts: list[Callout], grid_lines: list[GridLine], max_distance: int = 80
) -> list[Callout]:
    """Filter callouts to only those near grid line endpoints."""
    filtered = []

    for callout in callouts:
        cx, cy = callout.center

        for line in grid_lines:
            if line.orientation == "horizontal":
                # Check if callout is on this horizontal line
                if abs(cy - line.position) > max_distance:
                    continue
                # Check if near left or right end
                if cx < line.extent_start + max_distance or cx > line.extent_end - max_distance:
                    callout.associated_line = line
                    filtered.append(callout)
                    break
            else:  # vertical
                if abs(cx - line.position) > max_distance:
                    continue
                if cy < line.extent_start + max_distance or cy > line.extent_end - max_distance:
                    callout.associated_line = line
                    filtered.append(callout)
                    break

    return filtered


def visualize_callouts(
    image: np.ndarray, all_circles: list[Callout], filtered_callouts: list[Callout], title: str = ""
) -> np.ndarray:
    """Create visualization of detected callouts."""
    vis = image.copy()
    if len(vis.shape) == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    # Draw all detected circles (thin yellow)
    for c in all_circles:
        cv2.circle(vis, c.center, c.radius, COLORS["circle"], 2)

    # Draw filtered callouts (thick magenta)
    for c in filtered_callouts:
        cv2.circle(vis, c.center, c.radius, COLORS["callout"], 3)
        # Draw center point
        cv2.circle(vis, c.center, 3, COLORS["callout"], -1)
        # Add edge region label
        label = ",".join(c.edge_region)
        cv2.putText(
            vis,
            label,
            (c.center[0] - 20, c.center[1] - c.radius - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            COLORS["callout"],
            1,
        )

    # Add title
    cv2.putText(
        vis,
        f"{title} - All:{len(all_circles)} Filtered:{len(filtered_callouts)}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
    )

    return vis


def visualize_grid_lines_filtered(
    image: np.ndarray,
    valid_lines: list[GridLine],
    rejected_lines: list[GridLine],
    callouts: list[Callout],
    title: str = "",
) -> np.ndarray:
    """
    Visualize grid lines after filtering by callouts.

    Shows:
    - Valid lines (thick, colored by orientation)
    - Rejected lines (thin, red/dashed appearance)
    - Callout circles with center dots
    """
    vis = image.copy()
    if len(vis.shape) == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    # Draw rejected lines first (thin, red)
    for line in rejected_lines:
        if line.orientation == "horizontal":
            y = int(line.position)
            cv2.line(
                vis, (int(line.extent_start), y), (int(line.extent_end), y), (0, 0, 180), 1
            )  # Dark red, thin
        else:
            x = int(line.position)
            cv2.line(
                vis, (x, int(line.extent_start)), (x, int(line.extent_end)), (0, 0, 180), 1
            )  # Dark red, thin

    # Draw valid lines (thick, colored)
    for line in valid_lines:
        color = COLORS[line.orientation]
        if line.orientation == "horizontal":
            y = int(line.position)
            cv2.line(vis, (int(line.extent_start), y), (int(line.extent_end), y), color, 3)
            cv2.putText(
                vis,
                f"y={y}",
                (int(line.extent_start) + 10, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )
        else:
            x = int(line.position)
            cv2.line(vis, (x, int(line.extent_start)), (x, int(line.extent_end)), color, 3)
            cv2.putText(
                vis,
                f"x={x}",
                (x + 10, int(line.extent_start) + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

    # Draw callout circles and centers
    for c in callouts:
        cv2.circle(vis, c.center, c.radius, COLORS["callout"], 2)
        cv2.circle(vis, c.center, 5, COLORS["callout"], -1)  # Center dot

    # Stats
    h_valid = sum(1 for l in valid_lines if l.orientation == "horizontal")
    v_valid = sum(1 for l in valid_lines if l.orientation == "vertical")
    h_rejected = sum(1 for l in rejected_lines if l.orientation == "horizontal")
    v_rejected = sum(1 for l in rejected_lines if l.orientation == "vertical")

    cv2.putText(vis, f"{title}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(
        vis,
        f"Valid: H={h_valid} V={v_valid} | Rejected: H={h_rejected} V={v_rejected}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )

    return vis


# =============================================================================
# Phase 4: OCR for Labels
# =============================================================================


def extract_callout_region(image: np.ndarray, callout: Callout, padding: int = 5) -> np.ndarray:
    """Extract the circular region containing the label."""
    cx, cy = callout.center
    r = callout.radius

    h, w = image.shape[:2]

    # Crop bounding box with padding
    x1 = max(0, cx - r - padding)
    y1 = max(0, cy - r - padding)
    x2 = min(w, cx + r + padding)
    y2 = min(h, cy + r + padding)

    return image[y1:y2, x1:x2].copy()


def extract_label_simple(callout_region: np.ndarray) -> tuple[str | None, float]:
    """
    Simple label extraction using template matching or basic OCR.

    For now, returns None - we'll add OCR in next iteration.
    This placeholder allows testing the pipeline.
    """
    # TODO: Implement OCR using pytesseract or vision LLM
    # For now, return None to test the visualization pipeline
    _ = callout_region  # Placeholder - will be used for OCR
    return None, 0.0


def visualize_labels(
    image: np.ndarray, callouts: list[Callout], grid_lines: list[GridLine], title: str = ""
) -> np.ndarray:
    """Create visualization with labels on grid lines."""
    vis = image.copy()
    if len(vis.shape) == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    # Draw grid lines with labels
    for line in grid_lines:
        color = COLORS[line.orientation]
        if line.orientation == "horizontal":
            y = int(line.position)
            cv2.line(vis, (int(line.extent_start), y), (int(line.extent_end), y), color, 2)
            if line.label:
                cv2.putText(
                    vis,
                    f"[{line.label}]",
                    (int(line.extent_end) + 10, y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    COLORS["label"],
                    2,
                )
        else:
            x = int(line.position)
            cv2.line(vis, (x, int(line.extent_start)), (x, int(line.extent_end)), color, 2)
            if line.label:
                cv2.putText(
                    vis,
                    f"[{line.label}]",
                    (x - 15, int(line.extent_start) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    COLORS["label"],
                    2,
                )

    # Draw callouts with their extracted labels
    for c in callouts:
        cv2.circle(vis, c.center, c.radius, COLORS["callout"], 2)
        if c.label:
            cv2.putText(
                vis,
                c.label,
                (c.center[0] - 10, c.center[1] + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
            )

    cv2.putText(vis, title, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    return vis


# =============================================================================
# Main Pipeline
# =============================================================================


def detect_grid_system(image: np.ndarray, name: str = "image") -> tuple[GridSystem, dict]:
    """
    Main function to detect grid system in a construction drawing.

    Returns:
        (GridSystem, visualizations_dict)
    """
    visualizations = {}
    h, w = image.shape[:2]
    rotation_angle = 0.0  # Rotation detection disabled for now

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    # Phase 1: Detect candidate grid lines
    print("\n[Phase 1] Detecting candidate grid lines...")
    binary = preprocess_for_grid_detection(gray)
    visualizations[f"01_binary_{name}"] = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    segments = detect_line_segments(binary)
    print(f"  Detected {len(segments)} line segments")

    h_segments, v_segments = classify_line_segments(segments)
    print(f"  Classified: {len(h_segments)} horizontal, {len(v_segments)} vertical")

    h_grid_lines = cluster_segments_into_grid_lines(h_segments, True, image_dimension=w)
    v_grid_lines = cluster_segments_into_grid_lines(v_segments, False, image_dimension=h)
    print(f"  Clustered: {len(h_grid_lines)} horizontal, {len(v_grid_lines)} vertical grid lines")

    # Basic validation (span + edge proximity)
    h_grid_lines = validate_grid_lines(h_grid_lines, w, h)
    v_grid_lines = validate_grid_lines(v_grid_lines, w, h)
    print(f"  After basic validation: {len(h_grid_lines)} horizontal, {len(v_grid_lines)} vertical")

    candidate_grid_lines = h_grid_lines + v_grid_lines

    # Visualization of candidates (before callout filtering)
    grid_vis = visualize_grid_lines(
        image, h_segments, v_segments, candidate_grid_lines, f"Candidate Grid Lines - {name}"
    )
    visualizations[f"02_candidates_{name}"] = grid_vis

    # Phase 2: Detect callout circles
    print("\n[Phase 2] Detecting callout circles...")
    all_callouts = detect_callout_circles(gray)
    print(f"  Detected {len(all_callouts)} circles at edges")

    callout_vis = visualize_callouts(image, all_callouts, all_callouts, f"All Callouts - {name}")
    visualizations[f"03_callouts_{name}"] = callout_vis

    # Phase 3: Filter grid lines by callouts
    # Only keep lines that pass through at least one callout center
    print("\n[Phase 3] Filtering grid lines by callout positions...")
    valid_grid_lines, rejected_lines = filter_grid_lines_by_callouts(
        candidate_grid_lines, all_callouts, tolerance=50
    )
    print(f"  Valid grid lines: {len(valid_grid_lines)} (rejected: {len(rejected_lines)})")

    # Separate valid lines by orientation
    h_grid_lines = [l for l in valid_grid_lines if l.orientation == "horizontal"]
    v_grid_lines = [l for l in valid_grid_lines if l.orientation == "vertical"]
    print(f"  Final: {len(h_grid_lines)} horizontal, {len(v_grid_lines)} vertical")

    # Get callouts associated with valid grid lines
    associated_callouts = [c for c in all_callouts if c.associated_line is not None]
    print(f"  Associated callouts: {len(associated_callouts)}")

    # Visualization of filtered grid lines
    filtered_vis = visualize_grid_lines_filtered(
        image,
        valid_grid_lines,
        rejected_lines,
        associated_callouts,
        f"Filtered Grid Lines - {name}",
    )
    visualizations[f"04_filtered_{name}"] = filtered_vis

    # Phase 4: OCR (placeholder for now)
    print("\n[Phase 4] Extracting labels...")
    for callout in associated_callouts:
        region = extract_callout_region(gray, callout)
        label, conf = extract_label_simple(region)
        callout.label = label
        callout.confidence = conf

        # Associate label with grid line
        if callout.associated_line and label:
            callout.associated_line.label = label

    # Label visualization
    label_vis = visualize_labels(image, associated_callouts, valid_grid_lines, f"Labels - {name}")
    visualizations[f"05_labels_{name}"] = label_vis

    # Create grid system
    grid_system = GridSystem(
        horizontal_grids=h_grid_lines,
        vertical_grids=v_grid_lines,
        image_width=w,
        image_height=h,
        rotation_angle=rotation_angle,
    )

    return grid_system, visualizations


def main():
    parser = argparse.ArgumentParser(description="Grid-based image alignment")
    parser.add_argument(
        "--old", default=str(DATASET_DIR / "architectural_2.png"), help="Path to old image"
    )
    parser.add_argument(
        "--new", default=str(DATASET_DIR / "architectural_shop_2.png"), help="Path to new image"
    )
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument(
        "--intermediate-dir", default=str(INTERMEDIATE_DIR), help="Intermediate outputs"
    )

    args = parser.parse_args()

    old_path = Path(args.old)
    new_path = Path(args.new)
    output_dir = Path(args.output_dir)
    intermediate_dir = Path(args.intermediate_dir)

    # Validate inputs
    if not old_path.exists():
        print(f"Error: Old image not found: {old_path}")
        sys.exit(1)
    if not new_path.exists():
        print(f"Error: New image not found: {new_path}")
        sys.exit(1)

    # Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Grid-Based Image Alignment")
    print("=" * 60)

    # Load images
    old_img = load_image(old_path)
    new_img = load_image(new_path)

    print(f"\nOld image: {old_img.shape}")
    print(f"New image: {new_img.shape}")

    # Detect grid systems
    print("\n" + "=" * 60)
    print("Processing OLD image")
    print("=" * 60)
    old_grid, old_vis = detect_grid_system(old_img, "old")

    print("\n" + "=" * 60)
    print("Processing NEW image")
    print("=" * 60)
    new_grid, new_vis = detect_grid_system(new_img, "new")

    # Save intermediate visualizations
    print("\n" + "=" * 60)
    print("Saving intermediate visualizations")
    print("=" * 60)

    for name, vis in {**old_vis, **new_vis}.items():
        save_image(vis, intermediate_dir / f"{name}.png", is_bgr=True)

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("\nOLD image grid system:")
    print(f"  Horizontal grids: {len(old_grid.horizontal_grids)}")
    for g in old_grid.horizontal_grids:
        print(f"    - y={g.position:.0f}, label={g.label}")
    print(f"  Vertical grids: {len(old_grid.vertical_grids)}")
    for g in old_grid.vertical_grids:
        print(f"    - x={g.position:.0f}, label={g.label}")

    print("\nNEW image grid system:")
    print(f"  Horizontal grids: {len(new_grid.horizontal_grids)}")
    for g in new_grid.horizontal_grids:
        print(f"    - y={g.position:.0f}, label={g.label}")
    print(f"  Vertical grids: {len(new_grid.vertical_grids)}")
    for g in new_grid.vertical_grids:
        print(f"    - x={g.position:.0f}, label={g.label}")

    print("\n" + "=" * 60)
    print(f"Intermediate outputs saved to: {intermediate_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
