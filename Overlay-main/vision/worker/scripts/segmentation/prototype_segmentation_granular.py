import cv2


def segment_granular(image_path, output_path):
    print(f"Processing {image_path} granular...")

    img = cv2.imread(image_path)
    if img is None:
        return

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    h, w = img.shape[:2]

    # 1. Conservative Line Removal (from refined_v2)
    # Remove lines > 80% of dimension (only borders)
    h_kernel_len = int(w * 0.80)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)

    v_kernel_len = int(h * 0.80)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)

    lines = cv2.add(h_lines, v_lines)
    content = cv2.subtract(thresh, lines)

    # 2. Minimal Dilation (Granular)
    # 0.1% kernel to keep almost everything separate
    k_w = max(1, int(w * 0.001))  # 0.1%
    k_h = max(1, int(h * 0.001))  # 0.1%

    # Symmetric dilation
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, k_h))
    dilated = cv2.dilate(content, kernel, iterations=1)

    # 3. Find Contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 4. No Filtering (or very minimal)
    # User requested to remove min_area filter
    min_area = 0

    output_img = img.copy()
    regions = []

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch

        if area > min_area:
            # Use a thinner line for granular boxes so they don't overlap visually
            cv2.rectangle(output_img, (x, y), (x + cw, y + ch), (0, 0, 255), 1)
            regions.append((area, x, y, cw, ch))

    regions.sort(key=lambda x: x[0], reverse=True)

    cv2.imwrite(output_path, output_img)
    print(f"Saved result to {output_path}")
    print(f"Found {len(regions)} regions.")


if __name__ == "__main__":
    pass
