def cmyk_to_rgb(cmyk: tuple) -> tuple:
    """Convert CMYK values to grayscale."""
    c, m, y, k = cmyk
    return (1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)


def rgb_to_gray(rgb: tuple) -> float:
    """Convert RGB values to grayscale using luminance formula."""
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def cmyk_to_gray(cmyk: tuple) -> float:
    """Convert CMYK values to grayscale."""
    return rgb_to_gray(cmyk_to_rgb(cmyk))


def gray_to_tinted(gray: float, tint: tuple) -> tuple:
    """Convert a grayscale value to a tinted RGB color based on the target color."""
    r, g, b = tint
    return r + gray * (1 - r), g + gray * (1 - g), b + gray * (1 - b)


def rgb_to_tinted(rgb: tuple, tint: tuple) -> tuple:
    """Convert an RGB color to a tinted RGB color based on the target tint."""
    return gray_to_tinted(rgb_to_gray(rgb), tint)


def cmyk_to_tinted(cmyk: tuple, tint: tuple) -> tuple:
    """Convert a CMYK color to a tinted RGB color based on the target tint."""
    return gray_to_tinted(cmyk_to_gray(cmyk), tint)
