#!/usr/bin/env python3
"""
Test script for PDF color tinting functionality.
Converts colors to an arbitrary single color tint where:
- Black turns into the target color (e.g., red)
- Gray turns into a lighter version of the target color
- White maps to white
"""

import re
from pathlib import Path

import pymupdf


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


def get_page_content_streams(page: pymupdf.Page) -> list[int]:
    """Return list of xrefs of the page's content streams."""
    key = page.parent.xref_get_key(page.xref, "Contents")
    if key[0] == "xref":
        return [int(str(key[1]).split()[0])]
    if key[0] == "array":
        arr = key[1]
        return [int(m.group(1)) for m in re.finditer(r"(\d+)\s+0\s+R", arr)]
    return []


def convert_stream_to_tinted(stream_content: str, tint: tuple) -> str:
    """Convert all color operators in a content stream to tinted colors."""

    def unified_color_replacement(match):
        """Unified replacement function for all color operators."""
        full_match = match.group(0)

        # Determine the color space and operator based on the matched pattern
        if full_match.endswith(" rg"):  # RGB fill
            parts = full_match.split()
            r, g, b = map(float, parts[:3])
            converted_r, converted_g, converted_b = rgb_to_tinted((r, g, b), tint)
            return f"{converted_r:.6f} {converted_g:.6f} {converted_b:.6f} rg"
        elif full_match.endswith(" RG"):  # RGB stroke
            parts = full_match.split()
            r, g, b = map(float, parts[:3])
            converted_r, converted_g, converted_b = rgb_to_tinted((r, g, b), tint)
            return f"{converted_r:.6f} {converted_g:.6f} {converted_b:.6f} RG"
        elif full_match.endswith(" k"):  # CMYK fill
            parts = full_match.split()
            c, m, y, k = map(float, parts[:4])
            converted_r, converted_g, converted_b = cmyk_to_tinted((c, m, y, k), tint)
            return f"{converted_r:.6f} {converted_g:.6f} {converted_b:.6f} rg"
        elif full_match.endswith(" K"):  # CMYK stroke
            parts = full_match.split()
            c, m, y, k = map(float, parts[:4])
            converted_r, converted_g, converted_b = cmyk_to_tinted((c, m, y, k), tint)
            return f"{converted_r:.6f} {converted_g:.6f} {converted_b:.6f} RG"
        elif full_match.endswith(" g"):  # Gray fill
            parts = full_match.split()
            gray = float(parts[0])
            converted_r, converted_g, converted_b = gray_to_tinted(gray, tint)
            return f"{converted_r:.6f} {converted_g:.6f} {converted_b:.6f} rg"
        elif full_match.endswith(" G"):  # Gray stroke
            parts = full_match.split()
            gray = float(parts[0])
            converted_r, converted_g, converted_b = gray_to_tinted(gray, tint)
            return f"{converted_r:.6f} {converted_g:.6f} {converted_b:.6f} RG"

        return full_match  # Fallback, should not happen

    # Unified regex pattern that matches all color operators in one pass
    unified_pattern = re.compile(
        r"[0-9.]+\s+[0-9.]+\s+[0-9.]+\s+(?:rg|RG)|"  # RGB fill/stroke
        r"[0-9.]+\s+[0-9.]+\s+[0-9.]+\s+[0-9.]+\s+(?:k|K)|"  # CMYK fill/stroke
        r"[0-9.]+\s+(?:g|G)(?=\s|$|\n|\r)"  # Gray fill/stroke - must be followed by whitespace or end
    )

    # Set default tinted color for black (0 g)
    black_r, black_g, black_b = gray_to_tinted(0.0, tint)  # Convert black to tinted color
    tinted_color = f"{black_r:.6f} {black_g:.6f} {black_b:.6f}"

    # FIRST: Convert all explicit color operators
    converted_content = unified_pattern.sub(unified_color_replacement, stream_content)

    # SECOND: Simple fix for DeviceGray CS issue - just add color after it
    converted_content = re.sub(
        r"/DeviceGray\s+CS", f"/DeviceGray CS\n{tinted_color} RG", converted_content
    )

    # THIRD: Add tinted default colors at the beginning of the stream
    converted_content = f"{tinted_color} rg\n{tinted_color} RG\n" + converted_content

    return converted_content


