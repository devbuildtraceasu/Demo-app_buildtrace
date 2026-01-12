import os
import re
from pathlib import Path

import cv2
import numpy as np
from prototype_gemini_proposal import propose_regions_gemini

# Import all versions


def normalize_for_match(name):
    """Remove all non-alphanumeric chars for loose matching"""
    stem = Path(name).stem
    if stem.endswith("_annotated"):
        stem = stem[:-10]
    return re.sub(r"[^a-zA-Z0-9]", "", stem).lower()


def create_comparison(original_path, predicted_path, annotated_path, output_path, label):
    """Create a side-by-side comparison of Predicted vs Annotated"""
    pred_img = cv2.imread(predicted_path)

    if os.path.exists(annotated_path):
        anno_img = cv2.imread(annotated_path)
    else:
        print(f"Annotated file not found at {annotated_path}")
        return

    # Resize to same width if needed
    h1, w1 = pred_img.shape[:2]
    h2, w2 = anno_img.shape[:2]

    if w1 != w2:
        scale = w1 / w2
        new_h = int(h2 * scale)
        anno_img = cv2.resize(anno_img, (w1, new_h))

    # Concatenate Vertically
    combined = np.vstack((pred_img, anno_img))

    # Add labels
    # Predicted label at top
    cv2.putText(combined, "Predicted", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    # Ground Truth label below the first image
    cv2.putText(
        combined, "Ground Truth", (50, h1 + 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
    )

    cv2.imwrite(output_path, combined)
    print(f"Saved comparison to {output_path}")


def main():
    base_dir = Path(
        "/Users/kevin/Documents/deprecated/odin/apps/vision/worker/scripts/segmentation"
    )
    dataset_dir = base_dir / "dataset"
    predicted_dir = base_dir / "predicted"

    # Ensure predicted dir exists
    predicted_dir.mkdir(exist_ok=True)

    # Get all PNGs
    all_files = sorted(list(dataset_dir.glob("*.png")))

    # Separate input and annotated
    annotated_files = [f for f in all_files if "_annotated" in f.name]
    input_images = [f for f in all_files if "_annotated" not in f.name]

    print(f"Found {len(input_images)} input images and {len(annotated_files)} annotated images.")

    # Define versions to run
    versions = [
        ("gemini_proposal", propose_regions_gemini),
        # ("llm_proposal", propose_regions_llm),
        # ("granular", segment_granular),
        # ("final", segment_final),
        # ("refined", segment_refined),
        # ("v2", segment_refined_v2),
        # ("v3", segment_refined_v3),
        # ("tight", segment_tight),
        # ("polygon", segment_polygon),
    ]

    for img_path in input_images:
        print(f"\n--- Processing {img_path.name} ---")

        # Find corresponding annotated file once
        input_key = normalize_for_match(img_path.name)
        matched_anno = None
        for anno in annotated_files:
            anno_key = normalize_for_match(anno.name)
            if input_key == anno_key:
                matched_anno = anno
                break

        if not matched_anno:
            print(f"Warning: Could not find annotated file for {img_path.name}")
            continue

        # Run for each version
        for v_name, v_func in versions:
            print(f"Running {v_name}...")
            pred_filename = f"{img_path.stem[:20]}_predicted_{v_name}.png"
            pred_path = predicted_dir / pred_filename

            try:
                # 1. Generate Prediction
                v_func(str(img_path), str(pred_path))

                # 2. Create Comparison
                comp_filename = f"{img_path.stem[:20]}_comparison_{v_name}.png"
                comp_path = predicted_dir / comp_filename
                create_comparison(
                    str(img_path), str(pred_path), str(matched_anno), str(comp_path), v_name
                )

                # 3. Cleanup Prediction Image (as requested)
                if pred_path.exists():
                    os.remove(pred_path)

            except Exception as e:
                print(f"Error running {v_name} on {img_path.name}: {e}")


if __name__ == "__main__":
    main()
