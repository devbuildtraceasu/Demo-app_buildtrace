#!/usr/bin/env python3
"""Test different overlay alignment and rendering methods.

Compares:
1. SIFT alignment + merge mode (current)
2. SIFT alignment + diff mode
3. SIFT alignment + line colorization (expected style)
4. Grid alignment + line colorization
5. No alignment + line colorization (if images are already aligned)
"""

import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, '/Users/ashishrajshekhar/Downloads/Overlay-main/vision/worker')

from lib.sift_alignment import sift_align, _load_image_from_bytes, _encode_image_to_png
from lib.overlay_render import generate_overlay_merge_mode, generate_overlay_diff_mode

# Your test images
OLD_PNG = "/Users/ashishrajshekhar/Downloads/Overlay-main/my_set/old.png"
NEW_PNG = "/Users/ashishrajshekhar/Downloads/Overlay-main/my_set/new.png"
OUTPUT_DIR = "/Users/ashishrajshekhar/Downloads/Overlay-main/my_set/results"


def load_image(path: str) -> np.ndarray:
    """Load image as RGB numpy array."""
    with open(path, "rb") as f:
        return _load_image_from_bytes(f.read())


def save_image(img: np.ndarray, path: str):
    """Save RGB numpy array as PNG."""
    Image.fromarray(img).save(path)
    print(f"   ✅ Saved: {Path(path).name}")


def colorize_lines_overlay(old_img: np.ndarray, new_img: np.ndarray, 
                           ink_threshold: int = 240) -> np.ndarray:
    """Create overlay where old=red lines, new=green lines.
    
    This matches the expected output style:
    - Lines from old image appear RED
    - Lines from new image appear GREEN
    - Where both overlap, appears dark (black/brown)
    - White background where both are blank
    
    Args:
        old_img: Old image (RGB)
        new_img: New image (RGB)
        ink_threshold: Pixels darker than this are "ink/content"
    
    Returns:
        RGB overlay image
    """
    # Convert to grayscale
    old_gray = cv2.cvtColor(old_img, cv2.COLOR_RGB2GRAY)
    new_gray = cv2.cvtColor(new_img, cv2.COLOR_RGB2GRAY)
    
    # Invert so lines are white (high values)
    old_inv = 255 - old_gray
    new_inv = 255 - new_gray
    
    # Create RGB where:
    # R = old lines (inverted old)
    # G = new lines (inverted new)
    # B = 0 or combined for neutral
    
    # Method: Direct channel assignment
    # Red channel shows where OLD has content
    # Green channel shows where NEW has content
    r = old_inv
    g = new_inv
    b = np.minimum(old_inv, new_inv)  # Shared content
    
    overlay = np.stack([r, g, b], axis=-1)
    return overlay