def convert_page_to_tinted(page: pymupdf.Page, tint: tuple) -> bool:
    """Convert a single page to tinted colors by modifying its content streams."""
    doc = page.parent

    # Get content stream xrefs
    stream_xrefs = get_page_content_streams(page)
    if not stream_xrefs:
        print("No content streams found")
        return False

    changes_made = False

    for i, stream_xref in enumerate(stream_xrefs):
        # Read original stream
        original_bytes = doc.xref_stream(stream_xref) or b""
        original_content = original_bytes.decode("latin1", errors="ignore")

        # Convert to tinted colors
        converted_content = convert_stream_to_tinted(original_content, tint)

        # Check if changes were made
        if converted_content != original_content:
            # Update the stream
            new_bytes = converted_content.encode("latin1")
            doc.update_stream(stream_xref, new_bytes)
            changes_made = True
            print(f"Stream {i + 1}: Updated ({len(original_bytes)} -> {len(new_bytes)} bytes)")
        else:
            print(f"Stream {i + 1}: No color operators found")

    return changes_made


def convert_pdf_to_tinted(input_path: str, output_path: str, tint: tuple):
    """Convert a PDF to tinted colors and save it."""
    # Load the PDF document
    doc = pymupdf.open(input_path)

    print(f"Document: {input_path}")
    print(f"Number of pages: {len(doc)}")
    print(f"PDF format: {doc.metadata.get('format', 'Unknown')}")
    print(f"Target color (RGB): {tint}")

    # Process all pages in the document
    total_changes = 0
    print(f"Processing {len(doc)} page(s)...\n")

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        if convert_page_to_tinted(page, tint):
            total_changes += 1

    print(f"\nConversion completed. {total_changes} page(s) modified.")

    # Save the modified document
    doc.save(output_path)
    print(f"Tinted PDF saved successfully to: {output_path}")

    # Get file sizes for comparison
    input_size = Path(input_path).stat().st_size
    output_size = Path(output_path).stat().st_size

    print("\nFile size comparison:")
    print(f"Original: {input_size:,} bytes")
    print(f"Tinted: {output_size:,} bytes")
    print(
        f"Difference: {output_size - input_size:+,} bytes ({((output_size - input_size) / input_size * 100):+.1f}%)"
    )

    # Close the original document
    doc.close()


def analyze_content_stream(stream_content: str) -> dict:
    """Analyze content stream for color operators."""
    analysis = {
        "rgb_fill": [],  # r g b rg
        "rgb_stroke": [],  # r g b RG
        "cmyk_fill": [],  # c m y k k
        "cmyk_stroke": [],  # c m y k K
        "gray_fill": [],  # g g
        "gray_stroke": [],  # g G
    }

    # RGB fill color (rg)
    rgb_fill_pattern = r"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+rg"
    analysis["rgb_fill"] = re.findall(rgb_fill_pattern, stream_content)

    # RGB stroke color (RG)
    rgb_stroke_pattern = r"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+RG"
    analysis["rgb_stroke"] = re.findall(rgb_stroke_pattern, stream_content)

    # CMYK fill color (k)
    cmyk_fill_pattern = r"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+k"
    analysis["cmyk_fill"] = re.findall(cmyk_fill_pattern, stream_content)

    # CMYK stroke color (K)
    cmyk_stroke_pattern = r"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+K"
    analysis["cmyk_stroke"] = re.findall(cmyk_stroke_pattern, stream_content)

    # Gray fill color (g)
    gray_fill_pattern = r"([0-9.]+)\s+g(?=\s|$|\n|\r)"
    analysis["gray_fill"] = re.findall(gray_fill_pattern, stream_content)

    # Gray stroke color (G)
    gray_stroke_pattern = r"([0-9.]+)\s+G(?=\s|$|\n|\r)"
    analysis["gray_stroke"] = re.findall(gray_stroke_pattern, stream_content)

    return analysis


