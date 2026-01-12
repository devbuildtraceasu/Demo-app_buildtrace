import cv2
import numpy as np


def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Could not load image from {path}")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img


def save_image(img: np.ndarray, path: str) -> None:
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    success = cv2.imwrite(path, img)
    if not success:
        raise RuntimeError(f"Failed to save image to {path}")


def image_to_grayscale(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.bitwise_not(gray)
    return gray


def sharpen_image(image, sigma=1.0, strength=1.5):
    image_float = image.astype(np.float32)
    blurred = cv2.GaussianBlur(image_float, (0, 0), sigma)
    mask = image_float - blurred
    sharpened = image_float + mask * strength
    sharpened = np.clip(sharpened, 0, 255)
    sharpened = sharpened.astype(image.dtype)
    return sharpened


def image_to_float(img: np.ndarray) -> np.ndarray:
    return img.astype(np.float32) / 255.0


def image_to_uint8(img: np.ndarray) -> np.ndarray:
    return np.clip(img * 255.0, 0, 255).astype(np.uint8)


def transform_image(img: np.ndarray, matrix: np.ndarray, target_size: tuple) -> np.ndarray:
    return cv2.warpAffine(img, matrix, target_size)


def create_overlay_image(old_img, new_img, matrix) -> np.ndarray:
    """Visualize transformation results, drawing only inlier matches"""
    # Convert images to float32
    old_img = image_to_float(old_img)
    new_img = image_to_float(new_img)

    # Transform old image to align with new image
    old_img = transform_image(old_img, matrix, (new_img.shape[1], new_img.shape[0]))

    # Apply color tints and create overlay
    old_tinted = apply_color_tint(old_img, (0, 1, 0))  # Green tint for old image
    new_tinted = apply_color_tint(new_img, (1, 0, 0))  # Red tint for new image

    # Create overlay by blending the two tinted images
    overlay = old_tinted * new_tinted

    # Convert back to uint8
    overlay = image_to_uint8(overlay)
    return overlay


def apply_color_tint(img: np.ndarray, tint_color: tuple) -> np.ndarray:
    """Apply a color tint where black maps to tint color and white stays white"""
    img_float = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Create tint color array normalized to [0, 1]
    tint_rgb = np.array([[tint_color]], dtype=np.float32)

    # For each pixel, interpolate between tint color and white based on brightness
    # White pixels (1.0) stay white, black pixels (0.0) become tint color
    tinted = img_float * (1 - tint_rgb) + tint_rgb

    return tinted
