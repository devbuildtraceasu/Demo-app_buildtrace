import os

import cv2


def segment_final(image_path, output_path):
    print(f"Processing {image_path} final...")

    img = cv2.imread(image_path)
    if img is None:
        return

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # 1. Line Removal (Only Long Lines > 50%)
    h, w = img.shape[:2]
    h_kernel_len = int(w * 0.50)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)

    v_kernel_len = int(h * 0.50)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)

    lines = cv2.add(h_lines, v_lines)
    content = cv2.subtract(thresh, lines)

    # 2. Asymmetric Dilation
    # H: 1.5% (1 iter) - Keep plans separate
    # V: 1.5% (3 iter) - Merge text blocks
    k_w = max(3, int(w * 0.015))
    k_h = max(3, int(h * 0.015))

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, 1))
    dilated_h = cv2.dilate(content, kernel_h, iterations=1)

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_h))
    dilated = cv2.dilate(dilated_h, kernel_v, iterations=3)

    # 3. Find Contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 4. Filter
    # Threshold 0.6% to get top 5
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
    for i, r in enumerate(regions):
        print(f"Region {i + 1}: {r[0]} px at ({r[1]}, {r[2]}) - {r[3]}x{r[4]}")


if __name__ == "__main__":
    base_dir = "/Users/kevin/.gemini/antigravity/brain/f5b5cbf7-3baf-455e-ba82-883d315a99ec"
    img_name = "uploaded_image_0_1763839754550.png"
    segment_final(os.path.join(base_dir, img_name), os.path.join(base_dir, "seg_final.png"))
