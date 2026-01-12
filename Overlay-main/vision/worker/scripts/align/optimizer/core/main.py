import argparse

from .image_aligner import ImageAligner
from .pdf_utils import (
    create_overlay_pdf,
    load_pdf_page,
    load_pdf_page_as_image,
    pdf_page_to_image,
    save_pdf_page,
    transform_pdf_page,
)
from .visualization_utils import show_image


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Align drawings by comparing old and new PDF versions"
    )
    parser.add_argument("--old_path", help="Old PDF path.", required=True)
    parser.add_argument("--new_path", help="New PDF path.", required=True)
    parser.add_argument(
        "--show_overlay", action="store_true", help="Show overlay image after alignment."
    )
    parser.add_argument(
        "--aligned_path", help="Optional path to save the aligned old PDF.", default=None
    )
    parser.add_argument(
        "--overlay_path", help="Optional path to save the overlayed image.", default=None
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode to visualize matched features."
    )
    args = parser.parse_args()

    # Load PDF documents and pages
    old_page = load_pdf_page(args.old_path)
    new_page = load_pdf_page(args.new_path)

    # Convert pages to images for matrix estimation only
    old_img = load_pdf_page_as_image(args.old_path)
    new_img = load_pdf_page_as_image(args.new_path)

    # Estimate transformation matrix using images
    matrix = ImageAligner(debug=args.debug)(old_img, new_img)

    # Apply transformation to old PDF page directly
    if args.aligned_path:
        target_size = (new_page.rect.width, new_page.rect.height)
        transformed_page = transform_pdf_page(old_page, matrix, target_size)
        save_pdf_page(transformed_page, args.aligned_path)
        print(f"Aligned PDF saved to: {args.aligned_path}")

    # Create image overlay for visualization
    overlay_page = create_overlay_pdf(old_page, new_page, matrix)
    if args.overlay_path:
        save_pdf_page(overlay_page, args.overlay_path)
        print(f"Overlay PDF saved to: {args.overlay_path}")
    if args.show_overlay:
        overlay_img = pdf_page_to_image(overlay_page)
        show_image(overlay_img, "Overlay (Green=Old, Red=New) after alignment")


if __name__ == "__main__":
    main()
