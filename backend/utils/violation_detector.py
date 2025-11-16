"""
Parking violation detection module
Detects improper parking, double parking, blocking, etc.
"""

import numpy as np
from shapely.geometry import Polygon, Point, LineString
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ViolationType(Enum):
    """Types of parking violations"""
    DOUBLE_PARKING = "double_parking"  # Vehicle blocking another vehicle
    OUTSIDE_LINES = "outside_lines"  # Vehicle parked outside designated lines
    BLOCKING_EXIT = "blocking_exit"  # Vehicle blocking exit/entrance
    DISABLED_SPOT_MISUSE = "disabled_spot_misuse"  # Non-disabled vehicle in disabled spot
    OVERSTAY = "overstay"  # Vehicle exceeding time limit
    WRONG_ORIENTATION = "wrong_orientation"  # Vehicle parked in wrong direction


@dataclass
class ViolationRecord:
    """Parking violation record"""
    violation_id: str
    violation_type: ViolationType
    place_id: Optional[int]
    track_id: int
    timestamp: datetime
    confidence: float
    description: str
    vehicle_polygon: Optional[Polygon] = None


class ViolationDetector:
    """
    Detects parking violations
    
    Checks for:
    - Double parking (vehicle blocking others)
    - Parking outside designated lines
    - Blocking exits/entrances
    - Disabled spot misuse
    - Time limit violations
    - Wrong orientation
    """
    
    def __init__(
        self,
        outside_lines_threshold: float = 0.3,  # 30% outside = violation
        blocking_distance_threshold: float = 50.0,  # pixels
        orientation_tolerance: float = 30.0  # degrees
    ):
        """
        Initialize violation detector
        
        Args:
            outside_lines_threshold: Fraction of vehicle outside lines to trigger violation
            blocking_distance_threshold: Distance threshold for blocking detection
            orientation_tolerance: Angle tolerance for orientation check
        """
        self.outside_lines_threshold = outside_lines_threshold
        self.blocking_distance_threshold = blocking_distance_threshold
        self.orientation_tolerance = orientation_tolerance
        
        self.parking_places: Dict[int, Dict] = {}  # place_id -> metadata
        self.exit_zones: List[Polygon] = []
        self.violations: List[ViolationRecord] = []
    
    def add_parking_place(
        self,
        place_id: int,
        polygon: List[Tuple[float, float]],
        place_type: str = "regular",
        time_limit_hours: Optional[float] = None,
        expected_orientation: Optional[float] = None  # degrees, 0=horizontal
    ):
        """
        Add parking place with metadata
        
        Args:
            place_id: Place identifier
            polygon: Place polygon coordinates
            place_type: Type (regular, disabled, family, vip, electric, short_term)
            time_limit_hours: Time limit in hours (for short-term spots)
            expected_orientation: Expected vehicle orientation in degrees
        """
        poly = Polygon(polygon)
        
        if not poly.is_valid:
            logger.warning(f"Invalid polygon for place {place_id}, fixing")
            poly = poly.buffer(0)
        
        self.parking_places[place_id] = {
            'polygon': poly,
            'type': place_type,
            'time_limit_hours': time_limit_hours,
            'expected_orientation': expected_orientation
        }
    
    def add_exit_zone(self, polygon: List[Tuple[float, float]]):
        """Add exit/entrance zone that should not be blocked"""
        poly = Polygon(polygon)
        
        if not poly.is_valid:
            logger.warning("Invalid exit zone polygon, fixing")
            poly = poly.buffer(0)
        
        self.exit_zones.append(poly)
    
    def check_outside_lines(
        self,
        vehicle_polygon: Polygon,
        place_id: int,
        track_id: int
    ) -> Optional[ViolationRecord]:
        """
        Check if vehicle is parked outside designated lines
        
        Args:
            vehicle_polygon: Vehicle segmentation polygon
            place_id: Parking place ID
            track_id: Vehicle track ID
            
        Returns:
            ViolationRecord if violation detected, None otherwise
        """
        if place_id not in self.parking_places:
            return None
        
        place_poly = self.parking_places[place_id]['polygon']
        
        # Calculate how much of vehicle is outside the place
        intersection = vehicle_polygon.intersection(place_poly).area
        vehicle_area = vehicle_polygon.area
        
        if vehicle_area == 0:
            return None
        
        inside_fraction = intersection / vehicle_area
        outside_fraction = 1.0 - inside_fraction
        
        if outside_fraction > self.outside_lines_threshold:
            return ViolationRecord(
                violation_id=f"outside_{place_id}_{track_id}_{int(datetime.utcnow().timestamp())}",
                violation_type=ViolationType.OUTSIDE_LINES,
                place_id=place_id,
                track_id=track_id,
                timestamp=datetime.utcnow(),
                confidence=min(outside_fraction, 1.0),
                description=f"Vehicle {outside_fraction*100:.1f}% outside designated lines",
                vehicle_polygon=vehicle_polygon
            )
        
        return None
    
    def check_double_parking(
        self,
        vehicle_polygon: Polygon,
        track_id: int,
        other_vehicles: List[Dict]
    ) -> Optional[ViolationRecord]:
        """
        Check if vehicle is double-parked (blocking others)
        
        Args:
            vehicle_polygon: Vehicle segmentation polygon
            track_id: Vehicle track ID
            other_vehicles: List of other vehicles with polygons
            
        Returns:
            ViolationRecord if violation detected, None otherwise
        """
        # Check if vehicle is not in any parking place
        in_place = False
        for place_data in self.parking_places.values():
            if vehicle_polygon.intersects(place_data['polygon']):
                in_place = True
                break
        
        if in_place:
            return None  # Vehicle is in a place, not double-parked
        
        # Check if vehicle is blocking other vehicles
        for other in other_vehicles:
            if other.get('track_id') == track_id:
                continue
            
            other_poly = other.get('polygon')
            if other_poly is None:
                continue
            
            # Check distance between vehicles
            distance = vehicle_polygon.distance(other_poly)
            
            if distance < self.blocking_distance_threshold:
                # Check if other vehicle is in a parking place
                other_in_place = False
                for place_data in self.parking_places.values():
                    if other_poly.intersects(place_data['polygon']):
                        other_in_place = True
                        break
                
                if other_in_place:
                    return ViolationRecord(
                        violation_id=f"double_{track_id}_{int(datetime.utcnow().timestamp())}",
                        violation_type=ViolationType.DOUBLE_PARKING,
                        place_id=None,
                        track_id=track_id,
                        timestamp=datetime.utcnow(),
                        confidence=0.9,
                        description=f"Vehicle double-parked, blocking track {other.get('track_id')}",
                        vehicle_polygon=vehicle_polygon
                    )
        
        return None
    
    def check_blocking_exit(
        self,
        vehicle_polygon: Polygon,
        track_id: int
    ) -> Optional[ViolationRecord]:
        """
        Check if vehicle is blocking exit/entrance
        
        Args:
            vehicle_polygon: Vehicle segmentation polygon
            track_id: Vehicle track ID
            
        Returns:
            ViolationRecord if violation detected, None otherwise
        """
        for exit_zone in self.exit_zones:
            if vehicle_polygon.intersects(exit_zone):
                overlap = vehicle_polygon.intersection(exit_zone).area
                overlap_fraction = overlap / vehicle_polygon.area if vehicle_polygon.area > 0 else 0
                
                if overlap_fraction > 0.1:  # 10% overlap = blocking
                    return ViolationRecord(
                        violation_id=f"blocking_{track_id}_{int(datetime.utcnow().timestamp())}",
                        violation_type=ViolationType.BLOCKING_EXIT,
                        place_id=None,
                        track_id=track_id,
                        timestamp=datetime.utcnow(),
                        confidence=min(overlap_fraction * 2, 1.0),
                        description=f"Vehicle blocking exit/entrance ({overlap_fraction*100:.1f}% overlap)",
                        vehicle_polygon=vehicle_polygon
                    )
        
        return None
    
    def check_disabled_spot_misuse(
        self,
        place_id: int,
        track_id: int,
        has_disabled_permit: bool = False
    ) -> Optional[ViolationRecord]:
        """
        Check if non-disabled vehicle is using disabled spot
        
        Args:
            place_id: Parking place ID
            track_id: Vehicle track ID
            has_disabled_permit: Whether vehicle has disabled permit (from license plate recognition)
            
        Returns:
            ViolationRecord if violation detected, None otherwise
        """
        if place_id not in self.parking_places:
            return None
        
        place_data = self.parking_places[place_id]
        
        if place_data['type'] == 'disabled' and not has_disabled_permit:
            return ViolationRecord(
                violation_id=f"disabled_{place_id}_{track_id}_{int(datetime.utcnow().timestamp())}",
                violation_type=ViolationType.DISABLED_SPOT_MISUSE,
                place_id=place_id,
                track_id=track_id,
                timestamp=datetime.utcnow(),
                confidence=0.8,  # Lower confidence without permit verification
                description="Non-disabled vehicle in disabled parking spot",
                vehicle_polygon=None
            )
        
        return None
    
    def check_overstay(
        self,
        place_id: int,
        track_id: int,
        parked_duration_hours: float
    ) -> Optional[ViolationRecord]:
        """
        Check if vehicle exceeded time limit
        
        Args:
            place_id: Parking place ID
            track_id: Vehicle track ID
            parked_duration_hours: How long vehicle has been parked
            
        Returns:
            ViolationRecord if violation detected, None otherwise
        """
        if place_id not in self.parking_places:
            return None
        
        place_data = self.parking_places[place_id]
        time_limit = place_data.get('time_limit_hours')
        
        if time_limit and parked_duration_hours > time_limit:
            overstay_hours = parked_duration_hours - time_limit
            
            return ViolationRecord(
                violation_id=f"overstay_{place_id}_{track_id}_{int(datetime.utcnow().timestamp())}",
                violation_type=ViolationType.OVERSTAY,
                place_id=place_id,
                track_id=track_id,
                timestamp=datetime.utcnow(),
                confidence=1.0,
                description=f"Vehicle exceeded time limit by {overstay_hours:.1f} hours",
                vehicle_polygon=None
            )
        
        return None
    
    def check_wrong_orientation(
        self,
        vehicle_polygon: Polygon,
        place_id: int,
        track_id: int
    ) -> Optional[ViolationRecord]:
        """
        Check if vehicle is parked in wrong orientation
        
        Args:
            vehicle_polygon: Vehicle segmentation polygon
            place_id: Parking place ID
            track_id: Vehicle track ID
            
        Returns:
            ViolationRecord if violation detected, None otherwise
        """
        if place_id not in self.parking_places:
            return None
        
        place_data = self.parking_places[place_id]
        expected_orientation = place_data.get('expected_orientation')
        
        if expected_orientation is None:
            return None  # No orientation requirement
        
        # Calculate vehicle orientation from bounding box
        coords = np.array(vehicle_polygon.exterior.coords[:-1])
        
        if len(coords) < 2:
            return None
        
        # Use PCA to find principal axis
        centroid = coords.mean(axis=0)
        centered = coords - centroid
        cov = np.cov(centered.T)
        eigenvalues, eigenvectors = np.linalg.eig(cov)
        
        # Principal axis angle
        principal_axis = eigenvectors[:, np.argmax(eigenvalues)]
        vehicle_angle = np.degrees(np.arctan2(principal_axis[1], principal_axis[0]))
        
        # Normalize to 0-180 range
        vehicle_angle = vehicle_angle % 180
        expected_orientation = expected_orientation % 180
        
        # Calculate angle difference
        angle_diff = min(
            abs(vehicle_angle - expected_orientation),
            180 - abs(vehicle_angle - expected_orientation)
        )
        
        if angle_diff > self.orientation_tolerance:
            return ViolationRecord(
                violation_id=f"orientation_{place_id}_{track_id}_{int(datetime.utcnow().timestamp())}",
                violation_type=ViolationType.WRONG_ORIENTATION,
                place_id=place_id,
                track_id=track_id,
                timestamp=datetime.utcnow(),
                confidence=min(angle_diff / 90.0, 1.0),
                description=f"Vehicle orientation off by {angle_diff:.1f} degrees",
                vehicle_polygon=vehicle_polygon
            )
        
        return None
    
    def check_all_violations(
        self,
        vehicle_polygon: Polygon,
        track_id: int,
        place_id: Optional[int] = None,
        other_vehicles: List[Dict] = None,
        parked_duration_hours: Optional[float] = None,
        has_disabled_permit: bool = False
    ) -> List[ViolationRecord]:
        """
        Check all violation types for a vehicle
        
        Args:
            vehicle_polygon: Vehicle segmentation polygon
            track_id: Vehicle track ID
            place_id: Parking place ID (if known)
            other_vehicles: List of other vehicles
            parked_duration_hours: Parking duration
            has_disabled_permit: Whether vehicle has disabled permit
            
        Returns:
            List of detected violations
        """
        violations = []
        
        # Check outside lines
        if place_id is not None:
            violation = self.check_outside_lines(vehicle_polygon, place_id, track_id)
            if violation:
                violations.append(violation)
        
        # Check double parking
        if other_vehicles:
            violation = self.check_double_parking(vehicle_polygon, track_id, other_vehicles)
            if violation:
                violations.append(violation)
        
        # Check blocking exit
        violation = self.check_blocking_exit(vehicle_polygon, track_id)
        if violation:
            violations.append(violation)
        
        # Check disabled spot misuse
        if place_id is not None:
            violation = self.check_disabled_spot_misuse(place_id, track_id, has_disabled_permit)
            if violation:
                violations.append(violation)
        
        # Check overstay
        if place_id is not None and parked_duration_hours is not None:
            violation = self.check_overstay(place_id, track_id, parked_duration_hours)
            if violation:
                violations.append(violation)
        
        # Check wrong orientation
        if place_id is not None:
            violation = self.check_wrong_orientation(vehicle_polygon, place_id, track_id)
            if violation:
                violations.append(violation)
        
        # Store violations
        self.violations.extend(violations)
        
        return violations
    
    def get_violations(
        self,
        violation_type: Optional[ViolationType] = None,
        since: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get recorded violations
        
        Args:
            violation_type: Filter by violation type
            since: Filter by timestamp
            
        Returns:
            List of violation dictionaries
        """
        filtered = self.violations
        
        if violation_type:
            filtered = [v for v in filtered if v.violation_type == violation_type]
        
        if since:
            filtered = [v for v in filtered if v.timestamp >= since]
        
        return [
            {
                'violation_id': v.violation_id,
                'violation_type': v.violation_type.value,
                'place_id': v.place_id,
                'track_id': v.track_id,
                'timestamp': v.timestamp.isoformat(),
                'confidence': v.confidence,
                'description': v.description
            }
            for v in filtered
        ]