def colorize_lines_overlay_v2(old_img: np.ndarray, new_img: np.ndarray,
                               ink_threshold: int = 220) -> np.ndarray:
    """Alternative: Tint lines directly on white background.
    
    - Old content → Red tint
    - New content → Green tint
    - Unchanged → Black/gray
    """
    old_gray = cv2.cvtColor(old_img, cv2.COLOR_RGB2GRAY)
    new_gray = cv2.cvtColor(new_img, cv2.COLOR_RGB2GRAY)
    
    # Detect ink (lines)
    old_mask = old_gray < ink_threshold
    new_mask = new_gray < ink_threshold
    
    # Start with white background
    h, w = old_gray.shape
    overlay = np.full((h, w, 3), 255, dtype=np.uint8)
    
    # Only old (removed) → Red
    only_old = old_mask & ~new_mask
    overlay[only_old] = [255, 0, 0]  # Pure red
    
    # Only new (added) → Green
    only_new = new_mask & ~old_mask
    overlay[only_new] = [0, 255, 0]  # Pure green
    
    # Both (unchanged) → Black/gray from average
    both = old_mask & new_mask
    avg_gray = ((old_gray[both].astype(np.int32) + new_gray[both].astype(np.int32)) // 2).astype(np.uint8)
    overlay[both] = np.stack([avg_gray, avg_gray, avg_gray], axis=-1)
    
    return overlay


def colorize_lines_overlay_v3(old_img: np.ndarray, new_img: np.ndarray) -> np.ndarray:
    """Match the expected output style exactly.
    
    Uses the grayscale values to create colored lines:
    - Darker old pixels → More red
    - Darker new pixels → More green
    """
    old_gray = cv2.cvtColor(old_img, cv2.COLOR_RGB2GRAY).astype(np.float32)
    new_gray = cv2.cvtColor(new_img, cv2.COLOR_RGB2GRAY).astype(np.float32)
    
    # Invert: 0 = white, 255 = black line
    old_line = 255.0 - old_gray
    new_line = 255.0 - new_gray
    
    # Create output
    # R = 255 - new_line (more red where old has content, less where new)
    # G = 255 - old_line (more green where new has content, less where old)
    # B = 255 - max(old_line, new_line) (neutral)
    
    # Alternative: Make it look like the expected
    # Background = white (255)
    # Old lines = red (subtract from G and B)
    # New lines = green (subtract from R and B)
    
    r = np.clip(255 - new_line * 0.8, 0, 255)  # Less red where new has content
    g = np.clip(255 - old_line * 0.8, 0, 255)  # Less green where old has content
    b = np.clip(255 - np.maximum(old_line, new_line) * 0.9, 0, 255)
    
    overlay = np.stack([r, g, b], axis=-1).astype(np.uint8)
    return overlay


def run_tests():
    """Run all overlay tests."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("🖼️  Loading images...")
    old_img = load_image(OLD_PNG)
    new_img = load_image(NEW_PNG)
    print(f"   Old: {old_img.shape}")
    print(f"   New: {new_img.shape}")
    
    # Test 1: No alignment - just colorize (if images are same size)
    print("\n📊 Test 1: No alignment + Line Colorization V1 (channel merge)")
    if old_img.shape == new_img.shape:
        overlay1 = colorize_lines_overlay(old_img, new_img)
        save_image(overlay1, f"{OUTPUT_DIR}/01_no_align_colorize_v1.png")
    else:
        print("   ⚠️ Images different sizes, skipping")
    
    # Test 2: No alignment - colorize v2
    print("\n📊 Test 2: No alignment + Line Colorization V2 (discrete)")
    if old_img.shape == new_img.shape:
        overlay2 = colorize_lines_overlay_v2(old_img, new_img)
        save_image(overlay2, f"{OUTPUT_DIR}/02_no_align_colorize_v2.png")
    else:
        print("   ⚠️ Images different sizes, skipping")
        
    # Test 3: No alignment - colorize v3 (expected style)
    print("\n📊 Test 3: No alignment + Line Colorization V3 (gradient)")
    if old_img.shape == new_img.shape:
        overlay3 = colorize_lines_overlay_v3(old_img, new_img)
        save_image(overlay3, f"{OUTPUT_DIR}/03_no_align_colorize_v3.png")
    else:
        print("   ⚠️ Images different sizes, skipping")
    
    # Test 4: SIFT alignment + merge mode (current)
    print("\n📊 Test 4: SIFT Alignment + Merge Mode (current)")
    try:
        aligned_old, aligned_new, stats = sift_align(
            old_img, new_img,
            downsample_scale=0.5,
            n_features=2000,
            ratio_threshold=0.75,
            ransac_threshold=15.0,
            normalize_size=True,
            expand_canvas=True,
        )
        print(f"   SIFT stats: scale={stats.scale:.3f}, rotation={stats.rotation_deg:.2f}°, inliers={stats.inlier_count}")
        
        overlay4, _, _ = generate_overlay_merge_mode(aligned_old, aligned_new)
        save_image(overlay4, f"{OUTPUT_DIR}/04_sift_merge_mode.png")
        
        # Also save aligned images
        save_image(aligned_old, f"{OUTPUT_DIR}/04a_sift_aligned_old.png")
        save_image(aligned_new, f"{OUTPUT_DIR}/04b_sift_aligned_new.png")
        
        # Test 5: SIFT + diff mode
        print("\n📊 Test 5: SIFT Alignment + Diff Mode")
        overlay5, deletion5, addition5 = generate_overlay_diff_mode(aligned_old, aligned_new)
        save_image(overlay5, f"{OUTPUT_DIR}/05_sift_diff_mode.png")
        save_image(deletion5, f"{OUTPUT_DIR}/05a_sift_deletions.png")
        save_image(addition5, f"{OUTPUT_DIR}/05b_sift_additions.png")
        
        # Test 6: SIFT + line colorization v1
        print("\n📊 Test 6: SIFT Alignment + Line Colorization V1")
        overlay6 = colorize_lines_overlay(aligned_old, aligned_new)
        save_image(overlay6, f"{OUTPUT_DIR}/06_sift_colorize_v1.png")
        
        # Test 7: SIFT + line colorization v3
        print("\n📊 Test 7: SIFT Alignment + Line Colorization V3")
        overlay7 = colorize_lines_overlay_v3(aligned_old, aligned_new)
        save_image(overlay7, f"{OUTPUT_DIR}/07_sift_colorize_v3.png")
        
    except Exception as e:
        print(f"   ❌ SIFT failed: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n✨ Done! Check results in: {OUTPUT_DIR}")
    print("\nCompare these files to find the best match:")
    print("  - 01-03: No alignment (if images already aligned)")
    print("  - 04: Current merge mode")
    print("  - 05: Diff mode with discrete changes")
    print("  - 06-07: SIFT + colorization styles")


if __name__ == "__main__":
    run_tests()

