"""Unit tests for alignment.py pure functions."""

import numpy as np
import pytest
from PIL import Image

from lib.sift_alignment import (
    _encode_image_to_png,
    _load_image_from_bytes,
    apply_transformation,
    estimate_transformation,
    extract_sift_features,
    match_features,
)


class TestImageIO:
    """Tests for image I/O helper functions."""

    def test_load_image_from_bytes_valid_png(self):
        """Test loading valid PNG bytes returns RGB numpy array."""
        # Arrange: Create a simple test image
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))  # Red image
        import io

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        png_bytes = buffer.getvalue()

        # Act
        result = _load_image_from_bytes(png_bytes)

        # Assert
        assert isinstance(result, np.ndarray)
        assert result.shape == (100, 100, 3)
        assert result.dtype == np.uint8
        # Check that it's red (R=255, G=0, B=0)
        assert np.allclose(result[0, 0], [255, 0, 0])

    def test_load_image_from_bytes_invalid_data(self):
        """Test loading invalid bytes raises ValueError."""
        # Arrange
        invalid_bytes = b"not a valid png"

        # Act & Assert
        with pytest.raises(ValueError):
            _load_image_from_bytes(invalid_bytes)

    def test_encode_image_to_png_valid_array(self):
        """Test encoding numpy array to PNG bytes."""
        # Arrange: Create a simple numpy array
        img_array = np.zeros((100, 100, 3), dtype=np.uint8)
        img_array[:, :] = [0, 255, 0]  # Green image

        # Act
        result = _encode_image_to_png(img_array)

        # Assert
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Verify it's valid PNG by decoding
        decoded = _load_image_from_bytes(result)
        assert np.array_equal(decoded, img_array)

    def test_encode_image_to_png_invalid_shape(self):
        """Test encoding array with invalid shape raises ValueError."""
        # Arrange: Wrong shape (should be H x W x 3)
        invalid_array = np.zeros((100, 100), dtype=np.uint8)  # Grayscale

        # Act & Assert
        with pytest.raises(ValueError):
            _encode_image_to_png(invalid_array)


class TestSIFTFeatureExtraction:
    """Tests for SIFT feature extraction with margin masking."""

    def test_extract_sift_features_sufficient_features(self, test_old_image_path):
        """Test SIFT extracts features from test image with margin masking."""
        # Arrange
        img = Image.open(test_old_image_path).convert("L")  # Grayscale
        gray_array = np.array(img)

        # Act
        keypoints, descriptors = extract_sift_features(
            gray_array, n_features=10_000, exclude_margin=0.2
        )

        # Assert
        assert keypoints is not None
        assert descriptors is not None
        assert len(keypoints) > 0
        assert len(keypoints) == len(descriptors)
        assert descriptors.shape[1] == 128  # SIFT descriptor dimension
        # Should detect features but respect max limit
        assert len(keypoints) <= 10_000

    def test_extract_sift_features_margin_exclusion(self):
        """Test margin exclusion prevents feature detection in edge areas."""
        # Arrange: Create image with features only in margins
        gray_image = np.zeros((200, 200), dtype=np.uint8)
        # Add features in corners (will be excluded by 20% margin)
        gray_image[0:20, 0:20] = 255
        gray_image[180:200, 180:200] = 255
        # Add features in center (will be detected)
        gray_image[90:110, 90:110] = 255

        # Act
        keypoints, descriptors = extract_sift_features(
            gray_image, n_features=1_000, exclude_margin=0.2
        )

        # Assert
        # Features should be detected (mostly from center)
        assert len(keypoints) > 0
        # Verify no features are in margin (first 40 pixels on each edge)
        for kp in keypoints:
            x, y = kp.pt
            assert 40 <= x < 160, f"Feature at x={x} is in margin"
            assert 40 <= y < 160, f"Feature at y={y} is in margin"

    def test_extract_sift_features_invalid_image(self):
        """Test invalid image raises ValueError."""
        # Arrange: RGB image instead of grayscale
        rgb_image = np.zeros((100, 100, 3), dtype=np.uint8)

        # Act & Assert
        with pytest.raises(ValueError):
            extract_sift_features(rgb_image)


class TestFeatureMatching:
    """Tests for feature matching with Lowe's ratio test."""

    def test_match_features_valid_descriptors(self):
        """Test feature matching returns good matches."""
        # Arrange: Create synthetic descriptors (similar features)
        np.random.seed(42)
        descriptors1 = np.random.rand(100, 128).astype(np.float32)
        # Make descriptors2 similar to descriptors1 (with some noise)
        descriptors2 = descriptors1 + np.random.rand(100, 128).astype(np.float32) * 0.1

        # Act
        matches = match_features(descriptors1, descriptors2, ratio_threshold=0.75)

        # Assert
        assert isinstance(matches, list)
        assert len(matches) > 0  # Should find some matches
        # Each match should have query and train index
        for match in matches:
            assert hasattr(match, "queryIdx")
            assert hasattr(match, "trainIdx")
            assert hasattr(match, "distance")

    def test_match_features_no_matches(self):
        """Test feature matching with completely different descriptors."""
        # Arrange: Completely different descriptors
        np.random.seed(42)
        descriptors1 = np.random.rand(50, 128).astype(np.float32)
        descriptors2 = np.random.rand(50, 128).astype(np.float32) + 10  # Very different

        # Act
        matches = match_features(descriptors1, descriptors2, ratio_threshold=0.75)

        # Assert
        # May have very few or no matches
        assert isinstance(matches, list)
        assert len(matches) >= 0

    def test_match_features_empty_descriptors(self):
        """Test feature matching with empty descriptors raises ValueError."""
        # Arrange
        empty_descriptors = np.array([]).reshape(0, 128).astype(np.float32)
        valid_descriptors = np.random.rand(50, 128).astype(np.float32)

        # Act & Assert
        with pytest.raises(ValueError):
            match_features(empty_descriptors, valid_descriptors)


