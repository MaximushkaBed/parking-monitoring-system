"""
IoU-based occupancy detection module
Uses Intersection over Union between vehicle masks and parking place polygons
"""

import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class OccupancyEvent:
    """Occupancy event record"""
    place_id: int
    track_id: int
    event_type: str  # 'occupied' or 'freed'
    timestamp: datetime
    duration_seconds: Optional[float] = None
    confidence: float = 1.0


@dataclass
class ParkingPlaceState:
    """State of a parking place"""
    place_id: int
    polygon: Polygon
    status: str = "free"  # 'free' or 'occupied'
    current_track_id: Optional[int] = None
    occupied_since: Optional[datetime] = None
    
    # Temporal smoothing counters
    occupied_frames: int = 0
    free_frames: int = 0
    
    # IoU history for debugging
    iou_history: List[float] = field(default_factory=list)
    max_history_len: int = 30


class IoUOccupancyDetector:
    """
    Occupancy detector using IoU (Intersection over Union)
    
    More accurate than point-in-polygon, especially for:
    - Angled parking
    - Partial occlusions
    - Large vehicles
    """
    
    def __init__(
        self,
        iou_threshold: float = 0.25,
        min_frames_occupied: int = 5,
        min_frames_free: int = 5
    ):
        """
        Initialize IoU occupancy detector
        
        Args:
            iou_threshold: Minimum IoU to consider place occupied (0.25 = 25%)
            min_frames_occupied: Frames to confirm occupation
            min_frames_free: Frames to confirm freeing
        """
        self.iou_threshold = iou_threshold
        self.min_frames_occupied = min_frames_occupied
        self.min_frames_free = min_frames_free
        
        self.places: Dict[int, ParkingPlaceState] = {}
    
    def add_place(
        self,
        place_id: int,
        polygon: List[Tuple[float, float]]
    ):
        """
        Add a parking place
        
        Args:
            place_id: Unique place identifier
            polygon: List of (x, y) coordinates
        """
        poly = Polygon(polygon)
        
        if not poly.is_valid:
            logger.warning(f"Invalid polygon for place {place_id}, attempting to fix")
            poly = poly.buffer(0)  # Fix self-intersections
        
        self.places[place_id] = ParkingPlaceState(
            place_id=place_id,
            polygon=poly
        )
        
        logger.info(f"Added place {place_id} with area {poly.area:.2f}")
    
    def remove_place(self, place_id: int):
        """Remove a parking place"""
        if place_id in self.places:
            del self.places[place_id]
            logger.info(f"Removed place {place_id}")
    
    def compute_iou(
        self,
        mask: np.ndarray,
        polygon: Polygon
    ) -> float:
        """
        Compute IoU between binary mask and polygon
        
        Args:
            mask: Binary mask (H x W) where 1 = vehicle
            polygon: Shapely polygon of parking place
            
        Returns:
            IoU value (0.0 to 1.0)
        """
        # Get bounding box of polygon
        minx, miny, maxx, maxy = polygon.bounds
        minx, miny = int(minx), int(miny)
        maxx, maxy = int(maxx), int(maxy)
        
        # Clip to image bounds
        h, w = mask.shape
        minx = max(0, minx)
        miny = max(0, miny)
        maxx = min(w, maxx)
        maxy = min(h, maxy)
        
        if minx >= maxx or miny >= maxy:
            return 0.0
        
        # Create polygon mask
        y_coords, x_coords = np.meshgrid(
            np.arange(miny, maxy),
            np.arange(minx, maxx),
            indexing='ij'
        )
        
        points = np.column_stack([x_coords.ravel(), y_coords.ravel()])
        
        # Vectorized point-in-polygon check
        poly_mask = np.array([polygon.contains(Point(p)) for p in points])
        poly_mask = poly_mask.reshape(maxy - miny, maxx - minx)
        
        # Get vehicle mask in same region
        vehicle_mask = mask[miny:maxy, minx:maxx]
        
        # Compute intersection and union
        intersection = np.logical_and(poly_mask, vehicle_mask).sum()
        union = np.logical_or(poly_mask, vehicle_mask).sum()
        
        if union == 0:
            return 0.0
        
        iou = intersection / union
        return float(iou)
    
    def compute_iou_from_polygon(
        self,
        vehicle_polygon: Polygon,
        place_polygon: Polygon
    ) -> float:
        """
        Compute IoU between two polygons (faster alternative)
        
        Args:
            vehicle_polygon: Vehicle segmentation polygon
            place_polygon: Parking place polygon
            
        Returns:
            IoU value (0.0 to 1.0)
        """
        if not vehicle_polygon.is_valid or not place_polygon.is_valid:
            return 0.0
        
        intersection = vehicle_polygon.intersection(place_polygon).area
        union = vehicle_polygon.union(place_polygon).area
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def update(
        self,
        detections: List[Dict]
    ) -> List[OccupancyEvent]:
        """
        Update occupancy based on detections
        
        Args:
            detections: List of detection dictionaries with:
                - 'mask': Binary mask (H x W) or None
                - 'polygon': Shapely polygon or None
                - 'track_id': Unique track ID
                - 'centroid': [x, y] (fallback if no mask)
                - 'confidence': Detection confidence
                
        Returns:
            List of occupancy events (state changes)
        """
        events = []
        current_time = datetime.utcnow()
        
        # Track which places have vehicles
        place_occupancy = {}  # place_id -> (track_id, iou, confidence)
        
        # For each detection, find best matching place
        for det in detections:
            track_id = det.get('track_id')
            confidence = det.get('confidence', 1.0)
            
            # Get mask or polygon
            mask = det.get('mask')
            vehicle_poly = det.get('polygon')
            
            if mask is None and vehicle_poly is None:
                # Fallback to centroid-based (old method)
                centroid = det.get('centroid')
                if centroid:
                    vehicle_poly = Point(centroid).buffer(1.0)  # Small circle
            
            if mask is None and vehicle_poly is None:
                continue
            
            # Find best matching place
            best_place_id = None
            best_iou = 0.0
            
            for place_id, place_state in self.places.items():
                if mask is not None:
                    iou = self.compute_iou(mask, place_state.polygon)
                else:
                    iou = self.compute_iou_from_polygon(vehicle_poly, place_state.polygon)
                
                if iou > best_iou:
                    best_iou = iou
                    best_place_id = place_id
            
            # If IoU exceeds threshold, mark place as occupied
            if best_iou >= self.iou_threshold and best_place_id is not None:
                # Keep highest IoU detection for each place
                if best_place_id not in place_occupancy or best_iou > place_occupancy[best_place_id][1]:
                    place_occupancy[best_place_id] = (track_id, best_iou, confidence)
        
        # Update each place state
        for place_id, place_state in self.places.items():
            # Store IoU for debugging
            if place_id in place_occupancy:
                iou_value = place_occupancy[place_id][1]
                place_state.iou_history.append(iou_value)
            else:
                place_state.iou_history.append(0.0)
            
            # Trim history
            if len(place_state.iou_history) > place_state.max_history_len:
                place_state.iou_history.pop(0)
            
            # Check if place has vehicle
            has_vehicle = place_id in place_occupancy
            
            if has_vehicle:
                track_id, iou, conf = place_occupancy[place_id]
                place_state.occupied_frames += 1
                place_state.free_frames = 0
                
                # State transition: free -> occupied
                if (place_state.status == "free" and 
                    place_state.occupied_frames >= self.min_frames_occupied):
                    
                    place_state.status = "occupied"
                    place_state.current_track_id = track_id
                    place_state.occupied_since = current_time
                    
                    events.append(OccupancyEvent(
                        place_id=place_id,
                        track_id=track_id,
                        event_type="occupied",
                        timestamp=current_time,
                        confidence=conf
                    ))
                    
                    logger.info(f"Place {place_id} occupied by track {track_id} (IoU: {iou:.2f})")
            
            else:
                place_state.free_frames += 1
                place_state.occupied_frames = 0
                
                # State transition: occupied -> free
                if (place_state.status == "occupied" and 
                    place_state.free_frames >= self.min_frames_free):
                    
                    duration = None
                    if place_state.occupied_since:
                        duration = (current_time - place_state.occupied_since).total_seconds()
                    
                    old_track_id = place_state.current_track_id
                    
                    place_state.status = "free"
                    place_state.current_track_id = None
                    place_state.occupied_since = None
                    
                    events.append(OccupancyEvent(
                        place_id=place_id,
                        track_id=old_track_id,
                        event_type="freed",
                        timestamp=current_time,
                        duration_seconds=duration
                    ))
                    
                    logger.info(f"Place {place_id} freed (duration: {duration:.1f}s)")
        
        return events
    
    def get_occupancy_summary(self) -> Dict:
        """Get current occupancy summary"""
        total = len(self.places)
        occupied = sum(1 for p in self.places.values() if p.status == "occupied")
        free = total - occupied
        
        return {
            'total': total,
            'occupied': occupied,
            'free': free,
            'occupancy_rate': (occupied / total * 100) if total > 0 else 0.0
        }
    
    def get_place_status(self, place_id: int) -> Optional[Dict]:
        """Get status of a specific place"""
        if place_id not in self.places:
            return None
        
        place = self.places[place_id]
        
        return {
            'place_id': place_id,
            'status': place.status,
            'track_id': place.current_track_id,
            'occupied_since': place.occupied_since.isoformat() if place.occupied_since else None,
            'occupied_frames': place.occupied_frames,
            'free_frames': place.free_frames,
            'recent_iou': place.iou_history[-10:] if place.iou_history else []
        }
    
    def get_all_statuses(self) -> List[Dict]:
        """Get status of all places"""
        return [self.get_place_status(pid) for pid in self.places.keys()]


