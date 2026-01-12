import re

import cv2
import numpy as np
import pymupdf
import pypdfium2

from .color_utils import cmyk_to_tinted, gray_to_tinted, rgb_to_tinted


def load_pdf_document(path: str) -> pymupdf.Document:
    """Load a PDF document."""
    return pymupdf.open(path)


def save_pdf_document(doc: pymupdf.Document, output_path: str):
    """Save a PDF document to a file."""
    doc.save(output_path)


def load_pdf_page(path: str, page_number: int = 0) -> pymupdf.Page:
    """Load a specific page from a PDF document."""
    doc = pymupdf.open(path)
    if page_number >= len(doc):
        raise ValueError(f"Page {page_number} not found in PDF {path} (has {len(doc)} pages)")
    page = doc.load_page(page_number)
    return page


def save_pdf_page(page: pymupdf.Page, output_path: str):
    """Save a single PDF page to a file."""
    page.parent.save(output_path)


def load_pdf_page_as_image(path: str, page_number: int = 0, dpi: int = 72) -> np.ndarray:
    pdf = pypdfium2.PdfDocument(path)
    if page_number >= len(pdf):
        raise ValueError(f"Page {page_number} not found in PDF {path} (has {len(pdf)} pages)")
    page = pdf.get_page(page_number)
    bitmap = page.render(scale=dpi / 72.0)
    img = bitmap.to_numpy()
    page.close()
    pdf.close()
    return img


def pdf_page_to_image(page: pymupdf.Page, dpi: int = 72) -> np.ndarray:
    # Create a transformation matrix for the desired DPI
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)

    # Convert pixmap to numpy array
    img_data = pix.tobytes("ppm")
    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img


def transform_pdf_page(
    page: pymupdf.Page, cv_matrix: np.ndarray, target_size: tuple
) -> pymupdf.Page:
    """
    Transforms all vector objects on a PDF page using a given affine matrix.

    This function correctly applies the transformation by pre-calculating a new
    matrix that accounts for the difference between the PDF coordinate system
    (origin at bottom-left, y-axis up) and the OpenCV coordinate system (origin
    at top-left, y-axis down).

    Args:
        page: The pymupdf.Page object to be transformed.
        cv_matrix: A 2x3 or 3x3 NumPy array representing the affine transformation
                   matrix from the OpenCV coordinate system.
        target_size: A tuple (width, height) specifying the dimensions of the
                     final page in points.

    Returns:
        A new pymupdf.Page object containing the transformed vector content.
        NOTE: The returned page is part of a new in-memory document. A reference
        to this document is stored in `page.parent_doc` to prevent the page
        from becoming invalid.
    """
    src_doc = page.parent
    dest_doc = pymupdf.open()

    # 1. Create a 1-to-1 copy of the page content in a new document.
    # This gives us a clean slate with original content and coordinates.
    temp_page = dest_doc.new_page(width=page.rect.width, height=page.rect.height)
    temp_page.show_pdf_page(temp_page.rect, src_doc, page.number)

    # 2. Resize the page canvas to the final target size without scaling content. [2]
    temp_page.set_mediabox(pymupdf.Rect(0, 0, target_size[0], target_size[1]))

    # 3. Calculate the coordinate-system-corrected transformation matrix.
    #    This is the crucial step to fix the translation.

    # Original matrix components [a, b, e], [c, d, f]
    m = cv_matrix[:2]
    a, b, e = m[0]
    c, d, f = m[1]

    # Source and target page heights
    H = page.rect.height
    H_target = target_size[1]

    # New matrix components that account for the y-axis flip.
    # This new matrix effectively does:
    #   1. Flip Y-axis from PDF to CV
    #   2. Apply original CV transform
    #   3. Flip Y-axis back from CV to PDF
    a_new = a
    b_new = -b
    c_new = -c
    d_new = d
    e_new = e + b * H
    f_new = H_target - f - d * H

    transform_matrix = pymupdf.Matrix(a_new, b_new, c_new, d_new, e_new, f_new)

    # 4. Prepend the new, corrected transformation to the content stream.
    transform_command = f"{transform_matrix.a:.6f} {transform_matrix.b:.6f} {transform_matrix.c:.6f} {transform_matrix.d:.6f} {transform_matrix.e:.6f} {transform_matrix.f:.6f} cm\n".encode()

    contents_xref = temp_page.get_contents()[0]
    original_contents = dest_doc.xref_stream(contents_xref)

    # Wrap in q/Q to localize the graphics state change
    new_contents = b"q\n" + transform_command + original_contents + b"\nQ"

    dest_doc.update_stream(contents_xref, new_contents)

    # Keep a reference to the parent document to prevent the page from being invalidated.
    temp_page.parent_doc = dest_doc

    return temp_page