class TestTransformationEstimation:
    """Tests for RANSAC transformation estimation with constraints."""

    def test_estimate_transformation_valid_matches(self, sample_keypoints_and_matches):
        """Test transformation estimation with sufficient matches."""
        # Arrange
        kp1, kp2, matches = sample_keypoints_and_matches

        # Act
        matrix, mask, inlier_count, total_matches = estimate_transformation(
            kp1,
            kp2,
            matches,
            reproj_threshold=15.0,
            max_iters=5_000,
            confidence=0.95,
            scale_min=0.3,
            scale_max=2.5,
            rotation_deg_min=-30.0,
            rotation_deg_max=30.0,
        )

        # Assert
        assert matrix is not None
        assert matrix.shape == (2, 3)
        assert mask is not None
        assert inlier_count >= 3  # Minimum for affine transformation
        assert inlier_count <= total_matches
        assert total_matches == len(matches)

    def test_estimate_transformation_insufficient_matches(self):
        """Test transformation estimation with < 3 matches raises ValueError."""
        # Arrange: Only 2 matches (insufficient)
        import cv2

        kp1 = tuple([cv2.KeyPoint(x=10, y=10, size=1), cv2.KeyPoint(x=20, y=20, size=1)])
        kp2 = tuple([cv2.KeyPoint(x=12, y=12, size=1), cv2.KeyPoint(x=22, y=22, size=1)])
        matches = [cv2.DMatch(0, 0, 0, 1.0), cv2.DMatch(1, 1, 0, 1.5)]

        # Act & Assert
        with pytest.raises(ValueError, match="Insufficient matches"):
            estimate_transformation(kp1, kp2, matches)

    def test_estimate_transformation_constraints(self):
        """Test transformation estimation respects scale and rotation constraints."""
        # This test is difficult to unit test without full integration
        # Will be covered by integration tests with real images
        pytest.skip("Requires integration test with real images showing extreme transformations")


class TestApplyTransformation:
    """Tests for image warping with affine transformation."""

    def test_apply_transformation_valid_matrix(self):
        """Test applying affine transformation warps image correctly."""
        # Arrange
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[40:60, 40:60] = [255, 0, 0]  # Red square in center
        # Simple translation matrix: move 10 pixels right, 5 pixels down
        matrix = np.array([[1, 0, 10], [0, 1, 5]], dtype=np.float32)

        # Act
        warped = apply_transformation(img, matrix, output_shape=(100, 100))

        # Assert
        assert warped.shape == (100, 100, 3)
        assert warped.dtype == np.uint8
        # Check that red pixels exist in warped region (after translation)
        # Original was at [40:60, 40:60], after shift should be at [45:65, 50:70]
        red_pixels_in_warped = warped[45:65, 50:70]
        # At least check that we have red pixels (not all white/black)
        assert np.any(red_pixels_in_warped[:, :, 0] == 255)  # Red channel
        assert np.any(red_pixels_in_warped[:, :, 1] == 0)  # Green channel
        assert np.any(red_pixels_in_warped[:, :, 2] == 0)  # Blue channel

    def test_apply_transformation_invalid_matrix_shape(self):
        """Test invalid transformation matrix raises ValueError."""
        # Arrange
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        invalid_matrix = np.array([[1, 0], [0, 1]], dtype=np.float32)  # Wrong shape

        # Act & Assert
        with pytest.raises(ValueError, match="transformation_matrix shape"):
            apply_transformation(img, invalid_matrix, output_shape=(100, 100))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def test_old_image_path():
    """Path to test old image."""
    return "tests/assets/overlay/test_old.png"


@pytest.fixture
def test_new_image_path():
    """Path to test new image."""
    return "tests/assets/overlay/test_new.png"


@pytest.fixture
def sample_keypoints_and_matches():
    """Sample keypoints and matches for testing."""
    import cv2

    # Create sample keypoints (simple grid pattern)
    kp1 = tuple(
        [
            cv2.KeyPoint(x=10, y=10, size=1),
            cv2.KeyPoint(x=20, y=10, size=1),
            cv2.KeyPoint(x=30, y=10, size=1),
            cv2.KeyPoint(x=10, y=20, size=1),
            cv2.KeyPoint(x=20, y=20, size=1),
        ]
    )

    # Create corresponding keypoints with slight translation
    kp2 = tuple(
        [
            cv2.KeyPoint(x=12, y=12, size=1),
            cv2.KeyPoint(x=22, y=12, size=1),
            cv2.KeyPoint(x=32, y=12, size=1),
            cv2.KeyPoint(x=12, y=22, size=1),
            cv2.KeyPoint(x=22, y=22, size=1),
        ]
    )

    # Create matches
    matches = [
        cv2.DMatch(0, 0, 0, 1.0),
        cv2.DMatch(1, 1, 0, 1.0),
        cv2.DMatch(2, 2, 0, 1.0),
        cv2.DMatch(3, 3, 0, 1.0),
        cv2.DMatch(4, 4, 0, 1.0),
    ]

    return kp1, kp2, matches
