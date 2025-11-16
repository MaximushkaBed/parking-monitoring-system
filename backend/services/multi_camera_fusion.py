"""
Multi-camera fusion module
Combines data from multiple cameras covering the same parking area
"""

import numpy as np
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from shapely.geometry import Polygon, box
import logging

logger = logging.getLogger(__name__)


@dataclass
class CameraView:
    """Camera field of view"""
    camera_id: int
    fov_polygon: Polygon  # Field of view on global map
    priority: int = 1  # Higher priority cameras override lower ones
    last_update: Optional[datetime] = None


@dataclass
class GlobalParkingPlace:
    """Global parking place visible by multiple cameras"""
    place_id: int
    global_polygon: Polygon  # Position on global map
    visible_cameras: Set[int] = field(default_factory=set)
    
    # Per-camera status
    camera_statuses: Dict[int, str] = field(default_factory=dict)  # camera_id -> 'free'/'occupied'
    camera_track_ids: Dict[int, Optional[int]] = field(default_factory=dict)
    camera_confidences: Dict[int, float] = field(default_factory=dict)
    camera_timestamps: Dict[int, datetime] = field(default_factory=dict)
    
    # Fused status
    fused_status: str = "free"
    fused_track_id: Optional[int] = None
    fused_confidence: float = 0.0
    last_status_change: Optional[datetime] = None


