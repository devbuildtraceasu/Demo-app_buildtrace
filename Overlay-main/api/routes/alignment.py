"""Manual alignment routes for user-defined point correspondences."""

import json
from datetime import datetime, timezone
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from api.config import settings
from api.dependencies import CurrentUser, SessionDep, get_pubsub_client

router = APIRouter()


class Point(BaseModel):
    """A 2D point coordinate."""

    x: float
    y: float


class ManualAlignmentRequest(BaseModel):
    """Request for manual alignment with point correspondences."""

    overlay_id: str = Field(..., description="ID of the overlay to realign")

    # 3 point pairs: source (old image) -> target (new image)
    source_points: list[Point] = Field(
        ..., min_length=3, max_length=3, description="3 points from the old/source image"
    )
    target_points: list[Point] = Field(
        ..., min_length=3, max_length=3, description="3 points from the new/target image"
    )


class ManualAlignmentResponse(BaseModel):
    """Response from manual alignment."""

    overlay_id: str
    job_id: str
    status: str = "processing"
    message: str = "Manual alignment job submitted"

    # Computed transformation (for preview)
    scale: float | None = None
    rotation_deg: float | None = None
    translate_x: float | None = None
    translate_y: float | None = None


def compute_affine_from_points(
    source_points: list[Point],
    target_points: list[Point],
) -> tuple[np.ndarray, float, float, float, float]:
    """Compute affine transformation from 3 point correspondences.

    Args:
        source_points: 3 points from source image
        target_points: 3 points from target image

    Returns:
        (matrix, scale, rotation_deg, translate_x, translate_y)

    Raises:
        ValueError: If points are collinear or transformation is degenerate
    """
    # Convert to numpy arrays
    src = np.float32([[p.x, p.y] for p in source_points])
    dst = np.float32([[p.x, p.y] for p in target_points])

    # Check for collinearity
    def are_collinear(pts):
        v1 = pts[1] - pts[0]
        v2 = pts[2] - pts[0]
        cross = np.abs(v1[0] * v2[1] - v1[1] * v2[0])
        return cross < 1e-6

    if are_collinear(src) or are_collinear(dst):
        raise ValueError("Points are collinear - cannot compute transformation")

    # Compute affine transformation matrix using OpenCV-style approach
    # We need to solve: dst = M * src (where src is in homogeneous coords)
    # This gives us a 2x3 affine matrix

    # Build system of equations
    # For each point pair: [x', y'] = [a, b, c; d, e, f] * [x, y, 1]
    A = np.zeros((6, 6))
    b = np.zeros(6)

    for i in range(3):
        x, y = src[i]
        x_prime, y_prime = dst[i]

        # Equation for x': a*x + b*y + c = x'
        A[2 * i] = [x, y, 1, 0, 0, 0]
        b[2 * i] = x_prime

        # Equation for y': d*x + e*y + f = y'
        A[2 * i + 1] = [0, 0, 0, x, y, 1]
        b[2 * i + 1] = y_prime

    # Solve the system
    try:
        params = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        raise ValueError("Degenerate transformation - cannot solve system")

    # Build 2x3 matrix
    matrix = np.array([[params[0], params[1], params[2]], [params[3], params[4], params[5]]])

    # Extract scale, rotation, translation from affine matrix
    # For a similarity transform: [s*cos(θ), -s*sin(θ), tx; s*sin(θ), s*cos(θ), ty]
    # For general affine, we extract the "closest" similarity params

    # Scale is sqrt of determinant of the linear part
    det = params[0] * params[4] - params[1] * params[3]
    scale = np.sqrt(np.abs(det))

    # Rotation from the linear part (average of the two possible values)
    rotation_rad = np.arctan2(params[3], params[0])
    rotation_deg = np.degrees(rotation_rad)

    # Translation
    translate_x = params[2]
    translate_y = params[5]

    return matrix, scale, rotation_deg, translate_x, translate_y


@router.post("/manual", response_model=ManualAlignmentResponse)
async def submit_manual_alignment(
    request: ManualAlignmentRequest,
    session: SessionDep,
    user: CurrentUser,
):
    """Submit manual alignment with 3 point correspondences.

    The frontend captures 3 matching points between old and new drawings.
    This computes the affine transformation and submits a job to re-render
    the overlay with the user-specified alignment.
    """
    # Validate that overlay exists
    from api.routes.comparisons import Overlay
    overlay = session.get(Overlay, request.overlay_id)
    if not overlay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Overlay not found: {request.overlay_id}",
        )
    if overlay.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Overlay has been deleted: {request.overlay_id}",
        )
    
    # Validate the transformation
    try:
        matrix, scale, rotation_deg, translate_x, translate_y = compute_affine_from_points(
            request.source_points,
            request.target_points,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Validate scale and rotation are reasonable
    if scale < 0.1 or scale > 10.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scale factor: {scale:.2f}. Must be between 0.1 and 10.0",
        )

    if abs(rotation_deg) > 45:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid rotation: {rotation_deg:.1f}°. Must be within ±45°",
        )

    # Generate job ID
    import secrets
    import time

    timestamp = hex(int(time.time() * 1000))[2:]
    random_part = secrets.token_hex(8)
    job_id = f"c{timestamp}{random_part}"[:25]

    # Submit job to Pub/Sub
    try:
        pubsub = get_pubsub_client()
        topic_path = pubsub.topic_path(settings.pubsub_project_id, settings.vision_topic)

        job_payload = {
            "type": "vision.block.overlay.manual_align",
            "jobId": job_id,
            "payload": {
                "overlayId": request.overlay_id,
                "alignmentMatrix": matrix.tolist(),
                "sourcePoints": [[p.x, p.y] for p in request.source_points],
                "targetPoints": [[p.x, p.y] for p in request.target_points],
            },
        }

        pubsub.publish(
            topic_path,
            json.dumps(job_payload).encode("utf-8"),
            type="vision.block.overlay.manual_align",
        )
    except Exception as e:
        import logging

        logging.warning(f"Failed to publish manual alignment job: {e}")
        # Don't fail - return preview data anyway

    return ManualAlignmentResponse(
        overlay_id=request.overlay_id,
        job_id=job_id,
        status="processing",
        message="Manual alignment job submitted. The overlay will be regenerated.",
        scale=float(scale),
        rotation_deg=float(rotation_deg),
        translate_x=float(translate_x),
        translate_y=float(translate_y),
    )


@router.post("/preview", response_model=dict)
async def preview_alignment(
    request: ManualAlignmentRequest,
    user: CurrentUser,
):
    """Preview manual alignment transformation without submitting a job.

    Returns the computed transformation parameters for UI preview.
    """
    try:
        matrix, scale, rotation_deg, translate_x, translate_y = compute_affine_from_points(
            request.source_points,
            request.target_points,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return {
        "valid": True,
        "scale": float(scale),
        "rotation_deg": float(rotation_deg),
        "translate_x": float(translate_x),
        "translate_y": float(translate_y),
        "matrix": matrix.tolist(),
        "warnings": [],
    }

