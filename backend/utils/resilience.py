"""
Resilience and fault tolerance module
Implements graceful degradation, state persistence, and recovery
"""

import json
import pickle
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import threading
import time

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class CameraState:
    """Persisted camera state"""
    camera_id: int
    last_frame_time: datetime
    consecutive_failures: int
    last_known_status: str
    last_occupancy: Dict[int, bool]  # place_id -> is_occupied
    metadata: Dict[str, Any]


@dataclass
class SystemState:
    """Persisted system state"""
    timestamp: datetime
    cameras: Dict[int, CameraState]
    global_occupancy: Dict[int, bool]
    active_tracks: Dict[int, Dict]
    violations: list


class StateManager:
    """
    Manages system state persistence and recovery
    
    Features:
    - Periodic state snapshots
    - Recovery from crashes
    - State rollback
    - Graceful degradation
    """
    
    def __init__(
        self,
        state_dir: str = "./state",
        snapshot_interval: int = 60,  # seconds
        max_snapshots: int = 10
    ):
        """
        Initialize state manager
        
        Args:
            state_dir: Directory for state files
            snapshot_interval: Snapshot interval in seconds
            max_snapshots: Maximum number of snapshots to keep
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.snapshot_interval = snapshot_interval
        self.max_snapshots = max_snapshots
        
        self.current_state: Optional[SystemState] = None
        self.last_snapshot_time = datetime.utcnow()
        
        self._snapshot_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        logger.info(f"StateManager initialized: {state_dir}")
    
    def start_auto_snapshot(self):
        """Start automatic snapshot thread"""
        if self._snapshot_thread and self._snapshot_thread.is_alive():
            logger.warning("Auto-snapshot already running")
            return
        
        self._stop_event.clear()
        self._snapshot_thread = threading.Thread(
            target=self._snapshot_loop,
            daemon=True
        )
        self._snapshot_thread.start()
        logger.info("Auto-snapshot started")
    
    def stop_auto_snapshot(self):
        """Stop automatic snapshot thread"""
        if not self._snapshot_thread:
            return
        
        self._stop_event.set()
        self._snapshot_thread.join(timeout=5)
        logger.info("Auto-snapshot stopped")
    
    def _snapshot_loop(self):
        """Automatic snapshot loop"""
        while not self._stop_event.is_set():
            try:
                time.sleep(self.snapshot_interval)
                
                if self.current_state:
                    self.save_snapshot(self.current_state)
                    self._cleanup_old_snapshots()
            
            except Exception as e:
                logger.error(f"Error in snapshot loop: {e}")
    
    def save_snapshot(self, state: SystemState):
        """
        Save state snapshot
        
        Args:
            state: System state to save
        """
        try:
            timestamp = datetime.utcnow()
            filename = f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.pkl"
            filepath = self.state_dir / filename
            
            with open(filepath, 'wb') as f:
                pickle.dump(state, f)
            
            self.last_snapshot_time = timestamp
            logger.info(f"State snapshot saved: {filename}")
        
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
    
    def load_latest_snapshot(self) -> Optional[SystemState]:
        """
        Load latest state snapshot
        
        Returns:
            Latest system state or None
        """
        try:
            snapshots = sorted(self.state_dir.glob("snapshot_*.pkl"), reverse=True)
            
            if not snapshots:
                logger.warning("No snapshots found")
                return None
            
            latest = snapshots[0]
            
            with open(latest, 'rb') as f:
                state = pickle.load(f)
            
            logger.info(f"Loaded snapshot: {latest.name}")
            self.current_state = state
            return state
        
        except Exception as e:
            logger.error(f"Failed to load snapshot: {e}")
            return None
    
    def _cleanup_old_snapshots(self):
        """Remove old snapshots beyond max_snapshots"""
        try:
            snapshots = sorted(self.state_dir.glob("snapshot_*.pkl"), reverse=True)
            
            for snapshot in snapshots[self.max_snapshots:]:
                snapshot.unlink()
                logger.debug(f"Removed old snapshot: {snapshot.name}")
        
        except Exception as e:
            logger.error(f"Failed to cleanup snapshots: {e}")
    
    def update_camera_state(
        self,
        camera_id: int,
        last_frame_time: datetime,
        status: str,
        occupancy: Dict[int, bool],
        metadata: Dict[str, Any] = None
    ):
        """Update camera state"""
        if self.current_state is None:
            self.current_state = SystemState(
                timestamp=datetime.utcnow(),
                cameras={},
                global_occupancy={},
                active_tracks={},
                violations=[]
            )
        
        if camera_id not in self.current_state.cameras:
            self.current_state.cameras[camera_id] = CameraState(
                camera_id=camera_id,
                last_frame_time=last_frame_time,
                consecutive_failures=0,
                last_known_status=status,
                last_occupancy=occupancy,
                metadata=metadata or {}
            )
        else:
            camera_state = self.current_state.cameras[camera_id]
            camera_state.last_frame_time = last_frame_time
            camera_state.last_known_status = status
            camera_state.last_occupancy = occupancy
            if metadata:
                camera_state.metadata.update(metadata)
    
    def get_camera_last_occupancy(self, camera_id: int) -> Dict[int, bool]:
        """Get last known occupancy for camera"""
        if not self.current_state or camera_id not in self.current_state.cameras:
            return {}
        
        return self.current_state.cameras[camera_id].last_occupancy.copy()


class CircuitBreaker:
    """
    Circuit breaker pattern for fault tolerance
    
    States:
    - CLOSED: Normal operation
    - OPEN: Failures detected, requests blocked
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,  # seconds
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Failures before opening circuit
            timeout: Timeout before trying again (seconds)
            success_threshold: Successes needed to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout)
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"
        
        self._lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception if circuit is open
        """
        with self._lock:
            if self.state == "OPEN":
                if datetime.utcnow() - self.last_failure_time < self.timeout:
                    raise Exception("Circuit breaker is OPEN")
                else:
                    self.state = "HALF_OPEN"
                    self.success_count = 0
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            self.failure_count = 0
            
            if self.state == "HALF_OPEN":
                self.success_count += 1
                
                if self.success_count >= self.success_threshold:
                    self.state = "CLOSED"
                    logger.info("Circuit breaker CLOSED")
    
    def _on_failure(self):
        """Handle failed call"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")
    
    def get_state(self) -> str:
        """Get current circuit breaker state"""
        return self.state
    
    def reset(self):
        """Reset circuit breaker"""
        with self._lock:
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.state = "CLOSED"


