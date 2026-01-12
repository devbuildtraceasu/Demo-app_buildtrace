import cv2


def segment_refined_v3(image_path, output_path):
    print(f"Processing {image_path} refined v3...")

    img = cv2.imread(image_path)
    if img is None:
        return

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    h, w = img.shape[:2]

    # 1. Aggressive Line Removal (Remove Table Grids)
    # Remove lines > 5% of dimension
    h_kernel_len = int(w * 0.05)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)

    v_kernel_len = int(h * 0.05)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)

    lines = cv2.add(h_lines, v_lines)
    content = cv2.subtract(thresh, lines)

    # 2. Dilation
    # Now that grids are gone, we need to merge the text content back into blocks
    # 1.0% kernel
    k_w = max(3, int(w * 0.010))
    k_h = max(3, int(h * 0.010))

    # Symmetric dilation to merge text paragraphs
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, k_h))
    dilated = cv2.dilate(content, kernel, iterations=3)

    # 3. Find Contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 4. Filter
    min_area = (w * h) * 0.006

    output_img = img.copy()
    regions = []

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch

        if area > min_area:
            cv2.rectangle(output_img, (x, y), (x + cw, y + ch), (0, 0, 255), 3)
            regions.append((area, x, y, cw, ch))

    regions.sort(key=lambda x: x[0], reverse=True)

    cv2.imwrite(output_path, output_img)
    print(f"Saved result to {output_path}")
    print(f"Found {len(regions)} regions.")


if __name__ == "__main__":
    pass