def scale_transform(cv_matrix: np.ndarray, source_dpi: float, target_dpi: float = 72) -> np.ndarray:
    scale = target_dpi / source_dpi
    adjusted = cv_matrix.copy()
    adjusted[0, 2] *= scale
    adjusted[1, 2] *= scale
    return adjusted


def create_overlay_pdf(
    old_page: pymupdf.Page, new_page: pymupdf.Page, cv_matrix: np.ndarray
) -> pymupdf.Page:
    """Create an overlay PDF page for visual change detection.

    Visual result:
    - Unchanged content appears gray due to Multiply blending of red over green.
    - Additions appear red; removals appear green.
    - Page backgrounds remain unmodified/transparent.
    """

    apply_transparency_to_page(old_page, alpha=0.5)
    apply_transparency_to_page(new_page, alpha=0.5)

    convert_page_to_tinted(old_page, tint=(0, 0.5, 0.0))  # Green tint for old content
    convert_page_to_tinted(new_page, tint=(0.5, 0, 0.0))  # Red tint for new content

    target_size = (new_page.rect.width, new_page.rect.height)
    old_page = transform_pdf_page(old_page, cv_matrix, target_size)

    # 1) Create overlay page and place both source pages vectorially
    overlay_doc = pymupdf.open()
    overlay_page = overlay_doc.new_page(width=new_page.rect.width, height=new_page.rect.height)
    target_rect = pymupdf.Rect(0, 0, new_page.rect.width, new_page.rect.height)

    # Draw base (old) page first, then top (new). Keep transforms inside page contents.
    overlay_page.show_pdf_page(
        target_rect, old_page.parent, old_page.number, clip=old_page.rect, overlay=True
    )
    overlay_page.show_pdf_page(
        target_rect, new_page.parent, new_page.number, clip=new_page.rect, overlay=True
    )

    return overlay_page


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
        r"[0-9.]+\s+(?:g|G)(?=\s|$|\n|\r)"  # Gray fill/stroke
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


def convert_page_to_tinted(page: pymupdf.Page, tint: tuple):
    """Convert a single page to tinted colors by modifying its content streams."""
    doc = page.parent

    # Get content stream xrefs
    stream_xrefs = get_page_content_streams(page)
    for stream_xref in stream_xrefs:
        original_bytes = doc.xref_stream(stream_xref) or b""
        original_content = original_bytes.decode("latin1", errors="ignore")
        converted_content = convert_stream_to_tinted(original_content, tint)
        new_bytes = converted_content.encode("latin1")
        doc.update_stream(stream_xref, new_bytes)


