"""
Advanced analytics module
Provides heatmaps, statistics, and insights
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class OccupancyRecord:
    """Single occupancy record"""
    place_id: int
    track_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None


class ParkingAnalytics:
    """
    Advanced parking analytics
    
    Provides:
    - Heatmap of place popularity
    - Average duration statistics
    - Turnover rates
    - Peak hours analysis
    - Anomaly detection
    """
    
    def __init__(self):
        """Initialize analytics"""
        self.occupancy_history: List[OccupancyRecord] = []
        self.place_metadata: Dict[int, Dict] = {}  # place_id -> {zone, row, type, etc}
    
    def add_place_metadata(
        self,
        place_id: int,
        zone_id: Optional[int] = None,
        row: Optional[str] = None,
        place_type: str = "regular"
    ):
        """
        Add metadata for a place
        
        Args:
            place_id: Place identifier
            zone_id: Zone identifier
            row: Row identifier (e.g., "A", "B1")
            place_type: Type of place (regular, disabled, family, vip, electric, short_term)
        """
        self.place_metadata[place_id] = {
            'zone_id': zone_id,
            'row': row,
            'type': place_type
        }
    
    def record_occupancy_event(
        self,
        place_id: int,
        track_id: int,
        event_type: str,
        timestamp: datetime
    ):
        """
        Record an occupancy event
        
        Args:
            place_id: Place identifier
            track_id: Vehicle track ID
            event_type: 'occupied' or 'freed'
            timestamp: Event timestamp
        """
        if event_type == 'occupied':
            # Start new occupancy
            record = OccupancyRecord(
                place_id=place_id,
                track_id=track_id,
                start_time=timestamp
            )
            self.occupancy_history.append(record)
        
        elif event_type == 'freed':
            # Find matching occupancy and close it
            for record in reversed(self.occupancy_history):
                if (record.place_id == place_id and 
                    record.track_id == track_id and 
                    record.end_time is None):
                    
                    record.end_time = timestamp
                    record.duration_seconds = (timestamp - record.start_time).total_seconds()
                    break
    
    def get_heatmap(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        group_by: str = "place"  # 'place', 'zone', 'row'
    ) -> Dict[str, float]:
        """
        Generate heatmap of place usage
        
        Args:
            start_time: Start of analysis period
            end_time: End of analysis period
            group_by: Grouping level ('place', 'zone', 'row')
            
        Returns:
            Dict of identifier -> usage_score (0.0 to 1.0)
        """
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(days=7)
        
        # Count occupancies per identifier
        usage_counts = defaultdict(int)
        total_duration = defaultdict(float)
        
        for record in self.occupancy_history:
            # Filter by time range
            if record.start_time < start_time or record.start_time > end_time:
                continue
            
            # Determine identifier based on grouping
            if group_by == "place":
                identifier = str(record.place_id)
            elif group_by == "zone":
                metadata = self.place_metadata.get(record.place_id, {})
                zone_id = metadata.get('zone_id')
                if zone_id is None:
                    continue
                identifier = f"zone_{zone_id}"
            elif group_by == "row":
                metadata = self.place_metadata.get(record.place_id, {})
                row = metadata.get('row')
                if row is None:
                    continue
                identifier = f"row_{row}"
            else:
                continue
            
            usage_counts[identifier] += 1
            
            if record.duration_seconds:
                total_duration[identifier] += record.duration_seconds
        
        # Normalize to 0-1 scale
        if not usage_counts:
            return {}
        
        max_count = max(usage_counts.values())
        
        heatmap = {
            identifier: count / max_count
            for identifier, count in usage_counts.items()
        }
        
        return heatmap
    
    def get_average_duration(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        zone_id: Optional[int] = None,
        place_type: Optional[str] = None
    ) -> Dict:
        """
        Calculate average parking duration
        
        Args:
            start_time: Start of analysis period
            end_time: End of analysis period
            zone_id: Filter by zone
            place_type: Filter by place type
            
        Returns:
            Statistics dictionary
        """
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(days=7)
        
        durations = []
        
        for record in self.occupancy_history:
            # Filter by time
            if record.start_time < start_time or record.start_time > end_time:
                continue
            
            # Filter by zone
            if zone_id is not None:
                metadata = self.place_metadata.get(record.place_id, {})
                if metadata.get('zone_id') != zone_id:
                    continue
            
            # Filter by type
            if place_type is not None:
                metadata = self.place_metadata.get(record.place_id, {})
                if metadata.get('type') != place_type:
                    continue
            
            # Only completed occupancies
            if record.duration_seconds is not None:
                durations.append(record.duration_seconds)
        
        if not durations:
            return {
                'count': 0,
                'average_seconds': 0.0,
                'average_minutes': 0.0,
                'average_hours': 0.0,
                'median_seconds': 0.0,
                'min_seconds': 0.0,
                'max_seconds': 0.0
            }
        
        durations_array = np.array(durations)
        
        return {
            'count': len(durations),
            'average_seconds': float(np.mean(durations_array)),
            'average_minutes': float(np.mean(durations_array) / 60),
            'average_hours': float(np.mean(durations_array) / 3600),
            'median_seconds': float(np.median(durations_array)),
            'min_seconds': float(np.min(durations_array)),
            'max_seconds': float(np.max(durations_array)),
            'std_seconds': float(np.std(durations_array))
        }
    
    def get_turnover_rate(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        zone_id: Optional[int] = None
    ) -> Dict:
        """
        Calculate turnover rate (vehicles per day per place)
        
        Args:
            start_time: Start of analysis period
            end_time: End of analysis period
            zone_id: Filter by zone
            
        Returns:
            Turnover statistics
        """
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(days=7)
        
        period_days = (end_time - start_time).total_seconds() / 86400
        
        # Count occupancies per place
        place_counts = defaultdict(int)
        
        for record in self.occupancy_history:
            if record.start_time < start_time or record.start_time > end_time:
                continue
            
            if zone_id is not None:
                metadata = self.place_metadata.get(record.place_id, {})
                if metadata.get('zone_id') != zone_id:
                    continue
            
            place_counts[record.place_id] += 1
        
        if not place_counts:
            return {
                'turnover_rate': 0.0,
                'period_days': period_days,
                'total_occupancies': 0,
                'unique_places': 0
            }
        
        total_occupancies = sum(place_counts.values())
        unique_places = len(place_counts)
        
        # Turnover = total occupancies / (places * days)
        turnover_rate = total_occupancies / (unique_places * period_days) if period_days > 0 else 0.0
        
        return {
            'turnover_rate': float(turnover_rate),
            'period_days': period_days,
            'total_occupancies': total_occupancies,
            'unique_places': unique_places
        }
    
    def get_peak_hours(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[int, int]:
        """
        Analyze peak hours (hourly occupancy counts)
        
        Args:
            start_time: Start of analysis period
            end_time: End of analysis period
            
        Returns:
            Dict of hour (0-23) -> occupancy_count
        """
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(days=7)
        
        hour_counts = defaultdict(int)
        
        for record in self.occupancy_history:
            if record.start_time < start_time or record.start_time > end_time:
                continue
            
            hour = record.start_time.hour
            hour_counts[hour] += 1
        
        # Fill missing hours with 0
        result = {hour: hour_counts.get(hour, 0) for hour in range(24)}
        
        return result
    
    def detect_anomalies(
        self,
        threshold_hours: float = 24.0,
        current_time: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Detect anomalies (long-stay vehicles)
        
        Args:
            threshold_hours: Duration threshold for anomaly
            current_time: Current time (default: now)
            
        Returns:
            List of anomaly records
        """
        if current_time is None:
            current_time = datetime.utcnow()
        
        threshold_seconds = threshold_hours * 3600
        anomalies = []
        
        for record in self.occupancy_history:
            # Check completed occupancies
            if record.duration_seconds and record.duration_seconds > threshold_seconds:
                anomalies.append({
                    'place_id': record.place_id,
                    'track_id': record.track_id,
                    'start_time': record.start_time.isoformat(),
                    'end_time': record.end_time.isoformat() if record.end_time else None,
                    'duration_hours': record.duration_seconds / 3600,
                    'status': 'completed'
                })
            
            # Check ongoing occupancies
            elif record.end_time is None:
                duration = (current_time - record.start_time).total_seconds()
                if duration > threshold_seconds:
                    anomalies.append({
                        'place_id': record.place_id,
                        'track_id': record.track_id,
                        'start_time': record.start_time.isoformat(),
                        'end_time': None,
                        'duration_hours': duration / 3600,
                        'status': 'ongoing'
                    })
        
        return anomalies
    
    def get_zone_statistics(self) -> Dict[int, Dict]:
        """
        Get statistics per zone
        
        Returns:
            Dict of zone_id -> statistics
        """
        zone_stats = defaultdict(lambda: {
            'total_places': 0,
            'total_occupancies': 0,
            'total_duration_hours': 0.0
        })
        
        # Count places per zone
        for place_id, metadata in self.place_metadata.items():
            zone_id = metadata.get('zone_id')
            if zone_id is not None:
                zone_stats[zone_id]['total_places'] += 1
        
        # Aggregate occupancy data
        for record in self.occupancy_history:
            metadata = self.place_metadata.get(record.place_id, {})
            zone_id = metadata.get('zone_id')
            
            if zone_id is not None:
                zone_stats[zone_id]['total_occupancies'] += 1
                
                if record.duration_seconds:
                    zone_stats[zone_id]['total_duration_hours'] += record.duration_seconds / 3600
        
        # Calculate averages
        for zone_id, stats in zone_stats.items():
            if stats['total_occupancies'] > 0:
                stats['average_duration_hours'] = stats['total_duration_hours'] / stats['total_occupancies']
            else:
                stats['average_duration_hours'] = 0.0
        
        return dict(zone_stats)
    
    def export_summary(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """
        Export comprehensive summary for reporting
        
        Args:
            start_time: Start of analysis period
            end_time: End of analysis period
            
        Returns:
            Complete analytics summary
        """
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(days=7)
        
        return {
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'days': (end_time - start_time).total_seconds() / 86400
            },
            'heatmap': {
                'by_place': self.get_heatmap(start_time, end_time, 'place'),
                'by_zone': self.get_heatmap(start_time, end_time, 'zone'),
                'by_row': self.get_heatmap(start_time, end_time, 'row')
            },
            'duration': self.get_average_duration(start_time, end_time),
            'turnover': self.get_turnover_rate(start_time, end_time),
            'peak_hours': self.get_peak_hours(start_time, end_time),
            'anomalies': self.detect_anomalies(24.0, end_time),
            'zone_statistics': self.get_zone_statistics()
        }
