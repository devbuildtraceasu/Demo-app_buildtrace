"""Integration tests for alignment image generation mask consistency.

These tests validate that overlay uses _compute_change_masks correctly
and produces mutually exclusive masks for deletions, additions, and unchanged content.
"""

import numpy as np

from lib.sift_alignment import (
    _compute_change_masks,
    generate_overlay,
)


class TestMaskConsistency:
    """Integration tests for mask consistency using _compute_change_masks."""

    def test_mask_consistency_with_all_change_types(self):
        """Verify deletion, addition, and unchanged masks are mutually exclusive.

        Creates images with known deletions, additions, and unchanged content,
        then verifies _compute_change_masks classifies pixels correctly.
        """
        # Create aligned_old image: 100x100 RGB with specific patterns
        # Top-left quadrant (0-49, 0-49): Black pixels (content only in old = deletions)
        # Top-right quadrant (0-49, 50-99): White pixels (no content in old)
        # Bottom-left quadrant (50-99, 0-49): Black pixels (content in both = unchanged)
        # Bottom-right quadrant (50-99, 50-99): White pixels (no content)
        aligned_old = np.full((100, 100, 3), 255, dtype=np.uint8)  # Start white
        aligned_old[0:50, 0:50] = [0, 0, 0]  # Top-left: Black (will be deletions)
        aligned_old[50:100, 0:50] = [100, 100, 100]  # Bottom-left: Gray (unchanged)

        # Create new image: 100x100 RGB with different patterns
        # Top-left quadrant: White (no content in new)
        # Top-right quadrant: Black (content only in new = additions)
        # Bottom-left quadrant: Gray (content in both = unchanged, matching aligned_old)
        # Bottom-right quadrant: White (no content)
        new = np.full((100, 100, 3), 255, dtype=np.uint8)  # Start white
        new[0:50, 50:100] = [0, 0, 0]  # Top-right: Black (will be additions)
        new[50:100, 0:50] = [100, 100, 100]  # Bottom-left: Gray (unchanged, matches old)

        # Compute masks and generate overlay (disable morph cleanup for precise pixel counting)
        removed, added, unchanged, _ = _compute_change_masks(aligned_old, new, morph_kernel_size=1)
        overlay = generate_overlay(aligned_old, new, morph_kernel_size=1)

        # Verify output shapes match
        assert overlay.shape == (100, 100, 3)
        assert removed.shape == (100, 100)
        assert added.shape == (100, 100)
        assert unchanged.shape == (100, 100)

        # Expected counts
        expected_deletion_pixels = 50 * 50  # 2,500 pixels
        expected_addition_pixels = 50 * 50  # 2,500 pixels
        expected_unchanged_pixels = 50 * 50  # 2,500 pixels

        # Verify removed mask: Only top-left quadrant
        assert (
            np.sum(removed) == expected_deletion_pixels
        ), f"Expected {expected_deletion_pixels} deletion pixels, got {np.sum(removed)}"
        assert np.all(removed[0:50, 0:50]), "Deletion pixels missing from top-left quadrant"
        assert not np.any(removed[0:50, 50:100]), "Unexpected deletion pixels in top-right"
        assert not np.any(removed[50:100, :]), "Unexpected deletion pixels in bottom half"

        # Verify added mask: Only top-right quadrant
        assert (
            np.sum(added) == expected_addition_pixels
        ), f"Expected {expected_addition_pixels} addition pixels, got {np.sum(added)}"
        assert np.all(added[0:50, 50:100]), "Addition pixels missing from top-right quadrant"
        assert not np.any(added[0:50, 0:50]), "Unexpected addition pixels in top-left"
        assert not np.any(added[50:100, :]), "Unexpected addition pixels in bottom half"

        # Verify unchanged mask: Only bottom-left quadrant
        assert (
            np.sum(unchanged) == expected_unchanged_pixels
        ), f"Expected {expected_unchanged_pixels} unchanged pixels, got {np.sum(unchanged)}"

        # Verify overlay matches masks
        overlay_red_mask = np.all(overlay == [255, 0, 0], axis=-1)
        overlay_green_mask = np.all(overlay == [0, 255, 0], axis=-1)
        overlay_gray_mask = np.all(overlay == [100, 100, 100], axis=-1)

        assert np.sum(overlay_red_mask) == expected_deletion_pixels
        assert np.sum(overlay_green_mask) == expected_addition_pixels
        assert np.sum(overlay_gray_mask) == expected_unchanged_pixels

        # Verify no overlap between masks
        assert not np.any(removed & added), "Removed and added masks overlap"
        assert not np.any(removed & unchanged), "Removed and unchanged masks overlap"
        assert not np.any(added & unchanged), "Added and unchanged masks overlap"

    def test_mask_consistency_with_no_changes(self):
        """Verify masks handle identical inputs correctly.

        When old and new images are identical, there should be:
        - No deletions
        - No additions
        - All unchanged
        """
        # Create identical images: 50x50 with gray content
        aligned_old = np.full((50, 50, 3), 150, dtype=np.uint8)
        new = aligned_old.copy()

        # Compute masks
        removed, added, unchanged, _ = _compute_change_masks(aligned_old, new)
        overlay = generate_overlay(aligned_old, new)

        # No deletions or additions
        assert np.sum(removed) == 0, "Should have no deletions"
        assert np.sum(added) == 0, "Should have no additions"

        # All pixels unchanged
        assert np.sum(unchanged) == 50 * 50, "All pixels should be unchanged"

        # Overlay should be all gray
        overlay_gray_mask = np.all(overlay == [150, 150, 150], axis=-1)
        assert np.all(overlay_gray_mask), "Overlay should be all gray when no changes"

    def test_mask_consistency_with_only_deletions(self):
        """Verify behavior when only deletions exist (no additions)."""
        # Create images with only deletions
        aligned_old = np.full((50, 50, 3), 100, dtype=np.uint8)  # Gray content in old
        new = np.full((50, 50, 3), 255, dtype=np.uint8)  # All white in new

        # Compute masks
        removed, added, unchanged, _ = _compute_change_masks(aligned_old, new)
        overlay = generate_overlay(aligned_old, new)

        # All pixels should be deletions
        assert np.sum(removed) == 50 * 50, "All pixels should be deleted"
        assert np.sum(added) == 0, "Should have no additions"
        assert np.sum(unchanged) == 0, "Should have no unchanged"

        # Overlay should be all red
        overlay_red_mask = np.all(overlay == [255, 0, 0], axis=-1)
        assert np.all(overlay_red_mask), "Overlay should be all red when only deletions"

    def test_mask_consistency_with_only_additions(self):
        """Verify behavior when only additions exist (no deletions)."""
        # Create images with only additions
        aligned_old = np.full((50, 50, 3), 255, dtype=np.uint8)  # All white in old
        new = np.full((50, 50, 3), 100, dtype=np.uint8)  # Gray content in new

        # Compute masks
        removed, added, unchanged, _ = _compute_change_masks(aligned_old, new)
        overlay = generate_overlay(aligned_old, new)

        # All pixels should be additions
        assert np.sum(removed) == 0, "Should have no deletions"
        assert np.sum(added) == 50 * 50, "All pixels should be added"
        assert np.sum(unchanged) == 0, "Should have no unchanged"

        # Overlay should be all green
        overlay_green_mask = np.all(overlay == [0, 255, 0], axis=-1)
        assert np.all(overlay_green_mask), "Overlay should be all green when only additions"

    def test_threshold_boundary_behavior(self):
        """Verify pixel classification at threshold boundary (250).

        Tests that pixels with intensity exactly at or above threshold are treated
        as "no content" while pixels below threshold are "content present".
        The intensity_threshold (default 40) requires sufficient difference from white.
        """
        # Create test images with pixels at threshold boundaries
        # Use intensity 100 (well below 250) to ensure strong diff from white (255-100=155 > 40)
        aligned_old = np.full((2, 2, 3), 255, dtype=np.uint8)
        aligned_old[0, 0] = [100, 100, 100]  # Below 250 threshold, strong diff → deletion
        aligned_old[0, 1] = [250, 250, 250]  # At threshold → no content
        aligned_old[1, 0] = [251, 251, 251]  # Above threshold → no content

        # new: all white (no content)
        new = np.full((2, 2, 3), 255, dtype=np.uint8)

        # Compute masks (disable morph cleanup for small test image)
        removed, added, unchanged, _ = _compute_change_masks(aligned_old, new, morph_kernel_size=1)
        overlay = generate_overlay(aligned_old, new, morph_kernel_size=1)

        # Only pixel at (0,0) with intensity 100 should be classified as deletion
        assert removed[0, 0], "Pixel at 100 should be deletion"
        assert not removed[0, 1], "Pixel at 250 should not be deletion"
        assert not removed[1, 0], "Pixel at 251 should not be deletion"
        assert not removed[1, 1], "Pixel at 255 should not be deletion"

        # Verify overlay matches
        assert np.all(overlay[0, 0] == [255, 0, 0]), "Pixel at 100 should be red in overlay"
        assert np.all(overlay[0, 1] == [255, 255, 255]), "Pixel at 250 should be white in overlay"
        assert np.all(overlay[1, 0] == [255, 255, 255]), "Pixel at 251 should be white in overlay"
        assert np.all(overlay[1, 1] == [255, 255, 255]), "Pixel at 255 should be white in overlay"
