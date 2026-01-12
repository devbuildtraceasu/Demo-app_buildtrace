import cv2
import numpy as np
import scipy.optimize


def estimate_affine_partial_2d_constrained(
    from_points,
    to_points,
    ransac_reproj_threshold=3.0,
    max_iters=2000,
    confidence=0.99,
    scale_min=None,
    scale_max=None,
    rotation_deg_min=None,
    rotation_deg_max=None,
):
    """
    Estimates a partial 2D affine transformation between two sets of points using RANSAC
    with optional constraints on scale and rotation. It sorts all valid hypotheses and
    applies a constrained optimizer to them sequentially.

    Args:
        from_points (np.ndarray): Source points, shape (N, 2).
        to_points (np.ndarray): Destination points, shape (N, 2).
        ransac_reproj_threshold (float): RANSAC reprojection threshold.
        max_iters (int): The maximum number of RANSAC iterations.
        confidence (float): The confidence level for dynamically adapting iterations.
        scale_min (float, optional): The minimum allowed scale.
        scale_max (float, optional): The maximum allowed scale.
        rotation_deg_min (float, optional): The minimum allowed rotation in degrees.
        rotation_deg_max (float, optional): The maximum allowed rotation in degrees.

    Returns:
        tuple[np.ndarray, np.ndarray]:
            - The resulting 2x3 affine transformation matrix (or None if failed).
            - An inlier mask, a column vector of shape (N, 1) where inliers are 1.
    """
    num_points = from_points.shape[0]
    if num_points < 2:
        return None, None

    rot_rad_min = np.deg2rad(rotation_deg_min) if rotation_deg_min is not None else -np.inf
    rot_rad_max = np.deg2rad(rotation_deg_max) if rotation_deg_max is not None else np.inf

    hypotheses = []
    best_inlier_count = -1

    from_points_hom = np.hstack([from_points, np.ones((num_points, 1))])

    for _ in range(max_iters):
        # 1. Randomly sample 2 points
        sample_indices = np.random.choice(num_points, 2, replace=False)
        p1, p2 = from_points[sample_indices]
        q1, q2 = to_points[sample_indices]

        # 2. Compute a candidate model
        v_from, v_to = p2 - p1, q2 - q1
        len_from = np.linalg.norm(v_from)
        if np.isclose(len_from, 0):
            continue

        # a. Check scale constraint
        scale = np.linalg.norm(v_to) / len_from
        if (scale_min is not None and scale < scale_min) or (
            scale_max is not None and scale > scale_max
        ):
            continue

        # b. Check rotation constraint
        angle_from = np.arctan2(v_from[1], v_from[0])
        angle_to = np.arctan2(v_to[1], v_to[0])
        theta = angle_to - angle_from
        if not (
            rot_rad_min <= theta <= rot_rad_max
            or rot_rad_min <= theta + 2 * np.pi <= rot_rad_max
            or rot_rad_min <= theta - 2 * np.pi <= rot_rad_max
        ):
            continue

        # c. Form the candidate matrix
        cos_theta, sin_theta = np.cos(theta), np.sin(theta)
        tx = q1[0] - (p1[0] * scale * cos_theta - p1[1] * scale * sin_theta)
        ty = q1[1] - (p1[0] * scale * sin_theta + p1[1] * scale * cos_theta)
        m_candidate = np.array(
            [
                [scale * cos_theta, -scale * sin_theta, tx],
                [scale * sin_theta, scale * cos_theta, ty],
            ]
        )

        # 3. Count inliers
        transformed_points = (m_candidate @ from_points_hom.T).T
        errors = np.linalg.norm(to_points - transformed_points, axis=1)
        current_inlier_mask = errors < ransac_reproj_threshold
        current_inlier_count = np.sum(current_inlier_mask)

        # 4. Store the hypothesis
        hypotheses.append((current_inlier_count, current_inlier_mask))

        # 5. Update best model for dynamic iteration count
        if current_inlier_count > best_inlier_count:
            best_inlier_count = current_inlier_count
            # Dynamically update max_iters
            inlier_ratio = current_inlier_count / num_points
            if inlier_ratio > 0:
                new_max_iters = int(np.log(1 - confidence) / np.log(1 - inlier_ratio**2))
                if new_max_iters < max_iters:
                    max_iters = new_max_iters

    # 6. Sort hypotheses by inlier count in descending order
    hypotheses.sort(key=lambda x: x[0], reverse=True)

    # 7. Final Model Refinement by iterating through sorted hypotheses
    for _, inlier_mask in hypotheses:
        from_inliers = from_points[inlier_mask]
        to_inliers = to_points[inlier_mask]

        try:
            final_matrix = _run_constrained_optimizer(
                from_inliers, to_inliers, scale_min, scale_max, rotation_deg_min, rotation_deg_max
            )
            final_mask = inlier_mask.astype(np.uint8).reshape(-1, 1)
            return final_matrix, final_mask
        except RuntimeError:
            pass

    raise RuntimeError("All optimization attempts failed.")


def _run_constrained_optimizer(
    from_points,
    to_points,
    scale_min=None,
    scale_max=None,
    rotation_deg_min=None,
    rotation_deg_max=None,
):
    """Helper function to run the constrained optimization on a set of points."""
    if from_points.shape[0] < 2:
        raise RuntimeError("At least 2 points are required for optimization.")

    def objective_func(params):
        scale, theta_rad, tx, ty = params
        cos_theta, sin_theta = np.cos(theta_rad), np.sin(theta_rad)
        m = np.array(
            [
                [scale * cos_theta, -scale * sin_theta, tx],
                [scale * sin_theta, scale * cos_theta, ty],
            ]
        )
        from_points_hom = np.hstack([from_points, np.ones((from_points.shape[0], 1))])
        transformed_points = (m @ from_points_hom.T).T
        return np.sum((to_points - transformed_points) ** 2)

    initial_m, _ = cv2.estimateAffinePartial2D(from_points, to_points)
    if initial_m is not None:
        s_init = np.sqrt(initial_m[0, 0] ** 2 + initial_m[1, 0] ** 2)
        theta_rad_init = np.arctan2(initial_m[1, 0], initial_m[0, 0])
        tx_init, ty_init = initial_m[0, 2], initial_m[1, 2]
    else:
        s_init, theta_rad_init = 1.0, 0.0
        tx_init = np.mean(to_points[:, 0] - from_points[:, 0])
        ty_init = np.mean(to_points[:, 1] - from_points[:, 1])

    initial_guess = [s_init, theta_rad_init, tx_init, ty_init]
    rotation_rad_min = np.deg2rad(rotation_deg_min) if rotation_deg_min is not None else -np.inf
    rotation_rad_max = np.deg2rad(rotation_deg_max) if rotation_deg_max is not None else np.inf
    bounds = [
        (scale_min, scale_max),
        (rotation_rad_min, rotation_rad_max),
        (None, None),
        (None, None),
    ]

    result = scipy.optimize.minimize(
        objective_func, initial_guess, bounds=bounds, method="L-BFGS-B"
    )

    if not result.success:
        raise RuntimeError("Optimization failed: " + result.message)

    scale_opt, theta_rad_opt, tx_opt, ty_opt = result.x
    cos_opt, sin_opt = np.cos(theta_rad_opt), np.sin(theta_rad_opt)
    return np.array(
        [
            [scale_opt * cos_opt, -scale_opt * sin_opt, tx_opt],
            [scale_opt * sin_opt, scale_opt * cos_opt, ty_opt],
        ]
    )
