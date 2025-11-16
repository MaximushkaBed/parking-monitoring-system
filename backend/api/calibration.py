from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel
from typing import List
import cv2
import numpy as np
import base64

from backend.utils.homography import HomographyCalibrator

router = APIRouter()


class CalibrationPoints(BaseModel):
    camera_points: List[List[float]]  # [[x1,y1], [x2,y2], ...]
    map_points: List[List[float]]  # [[x1,y1], [x2,y2], ...]


@router.post("/{camera_id}/calibrate")
async def calibrate_camera(
    camera_id: int,
    points: CalibrationPoints,
    request: Request
):
    """
    Calibrate camera using point correspondences
    
    Requires at least 4 point pairs (camera coordinates -> map coordinates)
    """
    if len(points.camera_points) < 4 or len(points.map_points) < 4:
        raise HTTPException(
            status_code=400,
            detail="Need at least 4 point correspondences"
        )
    
    if len(points.camera_points) != len(points.map_points):
        raise HTTPException(
            status_code=400,
            detail="Number of camera and map points must match"
        )
    
    # Create calibrator
    calibrator = HomographyCalibrator()
    
    # Compute homography
    success = calibrator.calibrate(
        camera_points=[(p[0], p[1]) for p in points.camera_points],
        map_points=[(p[0], p[1]) for p in points.map_points]
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to compute homography matrix"
        )
    
    # Get matrix
    matrix = calibrator.get_matrix_list()
    reprojection_error = calibrator.reprojection_error
    quality = calibrator.get_calibration_quality()
    
    # In production, save matrix to database
    # Update pipeline with new matrix
    pipeline_manager = request.app.state.pipeline_manager
    pipeline = pipeline_manager.get_pipeline(camera_id)
    
    if pipeline:
        pipeline.set_homography_matrix(matrix)
    
    return {
        "camera_id": camera_id,
        "matrix": matrix,
        "reprojection_error": reprojection_error,
        "quality": quality,
        "message": "Calibration successful"
    }


@router.get("/{camera_id}/calibration")
async def get_calibration(camera_id: int):
    """Get current calibration matrix for camera"""
    # In production, fetch from database
    return {
        "camera_id": camera_id,
        "matrix": None,
        "calibrated": False
    }


@router.post("/{camera_id}/test-transform")
async def test_transform(
    camera_id: int,
    point: List[float],  # [x, y]
    request: Request
):
    """Test homography transformation on a point"""
    pipeline_manager = request.app.state.pipeline_manager
    pipeline = pipeline_manager.get_pipeline(camera_id)
    
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    if pipeline.homography.get_matrix() is None:
        raise HTTPException(status_code=400, detail="Camera not calibrated")
    
    # Transform point
    transformed = pipeline.homography.transform_point((point[0], point[1]))
    
    if transformed is None:
        raise HTTPException(status_code=500, detail="Transformation failed")
    
    return {
        "camera_point": point,
        "map_point": list(transformed)
    }
