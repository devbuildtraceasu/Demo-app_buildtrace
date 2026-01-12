import cv2
import numpy as np


def segment_tight(image_path, output_path):
    """
    Two-pass segmentation:
    1. Aggressive dilation for detection (catches all features like 'final')
    2. Tight bounding box refinement using original content mask
    """
    print(f"Processing {image_path} tight...")

    img = cv2.imread(image_path)
    if img is None:
        return

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    h, w = img.shape[:2]

    # 1. Line Removal (Same as final - 50% threshold)
    h_kernel_len = int(w * 0.50)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)

    v_kernel_len = int(h * 0.50)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)

    lines = cv2.add(h_lines, v_lines)
    content = cv2.subtract(thresh, lines)  # Original content mask (keep for refinement)

    # 2. PASS 1: Aggressive Dilation for Detection (same as final)
    k_w = max(3, int(w * 0.015))
    k_h = max(3, int(h * 0.015))

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, 1))
    dilated_h = cv2.dilate(content, kernel_h, iterations=1)

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_h))
    dilated = cv2.dilate(dilated_h, kernel_v, iterations=3)

    # 3. Find Contours from dilated mask
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 4. Filter and Refine
    min_area = (w * h) * 0.001

    output_img = img.copy()
    regions = []

    for cnt in contours:
        # Get initial bounding box from dilated contour
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch

        if area > min_area:
            # PASS 2: Refine bounding box using original content
            # Extract the ROI from the original content mask
            roi = content[y : y + ch, x : x + cw]

            # Find actual content within this ROI
            roi_contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if roi_contours:
                # Get combined bounding box of all content in ROI
                all_points = np.vstack(roi_contours)
                rx, ry, rw, rh = cv2.boundingRect(all_points)

                # Convert back to image coordinates
                tight_x = x + rx
                tight_y = y + ry
                tight_w = rw
                tight_h = rh

                # Add small padding (0.5% of dimension) for visual clarity
                pad_x = max(3, int(tight_w * 0.02))
                pad_y = max(3, int(tight_h * 0.02))

                tight_x = max(0, tight_x - pad_x)
                tight_y = max(0, tight_y - pad_y)
                tight_w = min(w - tight_x, tight_w + 2 * pad_x)
                tight_h = min(h - tight_y, tight_h + 2 * pad_y)

                cv2.rectangle(
                    output_img,
                    (tight_x, tight_y),
                    (tight_x + tight_w, tight_y + tight_h),
                    (0, 0, 255),
                    3,
                )
                regions.append((tight_w * tight_h, tight_x, tight_y, tight_w, tight_h))

    regions.sort(key=lambda x: x[0], reverse=True)

    cv2.imwrite(output_path, output_img)
    print(f"Saved result to {output_path}")
    print(f"Found {len(regions)} regions.")
    for i, r in enumerate(regions):
        print(f"Region {i + 1}: {r[0]} px at ({r[1]}, {r[2]}) - {r[3]}x{r[4]}")


if __name__ == "__main__":
    pass