class MultiCameraFusion:
    """
    Fuses occupancy data from multiple cameras
    
    Strategy:
    - If ANY camera sees place as occupied → place is occupied (OR logic)
    - Use highest confidence detection
    - Handle timestamp synchronization
    - Resolve conflicts based on camera priority
    """
    
    def __init__(
        self,
        max_time_diff_seconds: float = 2.0,
        stale_threshold_seconds: float = 10.0
    ):
        """
        Initialize multi-camera fusion
        
        Args:
            max_time_diff_seconds: Max time difference for synchronization
            stale_threshold_seconds: Consider data stale after this time
        """
        self.max_time_diff = timedelta(seconds=max_time_diff_seconds)
        self.stale_threshold = timedelta(seconds=stale_threshold_seconds)
        
        self.cameras: Dict[int, CameraView] = {}
        self.places: Dict[int, GlobalParkingPlace] = {}
    
    def add_camera(
        self,
        camera_id: int,
        fov_polygon: List[Tuple[float, float]],
        priority: int = 1
    ):
        """
        Register a camera with its field of view
        
        Args:
            camera_id: Unique camera identifier
            fov_polygon: Field of view polygon on global map
            priority: Camera priority (higher = more trusted)
        """
        poly = Polygon(fov_polygon)
        
        if not poly.is_valid:
            logger.warning(f"Invalid FOV polygon for camera {camera_id}, fixing")
            poly = poly.buffer(0)
        
        self.cameras[camera_id] = CameraView(
            camera_id=camera_id,
            fov_polygon=poly,
            priority=priority
        )
        
        # Update place visibility
        self._update_place_visibility()
        
        logger.info(f"Added camera {camera_id} with FOV area {poly.area:.2f}, priority {priority}")
    
    def remove_camera(self, camera_id: int):
        """Remove a camera"""
        if camera_id in self.cameras:
            del self.cameras[camera_id]
            
            # Remove from places
            for place in self.places.values():
                place.visible_cameras.discard(camera_id)
                place.camera_statuses.pop(camera_id, None)
                place.camera_track_ids.pop(camera_id, None)
                place.camera_confidences.pop(camera_id, None)
                place.camera_timestamps.pop(camera_id, None)
            
            logger.info(f"Removed camera {camera_id}")
    
    def add_place(
        self,
        place_id: int,
        global_polygon: List[Tuple[float, float]]
    ):
        """
        Add a parking place on global map
        
        Args:
            place_id: Unique place identifier
            global_polygon: Polygon on global map coordinates
        """
        poly = Polygon(global_polygon)
        
        if not poly.is_valid:
            logger.warning(f"Invalid polygon for place {place_id}, fixing")
            poly = poly.buffer(0)
        
        self.places[place_id] = GlobalParkingPlace(
            place_id=place_id,
            global_polygon=poly
        )
        
        # Determine which cameras can see this place
        self._update_place_visibility()
        
        logger.info(f"Added place {place_id}, visible by cameras: {self.places[place_id].visible_cameras}")
    
    def remove_place(self, place_id: int):
        """Remove a parking place"""
        if place_id in self.places:
            del self.places[place_id]
            logger.info(f"Removed place {place_id}")
    
    def _update_place_visibility(self):
        """Update which cameras can see which places"""
        for place_id, place in self.places.items():
            place.visible_cameras.clear()
            
            for camera_id, camera in self.cameras.items():
                # Check if place intersects with camera FOV
                if camera.fov_polygon.intersects(place.global_polygon):
                    place.visible_cameras.add(camera_id)
    
    def update_camera_data(
        self,
        camera_id: int,
        place_statuses: Dict[int, Dict]
    ):
        """
        Update data from a single camera
        
        Args:
            camera_id: Camera identifier
            place_statuses: Dict of place_id -> {
                'status': 'free' or 'occupied',
                'track_id': int or None,
                'confidence': float,
                'timestamp': datetime or str
            }
        """
        if camera_id not in self.cameras:
            logger.warning(f"Camera {camera_id} not registered")
            return
        
        current_time = datetime.utcnow()
        self.cameras[camera_id].last_update = current_time
        
        # Update each place
        for place_id, status_data in place_statuses.items():
            if place_id not in self.places:
                continue
            
            place = self.places[place_id]
            
            # Parse timestamp
            timestamp = status_data.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif timestamp is None:
                timestamp = current_time
            
            # Store camera-specific data
            place.camera_statuses[camera_id] = status_data.get('status', 'free')
            place.camera_track_ids[camera_id] = status_data.get('track_id')
            place.camera_confidences[camera_id] = status_data.get('confidence', 1.0)
            place.camera_timestamps[camera_id] = timestamp
        
        # Fuse data for all places
        self._fuse_all_places()
    
    def _fuse_all_places(self):
        """Fuse data from all cameras for all places"""
        current_time = datetime.utcnow()
        
        for place in self.places.values():
            self._fuse_place(place, current_time)
    
    def _fuse_place(self, place: GlobalParkingPlace, current_time: datetime):
        """
        Fuse data for a single place
        
        Strategy:
        1. Filter out stale data
        2. If ANY camera sees occupied → occupied (OR logic)
        3. Use highest confidence detection
        4. Prioritize higher priority cameras in case of conflict
        """
        # Filter valid cameras (not stale)
        valid_cameras = []
        
        for camera_id in place.visible_cameras:
            if camera_id not in place.camera_timestamps:
                continue
            
            timestamp = place.camera_timestamps[camera_id]
            age = current_time - timestamp
            
            if age <= self.stale_threshold:
                valid_cameras.append(camera_id)
        
        if not valid_cameras:
            # No recent data, keep previous status
            return
        
        # Check if any camera sees occupied
        occupied_cameras = [
            cam_id for cam_id in valid_cameras
            if place.camera_statuses.get(cam_id) == 'occupied'
        ]
        
        if occupied_cameras:
            # Place is occupied - use highest confidence detection
            best_camera = max(
                occupied_cameras,
                key=lambda cid: (
                    place.camera_confidences.get(cid, 0.0),
                    self.cameras[cid].priority
                )
            )
            
            new_status = 'occupied'
            new_track_id = place.camera_track_ids[best_camera]
            new_confidence = place.camera_confidences[best_camera]
        
        else:
            # All cameras see free
            new_status = 'free'
            new_track_id = None
            
            # Average confidence from all cameras
            confidences = [
                place.camera_confidences.get(cid, 1.0)
                for cid in valid_cameras
            ]
            new_confidence = np.mean(confidences) if confidences else 1.0
        
        # Check if status changed
        if place.fused_status != new_status:
            logger.info(
                f"Place {place.place_id} status changed: "
                f"{place.fused_status} -> {new_status} "
                f"(cameras: {valid_cameras})"
            )
            place.last_status_change = current_time
        
        # Update fused status
        place.fused_status = new_status
        place.fused_track_id = new_track_id
        place.fused_confidence = new_confidence
    
    def get_fused_occupancy(self) -> Dict[int, Dict]:
        """
        Get fused occupancy for all places
        
        Returns:
            Dict of place_id -> {
                'status': str,
                'track_id': int or None,
                'confidence': float,
                'visible_cameras': list,
                'last_change': str or None
            }
        """
        result = {}
        
        for place_id, place in self.places.items():
            result[place_id] = {
                'status': place.fused_status,
                'track_id': place.fused_track_id,
                'confidence': float(place.fused_confidence),
                'visible_cameras': list(place.visible_cameras),
                'last_change': place.last_status_change.isoformat() if place.last_status_change else None
            }
        
        return result
    
    def get_occupancy_summary(self) -> Dict:
        """Get overall occupancy summary"""
        total = len(self.places)
        occupied = sum(1 for p in self.places.values() if p.fused_status == 'occupied')
        free = total - occupied
        
        # Camera health
        current_time = datetime.utcnow()
        active_cameras = sum(
            1 for cam in self.cameras.values()
            if cam.last_update and (current_time - cam.last_update) <= self.stale_threshold
        )
        
        return {
            'total_places': total,
            'occupied': occupied,
            'free': free,
            'occupancy_rate': (occupied / total * 100) if total > 0 else 0.0,
            'total_cameras': len(self.cameras),
            'active_cameras': active_cameras
        }
    
    def get_camera_coverage(self) -> Dict[int, Dict]:
        """
        Get coverage information for each camera
        
        Returns:
            Dict of camera_id -> {
                'places_covered': int,
                'last_update': str or None,
                'is_active': bool
            }
        """
        current_time = datetime.utcnow()
        result = {}
        
        for camera_id, camera in self.cameras.items():
            places_covered = sum(
                1 for place in self.places.values()
                if camera_id in place.visible_cameras
            )
            
            is_active = (
                camera.last_update is not None and
                (current_time - camera.last_update) <= self.stale_threshold
            )
            
            result[camera_id] = {
                'places_covered': places_covered,
                'last_update': camera.last_update.isoformat() if camera.last_update else None,
                'is_active': is_active,
                'priority': camera.priority
            }
        
        return result
    
    def get_place_details(self, place_id: int) -> Optional[Dict]:
        """
        Get detailed information about a place
        
        Returns:
            Dict with per-camera and fused status
        """
        if place_id not in self.places:
            return None
        
        place = self.places[place_id]
        current_time = datetime.utcnow()
        
        camera_details = {}
        for camera_id in place.visible_cameras:
            status = place.camera_statuses.get(camera_id, 'unknown')
            timestamp = place.camera_timestamps.get(camera_id)
            
            age = None
            if timestamp:
                age = (current_time - timestamp).total_seconds()
            
            camera_details[camera_id] = {
                'status': status,
                'track_id': place.camera_track_ids.get(camera_id),
                'confidence': place.camera_confidences.get(camera_id, 0.0),
                'age_seconds': age
            }
        
        return {
            'place_id': place_id,
            'fused_status': place.fused_status,
            'fused_track_id': place.fused_track_id,
            'fused_confidence': place.fused_confidence,
            'last_status_change': place.last_status_change.isoformat() if place.last_status_change else None,
            'visible_cameras': list(place.visible_cameras),
            'camera_details': camera_details
        }
