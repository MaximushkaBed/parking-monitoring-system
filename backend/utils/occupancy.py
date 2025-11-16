import numpy as np
from shapely.geometry import Point, Polygon
from typing import List, Tuple, Dict, Optional
from collections import deque
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class OccupancyDetector:
    """
    Detect parking place occupancy using point-in-polygon algorithm
    """
    
    def __init__(self, polygon: List[Tuple[float, float]]):
        """
        Initialize occupancy detector for a parking place
        
        Args:
            polygon: List of (x, y) coordinates defining the parking place boundary
        """
        self.polygon_points = polygon
        try:
            self.polygon = Polygon(polygon)
            if not self.polygon.is_valid:
                # Try to fix invalid polygon
                self.polygon = self.polygon.buffer(0)
            self.is_valid = self.polygon.is_valid
        except Exception as e:
            logger.error(f"Invalid polygon: {e}")
            self.polygon = None
            self.is_valid = False
    
    def is_occupied(self, centroids: List[Tuple[float, float]]) -> bool:
        """
        Check if parking place is occupied by any vehicle
        
        Args:
            centroids: List of vehicle centroid coordinates
            
        Returns:
            True if at least one centroid is inside the polygon
        """
        if not self.is_valid or self.polygon is None:
            return False
        
        for cx, cy in centroids:
            point = Point(cx, cy)
            if self.polygon.contains(point):
                return True
        
        return False
    
    def get_occupying_vehicles(
        self,
        detections: List[Dict]
    ) -> List[Dict]:
        """
        Get list of vehicles occupying this parking place
        
        Args:
            detections: List of vehicle detections with 'centroid' key
            
        Returns:
            List of detections that are inside the polygon
        """
        if not self.is_valid or self.polygon is None:
            return []
        
        occupying = []
        for det in detections:
            cx, cy = det['centroid']
            point = Point(cx, cy)
            if self.polygon.contains(point):
                occupying.append(det)
        
        return occupying
    
    def get_overlap_ratio(self, bbox: Tuple[float, float, float, float]) -> float:
        """
        Calculate overlap ratio between bbox and polygon
        
        Args:
            bbox: (x1, y1, x2, y2) bounding box
            
        Returns:
            Overlap ratio [0, 1]
        """
        if not self.is_valid or self.polygon is None:
            return 0.0
        
        try:
            x1, y1, x2, y2 = bbox
            bbox_poly = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
            
            intersection = self.polygon.intersection(bbox_poly).area
            bbox_area = bbox_poly.area
            
            if bbox_area == 0:
                return 0.0
            
            return intersection / bbox_area
        except Exception as e:
            logger.error(f"Overlap calculation error: {e}")
            return 0.0


class TemporalSmoother:
    """
    Temporal smoothing to filter false positives/negatives
    Uses debounce logic with configurable thresholds
    """
    
    def __init__(
        self,
        min_frames_occupied: int = 5,
        min_frames_free: int = 5,
        max_history: int = 30
    ):
        """
        Initialize temporal smoother
        
        Args:
            min_frames_occupied: Minimum consecutive frames to confirm occupation
            min_frames_free: Minimum consecutive frames to confirm free
            max_history: Maximum history length to keep
        """
        self.min_frames_occupied = min_frames_occupied
        self.min_frames_free = min_frames_free
        self.max_history = max_history
        
        self.history = deque(maxlen=max_history)
        self.current_state = "free"  # "free" or "occupied"
        self.state_counter = 0
    
    def update(self, is_occupied: bool) -> Tuple[str, bool]:
        """
        Update state with new observation
        
        Args:
            is_occupied: Current frame observation
            
        Returns:
            (current_state, state_changed)
        """
        self.history.append(is_occupied)
        
        # Count consecutive frames in current observation
        if len(self.history) == 0:
            return self.current_state, False
        
        # Check recent history
        recent_occupied_count = sum(1 for x in list(self.history)[-max(self.min_frames_occupied, self.min_frames_free):] if x)
        recent_free_count = sum(1 for x in list(self.history)[-max(self.min_frames_occupied, self.min_frames_free):] if not x)
        
        state_changed = False
        
        # State transition logic
        if self.current_state == "free":
            # Check if we should transition to occupied
            if recent_occupied_count >= self.min_frames_occupied:
                self.current_state = "occupied"
                self.state_counter = 0
                state_changed = True
                logger.debug("State changed: free -> occupied")
        
        elif self.current_state == "occupied":
            # Check if we should transition to free
            if recent_free_count >= self.min_frames_free:
                self.current_state = "free"
                self.state_counter = 0
                state_changed = True
                logger.debug("State changed: occupied -> free")
        
        self.state_counter += 1
        
        return self.current_state, state_changed
    
    def get_state(self) -> str:
        """Get current smoothed state"""
        return self.current_state
    
    def reset(self):
        """Reset smoother state"""
        self.history.clear()
        self.current_state = "free"
        self.state_counter = 0