class GracefulDegradation:
    """
    Implements graceful degradation strategies
    
    When services fail:
    - Use cached data
    - Reduce functionality
    - Provide fallback options
    """
    
    def __init__(self, state_manager: StateManager):
        """
        Initialize graceful degradation
        
        Args:
            state_manager: State manager for cached data
        """
        self.state_manager = state_manager
        self.service_status: Dict[str, ServiceStatus] = {}
        self.fallback_data: Dict[str, Any] = {}
    
    def set_service_status(self, service: str, status: ServiceStatus):
        """Set service health status"""
        self.service_status[service] = status
        logger.info(f"Service {service} status: {status.value}")
    
    def get_service_status(self, service: str) -> ServiceStatus:
        """Get service health status"""
        return self.service_status.get(service, ServiceStatus.UNAVAILABLE)
    
    def is_service_available(self, service: str) -> bool:
        """Check if service is available"""
        status = self.get_service_status(service)
        return status in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]
    
    def get_occupancy_with_fallback(
        self,
        camera_id: int,
        fetch_func: Callable
    ) -> Dict[int, bool]:
        """
        Get occupancy data with fallback to cached data
        
        Args:
            camera_id: Camera identifier
            fetch_func: Function to fetch current data
            
        Returns:
            Occupancy data (current or cached)
        """
        try:
            # Try to get current data
            data = fetch_func()
            
            # Update cache
            self.fallback_data[f"occupancy_{camera_id}"] = data
            
            return data
        
        except Exception as e:
            logger.warning(f"Failed to fetch occupancy for camera {camera_id}: {e}")
            
            # Try cached data
            cached = self.fallback_data.get(f"occupancy_{camera_id}")
            if cached:
                logger.info(f"Using cached occupancy for camera {camera_id}")
                return cached
            
            # Try state manager
            last_known = self.state_manager.get_camera_last_occupancy(camera_id)
            if last_known:
                logger.info(f"Using last known occupancy for camera {camera_id}")
                return last_known
            
            # No data available
            logger.error(f"No occupancy data available for camera {camera_id}")
            return {}
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get overall system health status
        
        Returns:
            Health status dictionary
        """
        healthy_services = sum(
            1 for status in self.service_status.values()
            if status == ServiceStatus.HEALTHY
        )
        
        degraded_services = sum(
            1 for status in self.service_status.values()
            if status == ServiceStatus.DEGRADED
        )
        
        unavailable_services = sum(
            1 for status in self.service_status.values()
            if status == ServiceStatus.UNAVAILABLE
        )
        
        total_services = len(self.service_status)
        
        if total_services == 0:
            overall_status = ServiceStatus.UNAVAILABLE
        elif unavailable_services > 0:
            overall_status = ServiceStatus.DEGRADED
        elif degraded_services > 0:
            overall_status = ServiceStatus.DEGRADED
        else:
            overall_status = ServiceStatus.HEALTHY
        
        return {
            'overall_status': overall_status.value,
            'healthy_services': healthy_services,
            'degraded_services': degraded_services,
            'unavailable_services': unavailable_services,
            'total_services': total_services,
            'services': {
                service: status.value
                for service, status in self.service_status.items()
            }
        }


class AlertManager:
    """
    Manages system alerts for critical errors
    
    Sends alerts when:
    - Camera disconnects
    - Detection service fails
    - Database errors
    - High violation rates
    """
    
    def __init__(self, alert_callback: Optional[Callable] = None):
        """
        Initialize alert manager
        
        Args:
            alert_callback: Function to call when alert is triggered
        """
        self.alert_callback = alert_callback
        self.alert_history: list = []
        self.alert_cooldown: Dict[str, datetime] = {}
        self.cooldown_period = timedelta(minutes=5)
    
    def send_alert(
        self,
        alert_type: str,
        severity: str,  # info, warning, error, critical
        message: str,
        metadata: Dict[str, Any] = None
    ):
        """
        Send system alert
        
        Args:
            alert_type: Alert type identifier
            severity: Alert severity level
            message: Alert message
            metadata: Additional metadata
        """
        # Check cooldown
        if alert_type in self.alert_cooldown:
            last_alert = self.alert_cooldown[alert_type]
            if datetime.utcnow() - last_alert < self.cooldown_period:
                logger.debug(f"Alert {alert_type} in cooldown, skipping")
                return
        
        alert = {
            'alert_type': alert_type,
            'severity': severity,
            'message': message,
            'metadata': metadata or {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.alert_history.append(alert)
        self.alert_cooldown[alert_type] = datetime.utcnow()
        
        logger.log(
            logging.CRITICAL if severity == 'critical' else
            logging.ERROR if severity == 'error' else
            logging.WARNING if severity == 'warning' else
            logging.INFO,
            f"ALERT [{severity.upper()}] {alert_type}: {message}"
        )
        
        # Call callback if provided
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def get_recent_alerts(self, limit: int = 100) -> list:
        """Get recent alerts"""
        return self.alert_history[-limit:]
