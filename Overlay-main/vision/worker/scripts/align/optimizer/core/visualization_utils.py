import cv2
import matplotlib.pyplot as plt


def show_image(image, title):
    plt.figure(figsize=(10, 10))
    plt.imshow(image)
    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    plt.show()


def show_side_by_side(img1, img2, cmap=None, img1_title="Old Image", img2_title="New Image"):
    """Display old and new images side by side for comparison"""
    plt.figure(figsize=(20, 10))
    plt.subplot(1, 2, 1)
    plt.imshow(img1, cmap=cmap)
    plt.title(img1_title)
    plt.axis("off")
    plt.subplot(1, 2, 2)
    plt.imshow(img2, cmap=cmap)
    plt.title(img2_title)
    plt.axis("off")
    plt.tight_layout()
    plt.show()


def show_matched_features(img1, img2, kp1, kp2, matches, mask=None, limit=50):
    """Visualize matched features between two images"""
    # Filter matches based on mask if provided (inliers only)
    if mask is not None:
        filtered_matches = [matches[i] for i in range(len(matches)) if mask[i]]
        print(
            f"Visualizing {len(filtered_matches)} inlier matches out of {len(matches)} total matches"
        )
    else:
        filtered_matches = matches
        print(f"Visualizing all {len(filtered_matches)} matches")

    # Draw matches
    img_matches = cv2.drawMatches(
        img1,
        kp1,
        img2,
        kp2,
        filtered_matches[:limit],
        None,
        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
    )

    # Display the result
    plt.figure(figsize=(20, 10))
    plt.imshow(img_matches)
    plt.title(f"Feature Matches (showing top 50 out of {len(filtered_matches)} matches)")
    plt.axis("off")
    plt.tight_layout()
    plt.show()
