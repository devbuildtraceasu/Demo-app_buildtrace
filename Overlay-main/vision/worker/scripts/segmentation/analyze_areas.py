import os

import cv2


def analyze_areas(image_path):
    print(f"Analyzing {image_path}...")
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    total_area = h * w

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # Use the "Original" kernel that worked well for the big blocks
    k_w = max(3, int(w * 0.01))
    k_h = max(3, int(h * 0.01))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, k_h))
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        percent = (area / total_area) * 100
        regions.append((percent, area, x, y, cw, ch))

    # Sort by size descending
    regions.sort(key=lambda x: x[0], reverse=True)

    print(f"Total Image Area: {total_area} pixels")
    print("Found regions (Top 20):")
    for i, r in enumerate(regions[:20]):
        print(f"Region {i + 1}: {r[0]:.4f}% area ({r[1]} px) at ({r[2]}, {r[3]}) - {r[4]}x{r[5]}")


if __name__ == "__main__":
    base_dir = "/Users/kevin/.gemini/antigravity/brain/f5b5cbf7-3baf-455e-ba82-883d315a99ec"
    img_name = "uploaded_image_0_1763839754550.png"
    analyze_areas(os.path.join(base_dir, img_name))
