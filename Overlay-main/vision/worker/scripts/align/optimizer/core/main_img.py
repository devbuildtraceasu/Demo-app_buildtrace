import argparse

from .image_aligner import ImageAligner
from .image_utils import create_overlay_image, load_image, save_image, transform_image
from .pdf_utils import load_pdf_page_as_image
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

    if args.old_path.lower().endswith(".pdf"):
        old_img = load_pdf_page_as_image(args.old_path)
    else:
        old_img = load_image(args.old_path)

    if args.new_path.lower().endswith(".pdf"):
        new_img = load_pdf_page_as_image(args.new_path)
    else:
        new_img = load_image(args.new_path)

    # Estimate transformation matrix using images
    matrix = ImageAligner(debug=args.debug)(old_img, new_img)

    # Apply transformation to old image
    if args.aligned_path:
        target_size = (new_img.shape[1], new_img.shape[0])
        transformed_img = transform_image(old_img, matrix, target_size)
        save_image(transformed_img, args.aligned_path)
        print(f"Aligned image saved to: {args.aligned_path}")

    # Create image overlay for visualization
    overlay_img = create_overlay_image(old_img, new_img, matrix)
    if args.overlay_path:
        save_image(overlay_img, args.overlay_path)
        print(f"Overlay image saved to: {args.overlay_path}")
    if args.show_overlay:
        show_image(overlay_img, "Overlay (Green=Old, Red=New) after alignment")


if __name__ == "__main__":
    main()