class ParkingPlaceMonitor:
    """
    Monitor a single parking place combining occupancy detection and temporal smoothing
    """
    
    def __init__(
        self,
        place_id: int,
        polygon: List[Tuple[float, float]],
        min_frames_occupied: int = 5,
        min_frames_free: int = 5
    ):
        """
        Initialize parking place monitor
        
        Args:
            place_id: Unique parking place identifier
            polygon: Polygon defining the parking place
            min_frames_occupied: Frames to confirm occupation
            min_frames_free: Frames to confirm free
        """
        self.place_id = place_id
        self.detector = OccupancyDetector(polygon)
        self.smoother = TemporalSmoother(min_frames_occupied, min_frames_free)
        
        self.current_track_id: Optional[int] = None
        self.occupancy_start_time: Optional[datetime] = None
        self.last_update_time: Optional[datetime] = None
    
    def update(
        self,
        detections: List[Dict],
        timestamp: Optional[datetime] = None
    ) -> Tuple[str, bool, Optional[Dict]]:
        """
        Update parking place state with new detections
        
        Args:
            detections: List of vehicle detections
            timestamp: Current timestamp
            
        Returns:
            (state, state_changed, event_data)
            event_data is not None when state changes to occupied (contains vehicle info)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        self.last_update_time = timestamp
        
        # Check occupancy
        occupying_vehicles = self.detector.get_occupying_vehicles(detections)
        is_occupied = len(occupying_vehicles) > 0
        
        # Update smoother
        state, state_changed = self.smoother.update(is_occupied)
        
        event_data = None
        
        # Handle state changes
        if state_changed:
            if state == "occupied":
                # Started occupation
                self.occupancy_start_time = timestamp
                if len(occupying_vehicles) > 0:
                    self.current_track_id = occupying_vehicles[0].get('track_id')
                    event_data = {
                        'place_id': self.place_id,
                        'start_time': timestamp,
                        'track_id': self.current_track_id,
                        'vehicle_class': occupying_vehicles[0].get('class_name'),
                        'confidence': occupying_vehicles[0].get('confidence')
                    }
                logger.info(f"Place {self.place_id} occupied (track_id: {self.current_track_id})")
            
            elif state == "free":
                # Ended occupation
                if self.occupancy_start_time is not None:
                    duration = (timestamp - self.occupancy_start_time).total_seconds()
                    event_data = {
                        'place_id': self.place_id,
                        'start_time': self.occupancy_start_time,
                        'end_time': timestamp,
                        'duration_seconds': int(duration),
                        'track_id': self.current_track_id
                    }
                    logger.info(f"Place {self.place_id} freed (duration: {duration:.1f}s)")
                
                self.occupancy_start_time = None
                self.current_track_id = None
        
        return state, state_changed, event_data
    
    def get_state(self) -> Dict:
        """Get current state information"""
        return {
            'place_id': self.place_id,
            'state': self.smoother.get_state(),
            'track_id': self.current_track_id,
            'occupancy_start_time': self.occupancy_start_time,
            'last_update_time': self.last_update_time
        }
    
    def reset(self):
        """Reset monitor state"""
        self.smoother.reset()
        self.current_track_id = None
        self.occupancy_start_time = None


class ParkingMonitorManager:
    """
    Manage multiple parking place monitors
    """
    
    def __init__(self):
        self.monitors: Dict[int, ParkingPlaceMonitor] = {}
    
    def add_place(
        self,
        place_id: int,
        polygon: List[Tuple[float, float]],
        min_frames_occupied: int = 5,
        min_frames_free: int = 5
    ):
        """Add a parking place to monitor"""
        self.monitors[place_id] = ParkingPlaceMonitor(
            place_id, polygon, min_frames_occupied, min_frames_free
        )
        logger.info(f"Added parking place {place_id} to monitor")
    
    def remove_place(self, place_id: int):
        """Remove a parking place from monitoring"""
        if place_id in self.monitors:
            del self.monitors[place_id]
            logger.info(f"Removed parking place {place_id} from monitor")
    
    def update_all(
        self,
        detections: List[Dict],
        timestamp: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Update all parking places with new detections
        
        Args:
            detections: List of vehicle detections
            timestamp: Current timestamp
            
        Returns:
            List of events (state changes)
        """
        events = []
        
        for place_id, monitor in self.monitors.items():
            state, state_changed, event_data = monitor.update(detections, timestamp)
            
            if state_changed and event_data is not None:
                events.append(event_data)
        
        return events
    
    def get_all_states(self) -> Dict[int, Dict]:
        """Get current state of all parking places"""
        return {place_id: monitor.get_state() for place_id, monitor in self.monitors.items()}
    
    def get_occupancy_summary(self) -> Dict:
        """Get summary of occupancy"""
        states = self.get_all_states()
        total = len(states)
        occupied = sum(1 for s in states.values() if s['state'] == 'occupied')
        free = total - occupied
        
        return {
            'total': total,
            'occupied': occupied,
            'free': free,
            'occupancy_rate': (occupied / total * 100) if total > 0 else 0.0
        }
