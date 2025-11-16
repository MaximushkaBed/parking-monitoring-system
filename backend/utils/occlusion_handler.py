"""
Occlusion handling module
Improves detection accuracy when vehicles overlap or are partially hidden
"""

import numpy as np
from shapely.geometry import Polygon, Point
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import cv2
import logging

logger = logging.getLogger(__name__)


@dataclass
class OcclusionInfo:
    """Information about occlusion between two vehicles"""
    occluder_id: int  # Vehicle in front
    occluded_id: int  # Vehicle behind
    occlusion_ratio: float  # How much of occluded vehicle is hidden (0-1)
    overlap_area: float
    depth_order: int  # Estimated depth (lower = closer to camera)


class OcclusionHandler:
    """
    Handles vehicle occlusions using instance segmentation
    
    Features:
    - Detect overlapping vehicles
    - Estimate depth ordering
    - Recover partially occluded vehicles
    - Adjust confidence scores
    - Handle perspective effects
    """
    
    def __init__(
        self,
        min_occlusion_ratio: float = 0.1,  # Minimum overlap to consider occlusion
        depth_estimation_method: str = "centroid_y"  # centroid_y, area, perspective
    ):
        """
        Initialize occlusion handler
        
        Args:
            min_occlusion_ratio: Minimum occlusion ratio to track
            depth_estimation_method: Method for depth ordering
        """
        self.min_occlusion_ratio = min_occlusion_ratio
        self.depth_estimation_method = depth_estimation_method
        
        self.occlusion_history: Dict[Tuple[int, int], List[float]] = {}
    
    def detect_occlusions(
        self,
        detections: List[Dict]
    ) -> List[OcclusionInfo]:
        """
        Detect occlusions between vehicles
        
        Args:
            detections: List of vehicle detections with masks/polygons
            
        Returns:
            List of occlusion information
        """
        occlusions = []
        
        # Sort by depth (closer vehicles first)
        sorted_detections = self._sort_by_depth(detections)
        
        for i, det1 in enumerate(sorted_detections):
            poly1 = self._get_polygon(det1)
            if poly1 is None:
                continue
            
            for det2 in sorted_detections[i+1:]:
                poly2 = self._get_polygon(det2)
                if poly2 is None:
                    continue
                
                # Check if polygons overlap
                if not poly1.intersects(poly2):
                    continue
                
                # Calculate occlusion
                intersection = poly1.intersection(poly2)
                overlap_area = intersection.area
                
                # Determine which vehicle is occluding
                # Vehicle closer to camera (lower depth) occludes the other
                occluder_id = det1['track_id']
                occluded_id = det2['track_id']
                
                # Occlusion ratio relative to occluded vehicle
                occluded_area = poly2.area
                occlusion_ratio = overlap_area / occluded_area if occluded_area > 0 else 0
                
                if occlusion_ratio >= self.min_occlusion_ratio:
                    occlusion = OcclusionInfo(
                        occluder_id=occluder_id,
                        occluded_id=occluded_id,
                        occlusion_ratio=occlusion_ratio,
                        overlap_area=overlap_area,
                        depth_order=i
                    )
                    
                    occlusions.append(occlusion)
                    
                    # Track occlusion history
                    key = (occluder_id, occluded_id)
                    if key not in self.occlusion_history:
                        self.occlusion_history[key] = []
                    self.occlusion_history[key].append(occlusion_ratio)
                    
                    # Keep only recent history
                    if len(self.occlusion_history[key]) > 30:
                        self.occlusion_history[key] = self.occlusion_history[key][-30:]
        
        return occlusions
    
    def _sort_by_depth(self, detections: List[Dict]) -> List[Dict]:
        """
        Sort detections by estimated depth (closer first)
        
        Args:
            detections: List of detections
            
        Returns:
            Sorted detections
        """
        if self.depth_estimation_method == "centroid_y":
            # Vehicles lower in image are closer (perspective)
            return sorted(
                detections,
                key=lambda d: self._get_centroid_y(d),
                reverse=True
            )
        
        elif self.depth_estimation_method == "area":
            # Larger vehicles are closer
            return sorted(
                detections,
                key=lambda d: self._get_area(d),
                reverse=True
            )
        
        elif self.depth_estimation_method == "perspective":
            # Combine centroid_y and area with perspective weighting
            return sorted(
                detections,
                key=lambda d: self._get_perspective_score(d),
                reverse=True
            )
        
        else:
            return detections
    
    def _get_polygon(self, detection: Dict) -> Optional[Polygon]:
        """Extract polygon from detection"""
        # Try mask first
        if 'mask' in detection and detection['mask'] is not None:
            mask = detection['mask']
            contours, _ = cv2.findContours(
                mask.astype(np.uint8),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            if contours:
                # Use largest contour
                largest = max(contours, key=cv2.contourArea)
                points = largest.squeeze()
                
                if len(points.shape) == 2 and points.shape[0] >= 3:
                    return Polygon(points)
        
        # Try polygon
        if 'polygon' in detection and detection['polygon']:
            return Polygon(detection['polygon'])
        
        # Try bbox
        if 'bbox' in detection:
            x1, y1, x2, y2 = detection['bbox']
            return Polygon([
                (x1, y1), (x2, y1), (x2, y2), (x1, y2)
            ])
        
        return None
    
    def _get_centroid_y(self, detection: Dict) -> float:
        """Get Y coordinate of centroid"""
        poly = self._get_polygon(detection)
        if poly:
            return poly.centroid.y
        return 0.0
    
    def _get_area(self, detection: Dict) -> float:
        """Get area of detection"""
        poly = self._get_polygon(detection)
        if poly:
            return poly.area
        return 0.0
    
    def _get_perspective_score(self, detection: Dict) -> float:
        """
        Calculate perspective-aware depth score
        
        Combines:
        - Y position (lower = closer)
        - Area (larger = closer)
        - Aspect ratio (perspective distortion)
        """
        poly = self._get_polygon(detection)
        if not poly:
            return 0.0
        
        centroid_y = poly.centroid.y
        area = poly.area
        
        # Normalize (assuming image height ~1000, area ~10000)
        y_score = centroid_y / 1000.0
        area_score = np.sqrt(area / 10000.0)
        
        # Weighted combination
        # Y position is more reliable for depth
        score = 0.7 * y_score + 0.3 * area_score
        
        return score
    
    def adjust_confidence(
        self,
        detection: Dict,
        occlusions: List[OcclusionInfo]
    ) -> float:
        """
        Adjust detection confidence based on occlusion
        
        Args:
            detection: Detection dictionary
            occlusions: List of occlusions
            
        Returns:
            Adjusted confidence score
        """
        track_id = detection.get('track_id')
        original_conf = detection.get('confidence', 1.0)
        
        # Find occlusions involving this detection
        relevant_occlusions = [
            occ for occ in occlusions
            if occ.occluded_id == track_id
        ]
        
        if not relevant_occlusions:
            return original_conf
        
        # Calculate total occlusion
        total_occlusion = sum(occ.occlusion_ratio for occ in relevant_occlusions)
        total_occlusion = min(total_occlusion, 1.0)
        
        # Reduce confidence based on occlusion
        # Heavily occluded vehicles have lower confidence
        adjusted_conf = original_conf * (1.0 - 0.5 * total_occlusion)
        
        return max(adjusted_conf, 0.1)  # Minimum confidence
    
    def recover_occluded_vehicle(
        self,
        occluded_detection: Dict,
        occluder_detection: Dict,
        occlusion_info: OcclusionInfo
    ) -> Optional[Dict]:
        """
        Attempt to recover full shape of occluded vehicle
        
        Args:
            occluded_detection: Partially visible vehicle
            occluder_detection: Occluding vehicle
            occlusion_info: Occlusion information
            
        Returns:
            Updated detection with recovered shape or None
        """
        try:
            occluded_poly = self._get_polygon(occluded_detection)
            occluder_poly = self._get_polygon(occluder_detection)
            
            if not occluded_poly or not occluder_poly:
                return None
            
            # If occlusion is severe (>50%), try to extrapolate
            if occlusion_info.occlusion_ratio > 0.5:
                # Get visible part
                visible_part = occluded_poly.difference(occluder_poly)
                
                if visible_part.is_empty:
                    return None
                
                # Estimate full shape by mirroring/extending visible part
                # This is a simplified approach
                centroid = visible_part.centroid
                
                # Extend bounding box
                minx, miny, maxx, maxy = visible_part.bounds
                
                # Estimate hidden part based on visible dimensions
                width = maxx - minx
                height = maxy - miny
                
                # Extend in direction away from occluder
                occluder_centroid = occluder_poly.centroid
                
                dx = centroid.x - occluder_centroid.x
                dy = centroid.y - occluder_centroid.y
                
                # Normalize direction
                length = np.sqrt(dx**2 + dy**2)
                if length > 0:
                    dx /= length
                    dy /= length
                
                # Extend by estimated hidden amount
                extension = occlusion_info.occlusion_ratio * max(width, height)
                
                new_minx = minx + dx * extension if dx < 0 else minx
                new_miny = miny + dy * extension if dy < 0 else miny
                new_maxx = maxx + dx * extension if dx > 0 else maxx
                new_maxy = maxy + dy * extension if dy > 0 else maxy
                
                # Create extended polygon
                extended_poly = Polygon([
                    (new_minx, new_miny),
                    (new_maxx, new_miny),
                    (new_maxx, new_maxy),
                    (new_minx, new_maxy)
                ])
                
                # Update detection
                recovered = occluded_detection.copy()
                recovered['polygon'] = list(extended_poly.exterior.coords[:-1])
                recovered['bbox'] = [new_minx, new_miny, new_maxx, new_maxy]
                recovered['confidence'] *= 0.8  # Reduce confidence for extrapolated shape
                recovered['is_recovered'] = True
                
                return recovered
        
        except Exception as e:
            logger.error(f"Failed to recover occluded vehicle: {e}")
        
        return None
    
    def get_occlusion_statistics(self) -> Dict:
        """
        Get occlusion statistics
        
        Returns:
            Statistics dictionary
        """
        if not self.occlusion_history:
            return {
                'total_occlusions': 0,
                'average_occlusion_ratio': 0.0,
                'max_occlusion_ratio': 0.0
            }
        
        all_ratios = [
            ratio
            for ratios in self.occlusion_history.values()
            for ratio in ratios
        ]
        
        return {
            'total_occlusions': len(self.occlusion_history),
            'average_occlusion_ratio': np.mean(all_ratios) if all_ratios else 0.0,
            'max_occlusion_ratio': np.max(all_ratios) if all_ratios else 0.0,
            'occlusion_pairs': len(self.occlusion_history)
        }


class PerspectiveCorrector:
    """
    Corrects for perspective effects in occlusion detection
    
    Accounts for:
    - Camera angle
    - Lens distortion
    - Vanishing point
    """
    
    def __init__(
        self,
        vanishing_point: Optional[Tuple[float, float]] = None,
        horizon_y: Optional[float] = None
    ):
        """
        Initialize perspective corrector
        
        Args:
            vanishing_point: Vanishing point coordinates (x, y)
            horizon_y: Y coordinate of horizon line
        """
        self.vanishing_point = vanishing_point
        self.horizon_y = horizon_y
    
    def estimate_vanishing_point(
        self,
        parking_lines: List[List[Tuple[float, float]]]
    ) -> Tuple[float, float]:
        """
        Estimate vanishing point from parking lot lines
        
        Args:
            parking_lines: List of line segments
            
        Returns:
            Vanishing point (x, y)
        """
        # Find intersection of parallel lines
        # Simplified implementation
        
        if len(parking_lines) < 2:
            return (0, 0)
        
        # Use first two lines
        line1 = parking_lines[0]
        line2 = parking_lines[1]
        
        # Convert to line equations
        x1, y1 = line1[0]
        x2, y2 = line1[1]
        x3, y3 = line2[0]
        x4, y4 = line2[1]
        
        # Calculate intersection
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        
        if abs(denom) < 1e-6:
            return (0, 0)
        
        px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
        py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
        
        self.vanishing_point = (px, py)
        return self.vanishing_point
    
    def get_depth_weight(self, y: float, image_height: float) -> float:
        """
        Get depth weight based on Y position and perspective
        
        Args:
            y: Y coordinate
            image_height: Image height
            
        Returns:
            Depth weight (higher = closer)
        """
        if self.horizon_y is None:
            # Assume horizon at top third of image
            self.horizon_y = image_height / 3.0
        
        # Distance from horizon
        distance_from_horizon = y - self.horizon_y
        
        # Normalize to 0-1
        max_distance = image_height - self.horizon_y
        
        if max_distance > 0:
            weight = distance_from_horizon / max_distance
            return max(0.0, min(1.0, weight))
        
        return 0.5
