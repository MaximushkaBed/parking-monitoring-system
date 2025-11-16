"""
Prometheus metrics module
Exposes system metrics for monitoring
"""

from prometheus_client import Counter, Gauge, Histogram, Summary, Info, generate_latest, REGISTRY
from prometheus_client.core import CollectorRegistry
from typing import Dict, Optional
import time
import logging

logger = logging.getLogger(__name__)


class ParkingMetrics:
    """
    Prometheus metrics for parking monitoring system
    
    Tracks:
    - Detection performance (FPS, latency)
    - Occupancy statistics
    - Camera health
    - API requests
    - Violations
    - System resources
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics
        
        Args:
            registry: Prometheus registry (default: global REGISTRY)
        """
        if registry is None:
            registry = REGISTRY
        
        self.registry = registry
        
        # System info
        self.system_info = Info(
            'parking_system',
            'Parking monitoring system information',
            registry=registry
        )
        self.system_info.info({
            'version': '1.0.0',
            'ml_model': 'YOLOv11-Seg',
            'tracker': 'ByteTrack'
        })
        
        # Detection metrics
        self.detections_total = Counter(
            'parking_detections_total',
            'Total number of vehicle detections',
            ['camera_id'],
            registry=registry
        )
        
        self.detection_fps = Gauge(
            'parking_detection_fps',
            'Detection frames per second',
            ['camera_id'],
            registry=registry
        )
        
        self.detection_latency = Histogram(
            'parking_detection_latency_seconds',
            'Detection processing latency',
            ['camera_id'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=registry
        )
        
        self.detection_confidence = Histogram(
            'parking_detection_confidence',
            'Detection confidence scores',
            ['camera_id'],
            buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0],
            registry=registry
        )
        
        # Tracking metrics
        self.tracks_active = Gauge(
            'parking_tracks_active',
            'Number of active vehicle tracks',
            ['camera_id'],
            registry=registry
        )
        
        self.tracks_total = Counter(
            'parking_tracks_total',
            'Total number of vehicle tracks created',
            ['camera_id'],
            registry=registry
        )
        
        self.track_duration = Histogram(
            'parking_track_duration_seconds',
            'Track duration (vehicle visibility time)',
            ['camera_id'],
            buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600],
            registry=registry
        )
        
        # Occupancy metrics
        self.occupancy_total = Gauge(
            'parking_occupancy_total',
            'Total number of parking places',
            ['zone_id'],
            registry=registry
        )
        
        self.occupancy_occupied = Gauge(
            'parking_occupancy_occupied',
            'Number of occupied parking places',
            ['zone_id'],
            registry=registry
        )
        
        self.occupancy_free = Gauge(
            'parking_occupancy_free',
            'Number of free parking places',
            ['zone_id'],
            registry=registry
        )
        
        self.occupancy_rate = Gauge(
            'parking_occupancy_rate',
            'Occupancy rate (0-1)',
            ['zone_id'],
            registry=registry
        )
        
        self.occupancy_events = Counter(
            'parking_occupancy_events_total',
            'Total occupancy events',
            ['event_type', 'zone_id'],  # event_type: occupied, freed
            registry=registry
        )
        
        self.parking_duration = Histogram(
            'parking_duration_seconds',
            'Parking duration',
            ['zone_id', 'place_type'],
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 28800, 86400],
            registry=registry
        )
        
        # Camera metrics
        self.camera_status = Gauge(
            'parking_camera_status',
            'Camera status (1=active, 0=inactive)',
            ['camera_id', 'camera_name'],
            registry=registry
        )
        
        self.camera_frames_total = Counter(
            'parking_camera_frames_total',
            'Total frames received from camera',
            ['camera_id'],
            registry=registry
        )
        
        self.camera_frames_dropped = Counter(
            'parking_camera_frames_dropped_total',
            'Total frames dropped',
            ['camera_id', 'reason'],  # reason: timeout, error, skip
            registry=registry
        )
        
        self.camera_reconnects = Counter(
            'parking_camera_reconnects_total',
            'Camera reconnection attempts',
            ['camera_id'],
            registry=registry
        )
        
        self.camera_errors = Counter(
            'parking_camera_errors_total',
            'Camera errors',
            ['camera_id', 'error_type'],
            registry=registry
        )
        
        # Violation metrics
        self.violations_total = Counter(
            'parking_violations_total',
            'Total parking violations detected',
            ['violation_type', 'zone_id'],
            registry=registry
        )
        
        self.violations_active = Gauge(
            'parking_violations_active',
            'Active (unresolved) violations',
            ['violation_type'],
            registry=registry
        )
        
        # API metrics
        self.api_requests_total = Counter(
            'parking_api_requests_total',
            'Total API requests',
            ['method', 'endpoint', 'status'],
            registry=registry
        )
        
        self.api_request_duration = Histogram(
            'parking_api_request_duration_seconds',
            'API request duration',
            ['method', 'endpoint'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
            registry=registry
        )
        
        # Multi-camera fusion metrics
        self.fusion_conflicts = Counter(
            'parking_fusion_conflicts_total',
            'Multi-camera fusion conflicts',
            ['place_id'],
            registry=registry
        )
        
        self.fusion_latency = Histogram(
            'parking_fusion_latency_seconds',
            'Multi-camera fusion processing latency',
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
            registry=registry
        )
        
        # IoU metrics
        self.iou_scores = Histogram(
            'parking_iou_scores',
            'IoU scores for occupancy detection',
            ['place_id'],
            buckets=[0.0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            registry=registry
        )
        
        # System resource metrics
        self.cpu_usage = Gauge(
            'parking_cpu_usage_percent',
            'CPU usage percentage',
            registry=registry
        )
        
        self.memory_usage = Gauge(
            'parking_memory_usage_bytes',
            'Memory usage in bytes',
            registry=registry
        )
        
        self.gpu_usage = Gauge(
            'parking_gpu_usage_percent',
            'GPU usage percentage',
            ['gpu_id'],
            registry=registry
        )
        
        self.gpu_memory_usage = Gauge(
            'parking_gpu_memory_usage_bytes',
            'GPU memory usage in bytes',
            ['gpu_id'],
            registry=registry
        )
    
    # Detection methods
    def record_detection(self, camera_id: str, confidence: float):
        """Record a vehicle detection"""
        self.detections_total.labels(camera_id=camera_id).inc()
        self.detection_confidence.labels(camera_id=camera_id).observe(confidence)
    
    def update_detection_fps(self, camera_id: str, fps: float):
        """Update detection FPS"""
        self.detection_fps.labels(camera_id=camera_id).set(fps)
    
    def record_detection_latency(self, camera_id: str, latency: float):
        """Record detection processing latency"""
        self.detection_latency.labels(camera_id=camera_id).observe(latency)
    
    # Tracking methods
    def update_active_tracks(self, camera_id: str, count: int):
        """Update number of active tracks"""
        self.tracks_active.labels(camera_id=camera_id).set(count)
    
    def record_new_track(self, camera_id: str):
        """Record creation of new track"""
        self.tracks_total.labels(camera_id=camera_id).inc()
    
    def record_track_duration(self, camera_id: str, duration: float):
        """Record track duration"""
        self.track_duration.labels(camera_id=camera_id).observe(duration)
    
    # Occupancy methods
    def update_occupancy(
        self,
        zone_id: str,
        total: int,
        occupied: int,
        free: int
    ):
        """Update occupancy statistics"""
        self.occupancy_total.labels(zone_id=zone_id).set(total)
        self.occupancy_occupied.labels(zone_id=zone_id).set(occupied)
        self.occupancy_free.labels(zone_id=zone_id).set(free)
        
        rate = occupied / total if total > 0 else 0.0
        self.occupancy_rate.labels(zone_id=zone_id).set(rate)
    
    def record_occupancy_event(self, event_type: str, zone_id: str):
        """Record occupancy event (occupied/freed)"""
        self.occupancy_events.labels(
            event_type=event_type,
            zone_id=zone_id
        ).inc()
    
    def record_parking_duration(
        self,
        zone_id: str,
        place_type: str,
        duration: float
    ):
        """Record parking duration"""
        self.parking_duration.labels(
            zone_id=zone_id,
            place_type=place_type
        ).observe(duration)
    
    # Camera methods
    def update_camera_status(
        self,
        camera_id: str,
        camera_name: str,
        is_active: bool
    ):
        """Update camera status"""
        self.camera_status.labels(
            camera_id=camera_id,
            camera_name=camera_name
        ).set(1 if is_active else 0)
    
    def record_camera_frame(self, camera_id: str):
        """Record received frame"""
        self.camera_frames_total.labels(camera_id=camera_id).inc()
    
    def record_dropped_frame(self, camera_id: str, reason: str):
        """Record dropped frame"""
        self.camera_frames_dropped.labels(
            camera_id=camera_id,
            reason=reason
        ).inc()
    
    def record_camera_reconnect(self, camera_id: str):
        """Record camera reconnection"""
        self.camera_reconnects.labels(camera_id=camera_id).inc()
    
    def record_camera_error(self, camera_id: str, error_type: str):
        """Record camera error"""
        self.camera_errors.labels(
            camera_id=camera_id,
            error_type=error_type
        ).inc()
    
    # Violation methods
    def record_violation(self, violation_type: str, zone_id: str):
        """Record parking violation"""
        self.violations_total.labels(
            violation_type=violation_type,
            zone_id=zone_id
        ).inc()
    
    def update_active_violations(self, violation_type: str, count: int):
        """Update active violations count"""
        self.violations_active.labels(violation_type=violation_type).set(count)
    
    # API methods
    def record_api_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float
    ):
        """Record API request"""
        self.api_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=str(status)
        ).inc()
        
        self.api_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    # Fusion methods
    def record_fusion_conflict(self, place_id: str):
        """Record multi-camera fusion conflict"""
        self.fusion_conflicts.labels(place_id=place_id).inc()
    
    def record_fusion_latency(self, latency: float):
        """Record fusion processing latency"""
        self.fusion_latency.observe(latency)
    
    # IoU methods
    def record_iou_score(self, place_id: str, iou: float):
        """Record IoU score"""
        self.iou_scores.labels(place_id=place_id).observe(iou)
    
    # System resource methods
    def update_cpu_usage(self, percent: float):
        """Update CPU usage"""
        self.cpu_usage.set(percent)
    
    def update_memory_usage(self, bytes_used: int):
        """Update memory usage"""
        self.memory_usage.set(bytes_used)
    
    def update_gpu_usage(self, gpu_id: str, percent: float):
        """Update GPU usage"""
        self.gpu_usage.labels(gpu_id=gpu_id).set(percent)
    
    def update_gpu_memory(self, gpu_id: str, bytes_used: int):
        """Update GPU memory usage"""
        self.gpu_memory_usage.labels(gpu_id=gpu_id).set(bytes_used)
    
    def get_metrics(self) -> bytes:
        """
        Get metrics in Prometheus format
        
        Returns:
            Metrics as bytes
        """
        return generate_latest(self.registry)


# Global metrics instance
_metrics: Optional[ParkingMetrics] = None


def get_metrics() -> ParkingMetrics:
    """Get global metrics instance"""
    global _metrics
    if _metrics is None:
        _metrics = ParkingMetrics()
    return _metrics


def reset_metrics():
    """Reset global metrics instance"""
    global _metrics
    _metrics = None