def apply_transparency_to_page(page: pymupdf.Page, alpha: float):
    """
    Applies transparency to a single page by adding a graphics state
    and prepending the content stream with a command to use it.
    """
    doc = page.parent

    # 1. Create the ExtGState object for transparency
    gstate_xref = doc.get_new_xref()
    gstate_dict = f"<< /Type /ExtGState /ca {alpha} /CA {alpha} >>"
    doc.update_object(gstate_xref, gstate_dict)

    # 2. Add the new graphics state to the page's resources
    # Get the page's resource dictionary
    res_key = doc.xref_get_key(page.xref, "Resources")
    if not res_key or not res_key[1]:  # Should not happen for a normal page
        return

    res_type, res_value = res_key

    if res_type == "dict":
        # Resources is an inline dictionary - parse it to find ExtGState
        res_dict = res_value.strip()

        # Look for ExtGState in the dictionary string - handle both reference and inline cases
        import re

        # First try to find ExtGState as a reference: /ExtGState 123 0 R
        extgstate_ref_match = re.search(r"/ExtGState\s+(\d+)\s+\d+\s+R", res_dict)

        # Also try to find ExtGState as an inline dictionary: /ExtGState<<...>>
        extgstate_inline_match = re.search(r"/ExtGState\s*<<([^>]*)>>", res_dict)

        if extgstate_ref_match:
            # ExtGState reference exists, modify the referenced object
            extgstate_xref = int(extgstate_ref_match.group(1))

            # Get the existing ExtGState dictionary content
            existing_keys = doc.xref_get_keys(extgstate_xref)
            existing_dict_parts = []
            for key in existing_keys:
                value = doc.xref_get_key(extgstate_xref, key)[1]
                existing_dict_parts.append(f"/{key} {value}")

            # Add our new graphics state
            existing_dict_parts.append(f"/gsT {gstate_xref} 0 R")
            new_dict = f"<< {' '.join(existing_dict_parts)} >>"
            doc.update_object(extgstate_xref, new_dict)

        elif extgstate_inline_match:
            # ExtGState is inline, need to add our graphics state to it
            inline_content = extgstate_inline_match.group(1)
            new_inline_content = f"{inline_content}/gsT {gstate_xref} 0 R"

            # Replace the ExtGState inline dictionary in the resources
            new_extgstate = f"/ExtGState<<{new_inline_content}>>"
            new_res_dict = res_dict.replace(extgstate_inline_match.group(0), new_extgstate)
            doc.xref_set_key(page.xref, "Resources", new_res_dict)

        else:
            # No ExtGState in resources, need to add one
            # Create a new ExtGState object
            extgstate_obj_xref = doc.get_new_xref()
            extgstate_obj_dict = f"<< /gsT {gstate_xref} 0 R >>"
            doc.update_object(extgstate_obj_xref, extgstate_obj_dict)

            # Update the resources dictionary to include the new ExtGState
            if res_dict.startswith("<<") and res_dict.endswith(">>"):
                # Remove the outer brackets and add the new ExtGState
                inner_dict = res_dict[2:-2].strip()
                if inner_dict:
                    new_res_dict = f"<< {inner_dict} /ExtGState {extgstate_obj_xref} 0 R >>"
                else:
                    new_res_dict = f"<< /ExtGState {extgstate_obj_xref} 0 R >>"
                doc.xref_set_key(page.xref, "Resources", new_res_dict)

    elif res_type == "xref":
        # Resources is a reference to another object
        res_obj_xref = int(res_value.split()[0])

        # Check if the resource object has an ExtGState key
        extgstate_key = doc.xref_get_key(res_obj_xref, "ExtGState")

        if extgstate_key and extgstate_key[1] and extgstate_key[1].strip() != "null":
            # ExtGState exists as a reference
            if extgstate_key[0] == "xref":
                extgstate_xref = int(extgstate_key[1].split()[0])

                # Add our graphics state to the existing ExtGState object
                doc.xref_set_key(extgstate_xref, "gsT", f"{gstate_xref} 0 R")
            else:
                # ExtGState is an inline dictionary - shouldn't happen but handle it
                print(f"Warning: Unexpected ExtGState type: {extgstate_key[0]}")
        else:
            # No ExtGState, create one and add it to the resource object
            extgstate_obj_xref = doc.get_new_xref()
            extgstate_obj_dict = f"<< /gsT {gstate_xref} 0 R >>"
            doc.update_object(extgstate_obj_xref, extgstate_obj_dict)

            # Add the ExtGState reference to the resource object
            doc.xref_set_key(res_obj_xref, "ExtGState", f"{extgstate_obj_xref} 0 R")

    # 3. Prepend the content stream(s) with the command to use the graphics state
    stream_xrefs = get_page_content_streams(page)
    for stream_xref in stream_xrefs:
        original_bytes = doc.xref_stream(stream_xref) or b""
        new_bytes = b"/gsT gs\n" + original_bytes
        doc.update_stream(stream_xref, new_bytes)