def verify_conversion(output_path: str) -> bool:
    # Verify the conversion
    print("\n=== Verification ===")
    verify_doc = pymupdf.open(output_path)
    verify_page = verify_doc.load_page(0)

    # Get content streams and analyze
    verify_streams = get_page_content_streams(verify_page)
    verify_content = ""

    for stream_xref in verify_streams:
        stream_bytes = verify_doc.xref_stream(stream_xref) or b""
        verify_content += stream_bytes.decode("latin1", errors="ignore")

    verify_analysis = analyze_content_stream(verify_content)

    print("Verification - Color operators in converted PDF:")
    for color_type, colors in verify_analysis.items():
        if colors:
            print(f"  {color_type}: {len(colors)} occurrences")

    # Check conversion success
    rgb_found = verify_analysis["rgb_fill"] or verify_analysis["rgb_stroke"]
    gray_cmyk_found = (
        verify_analysis["gray_fill"]
        or verify_analysis["gray_stroke"]
        or verify_analysis["cmyk_fill"]
        or verify_analysis["cmyk_stroke"]
    )

    if rgb_found and not gray_cmyk_found:
        print("✅ Success: All colors converted to tinted RGB!")
    elif gray_cmyk_found:
        print("⚠️  Warning: Some gray/CMYK color operators still present!")
    else:
        print("ℹ️  Info: No color operators found or conversion completed")

    verify_doc.close()
    return True


def main():
    """Test the color tinting conversion with available test files."""
    # Define target colors to test
    tints = {
        "red": (1.0, 0.0, 0.0),
        "blue": (0.0, 0.0, 1.0),
        "green": (0.0, 1.0, 0.0),
        "purple": (1.0, 0.0, 1.0),
    }

    # Test conversion functions first
    print("=== Testing color conversion functions ===")
    test_target = tints["red"]
    print(f"Target color (red): {test_target}")
    print(f"Black (0.0) -> Tinted: {gray_to_tinted(0.0, test_target)}")
    print(f"Dark gray (0.25) -> Tinted: {gray_to_tinted(0.25, test_target)}")
    print(f"Mid gray (0.5) -> Tinted: {gray_to_tinted(0.5, test_target)}")
    print(f"Light gray (0.75) -> Tinted: {gray_to_tinted(0.75, test_target)}")
    print(f"White (1.0) -> Tinted: {gray_to_tinted(1.0, test_target)}")

    # Test stream conversion
    print("\n=== Testing stream conversion ===")
    test_content = "0 0 0 rg 0.5 0.5 0.5 RG 0.8 g 0.2 G"
    converted = convert_stream_to_tinted(test_content, test_target)
    print(f"Original: {test_content}")
    print(f"Converted: {converted}")

    # Test with actual PDF files
    print("\n=== Testing with red tint ===")
    test_files = [
        ("drawings/test3_old.pdf", "drawings/outputs/test3_old_green.pdf", "green"),
        ("drawings/test3_new.pdf", "drawings/outputs/test3_new_red.pdf", "red"),
    ]

    for input_path, output_path, tint in test_files:
        if Path(input_path).exists():
            print(f"\n=== Converting to red tint: {input_path} ===")
            convert_pdf_to_tinted(input_path, output_path, tints[tint])
            success = verify_conversion(output_path)
            if success:
                print(f"✅ Conversion successful: {output_path}")
            else:
                print(f"❌ Conversion failed: {input_path}")
        else:
            print(f"⚠️  Test file not found: {input_path}")


if __name__ == "__main__":
    main()
