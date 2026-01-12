import cv2


def segment_refined(image_path, output_path):
    print(f"Processing {image_path} refined...")

    img = cv2.imread(image_path)
    if img is None:
        return

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    h, w = img.shape[:2]

    # 1. Line Removal (Only Long Lines > 50%)
    h_kernel_len = int(w * 0.50)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)

    v_kernel_len = int(h * 0.50)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)

    lines = cv2.add(h_lines, v_lines)
    content = cv2.subtract(thresh, lines)

    # 2. Refined Asymmetric Dilation
    # Previous: 1.5% kernel, V=3 iter, H=1 iter
    # New: 1.0% kernel, V=2 iter, H=1 iter
    # This reduces the merge radius to avoid merging stacked details

    k_w = max(3, int(w * 0.010))  # Reduced from 0.015
    k_h = max(3, int(h * 0.010))  # Reduced from 0.015

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, 1))
    dilated_h = cv2.dilate(content, kernel_h, iterations=1)

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_h))
    dilated = cv2.dilate(dilated_h, kernel_v, iterations=2)  # Reduced from 3

    # 3. Find Contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 4. Filter
    # Keep threshold 0.6%
    min_area = (w * h) * 0.001

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
    # Test on one of the problematic images if possible, but we'll use the evaluator
    pass