class ParkingMonitorManagerIoU:
    """
    Manager for multiple parking places with IoU-based detection
    Replaces the old point-in-polygon manager
    """
    
    def __init__(
        self,
        iou_threshold: float = 0.25,
        min_frames_occupied: int = 5,
        min_frames_free: int = 5
    ):
        """Initialize manager"""
        self.detector = IoUOccupancyDetector(
            iou_threshold=iou_threshold,
            min_frames_occupied=min_frames_occupied,
            min_frames_free=min_frames_free
        )
    
    def add_place(self, place_id: int, polygon: List[Tuple[float, float]]):
        """Add parking place"""
        self.detector.add_place(place_id, polygon)
    
    def remove_place(self, place_id: int):
        """Remove parking place"""
        self.detector.remove_place(place_id)
    
    def update_all(self, detections: List[Dict]) -> List[Dict]:
        """
        Update all places with new detections
        
        Returns:
            List of events (state changes)
        """
        events = self.detector.update(detections)
        
        # Convert to dict format
        return [
            {
                'place_id': e.place_id,
                'track_id': e.track_id,
                'event_type': e.event_type,
                'timestamp': e.timestamp.isoformat(),
                'duration_seconds': e.duration_seconds,
                'confidence': e.confidence
            }
            for e in events
        ]
    
    def get_occupancy_summary(self) -> Dict:
        """Get occupancy summary"""
        return self.detector.get_occupancy_summary()
    
    def get_place_status(self, place_id: int) -> Optional[Dict]:
        """Get place status"""
        return self.detector.get_place_status(place_id)
    
    def get_all_statuses(self) -> List[Dict]:
        """Get all place statuses"""
        return self.detector.get_all_statuses()
