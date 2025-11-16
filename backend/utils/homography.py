import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class HomographyCalibrator:
    """
    Camera calibration using homography matrix
    Transforms coordinates from camera view to map (bird's eye) view
    """
    
    def __init__(self):
        self.matrix: Optional[np.ndarray] = None
        self.inv_matrix: Optional[np.ndarray] = None
        self.camera_points: Optional[np.ndarray] = None
        self.map_points: Optional[np.ndarray] = None
        self.reprojection_error: float = 0.0
    
    def calibrate(
        self,
        camera_points: List[Tuple[float, float]],
        map_points: List[Tuple[float, float]],
        method: int = cv2.RANSAC
    ) -> bool:
        """
        Compute homography matrix from point correspondences
        
        Args:
            camera_points: List of (x, y) points in camera coordinates
            map_points: List of (x, y) points in map coordinates
            method: OpenCV method (cv2.RANSAC, cv2.LMEDS, or 0 for exact)
            
        Returns:
            True if calibration successful
        """
        if len(camera_points) < 4 or len(map_points) < 4:
            logger.error("Need at least 4 point correspondences for homography")
            return False
        
        if len(camera_points) != len(map_points):
            logger.error("Number of camera and map points must match")
            return False
        
        try:
            self.camera_points = np.array(camera_points, dtype=np.float32)
            self.map_points = np.array(map_points, dtype=np.float32)
            
            # Compute homography
            if len(camera_points) == 4 and method == 0:
                # Exact solution for 4 points
                self.matrix, _ = cv2.findHomography(
                    self.camera_points,
                    self.map_points,
                    method=0
                )
            else:
                # RANSAC for more than 4 points
                self.matrix, mask = cv2.findHomography(
                    self.camera_points,
                    self.map_points,
                    method=method,
                    ransacReprojThreshold=5.0
                )
            
            if self.matrix is None:
                logger.error("Failed to compute homography matrix")
                return False
            
            # Compute inverse matrix
            self.inv_matrix = np.linalg.inv(self.matrix)
            
            # Calculate reprojection error
            self.reprojection_error = self._calculate_reprojection_error()
            
            logger.info(f"Homography calibration successful. Reprojection error: {self.reprojection_error:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Calibration error: {e}")
            return False
    
    def _calculate_reprojection_error(self) -> float:
        """Calculate average reprojection error"""
        if self.matrix is None or self.camera_points is None or self.map_points is None:
            return float('inf')
        
        # Transform camera points to map coordinates
        transformed = cv2.perspectiveTransform(
            self.camera_points.reshape(-1, 1, 2),
            self.matrix
        ).reshape(-1, 2)
        
        # Calculate Euclidean distance
        errors = np.linalg.norm(transformed - self.map_points, axis=1)
        return float(np.mean(errors))
    
    def transform_point(
        self,
        point: Tuple[float, float],
        inverse: bool = False
    ) -> Optional[Tuple[float, float]]:
        """
        Transform a single point
        
        Args:
            point: (x, y) coordinates
            inverse: If True, transform from map to camera coordinates
            
        Returns:
            Transformed (x, y) or None if not calibrated
        """
        if self.matrix is None:
            logger.warning("Homography matrix not computed")
            return None
        
        try:
            pt = np.array([[point]], dtype=np.float32)
            matrix = self.inv_matrix if inverse else self.matrix
            transformed = cv2.perspectiveTransform(pt, matrix)
            return tuple(transformed[0][0].tolist())
        except Exception as e:
            logger.error(f"Point transformation error: {e}")
            return None
    
    def transform_points(
        self,
        points: List[Tuple[float, float]],
        inverse: bool = False
    ) -> Optional[List[Tuple[float, float]]]:
        """
        Transform multiple points
        
        Args:
            points: List of (x, y) coordinates
            inverse: If True, transform from map to camera coordinates
            
        Returns:
            List of transformed (x, y) or None if not calibrated
        """
        if self.matrix is None:
            logger.warning("Homography matrix not computed")
            return None
        
        if len(points) == 0:
            return []
        
        try:
            pts = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
            matrix = self.inv_matrix if inverse else self.matrix
            transformed = cv2.perspectiveTransform(pts, matrix)
            return [tuple(pt[0].tolist()) for pt in transformed]
        except Exception as e:
            logger.error(f"Points transformation error: {e}")
            return None
    
    def transform_bbox(
        self,
        bbox: Tuple[float, float, float, float],
        inverse: bool = False
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Transform bounding box
        
        Args:
            bbox: (x1, y1, x2, y2) coordinates
            inverse: If True, transform from map to camera coordinates
            
        Returns:
            Transformed (x1, y1, x2, y2) or None if not calibrated
        """
        x1, y1, x2, y2 = bbox
        
        # Transform all 4 corners
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        transformed_corners = self.transform_points(corners, inverse)
        
        if transformed_corners is None:
            return None
        
        # Get bounding box of transformed corners
        xs = [pt[0] for pt in transformed_corners]
        ys = [pt[1] for pt in transformed_corners]
        
        return (min(xs), min(ys), max(xs), max(ys))
    
    def transform_polygon(
        self,
        polygon: List[Tuple[float, float]],
        inverse: bool = False
    ) -> Optional[List[Tuple[float, float]]]:
        """
        Transform polygon points
        
        Args:
            polygon: List of (x, y) coordinates
            inverse: If True, transform from map to camera coordinates
            
        Returns:
            Transformed polygon or None if not calibrated
        """
        return self.transform_points(polygon, inverse)
    
    def get_matrix(self) -> Optional[np.ndarray]:
        """Get homography matrix"""
        return self.matrix
    
    def get_matrix_list(self) -> Optional[List[List[float]]]:
        """Get homography matrix as list (for JSON serialization)"""
        if self.matrix is None:
            return None
        return self.matrix.tolist()
    
    def set_matrix(self, matrix: List[List[float]]) -> bool:
        """
        Set homography matrix from list
        
        Args:
            matrix: 3x3 matrix as list of lists
            
        Returns:
            True if matrix is valid
        """
        try:
            self.matrix = np.array(matrix, dtype=np.float32)
            if self.matrix.shape != (3, 3):
                logger.error("Matrix must be 3x3")
                return False
            
            self.inv_matrix = np.linalg.inv(self.matrix)
            logger.info("Homography matrix loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to set matrix: {e}")
            return False
    
    def visualize_calibration(
        self,
        camera_image: np.ndarray,
        map_image: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Visualize calibration points on images
        
        Args:
            camera_image: Camera frame
            map_image: Map/schema image
            
        Returns:
            (annotated_camera_image, annotated_map_image)
        """
        cam_vis = camera_image.copy()
        map_vis = map_image.copy()
        
        if self.camera_points is not None and self.map_points is not None:
            for i, (cam_pt, map_pt) in enumerate(zip(self.camera_points, self.map_points)):
                # Draw on camera image
                cv2.circle(cam_vis, tuple(cam_pt.astype(int)), 8, (0, 255, 0), -1)
                cv2.putText(cam_vis, str(i+1), tuple(cam_pt.astype(int) + 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # Draw on map image
                cv2.circle(map_vis, tuple(map_pt.astype(int)), 8, (0, 0, 255), -1)
                cv2.putText(map_vis, str(i+1), tuple(map_pt.astype(int) + 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return cam_vis, map_vis
    
    def get_calibration_quality(self) -> str:
        """
        Get calibration quality assessment
        
        Returns:
            Quality string: 'excellent', 'good', 'acceptable', 'poor', or 'not_calibrated'
        """
        if self.matrix is None:
            return 'not_calibrated'
        
        if self.reprojection_error < 5:
            return 'excellent'
        elif self.reprojection_error < 10:
            return 'good'
        elif self.reprojection_error < 20:
            return 'acceptable'
        else:
            return 'poor'
