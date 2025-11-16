import cv2
import numpy as np
from typing import Optional, Callable, Dict
import threading
import time
import logging
from queue import Queue, Empty
from enum import Enum

logger = logging.getLogger(__name__)


class CameraType(Enum):
    RTSP = "rtsp"
    HTTP = "http"
    MOTION_ACTIVATED = "motion_activated"
    FILE = "file"  # For testing with video files


class CameraConnector:
    """
    Universal camera connector supporting RTSP, HTTP, motion-activated cameras
    """
    
    def __init__(
        self,
        camera_id: int,
        source: str,
        camera_type: CameraType = CameraType.RTSP,
        reconnect_delay: int = 5,
        timeout: int = 10,
        frame_buffer_size: int = 1
    ):
        """
        Initialize camera connector
        
        Args:
            camera_id: Unique camera identifier
            source: Camera source (RTSP URL, HTTP URL, or file path)
            camera_type: Type of camera connection
            reconnect_delay: Seconds to wait before reconnection attempt
            timeout: Connection timeout in seconds
            frame_buffer_size: Size of frame buffer (1 = only latest frame)
        """
        self.camera_id = camera_id
        self.source = source
        self.camera_type = camera_type
        self.reconnect_delay = reconnect_delay
        self.timeout = timeout
        
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.is_connected = False
        
        self.frame_queue = Queue(maxsize=frame_buffer_size)
        self.capture_thread: Optional[threading.Thread] = None
        
        self.frame_count = 0
        self.last_frame_time = None
        self.fps = 0.0
        
        self._lock = threading.Lock()
    
    def connect(self) -> bool:
        """
        Connect to camera
        
        Returns:
            True if connection successful
        """
        try:
            logger.info(f"Connecting to camera {self.camera_id}: {self.source}")
            
            if self.camera_type == CameraType.RTSP:
                # RTSP with optimizations
                self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
                self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            elif self.camera_type == CameraType.HTTP:
                # HTTP stream
                self.cap = cv2.VideoCapture(self.source)
            
            elif self.camera_type == CameraType.FILE:
                # Video file (for testing)
                self.cap = cv2.VideoCapture(self.source)
            
            else:
                logger.error(f"Unsupported camera type: {self.camera_type}")
                return False
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera {self.camera_id}")
                return False
            
            # Test read
            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.error(f"Failed to read frame from camera {self.camera_id}")
                self.cap.release()
                return False
            
            self.is_connected = True
            logger.info(f"Camera {self.camera_id} connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Connection error for camera {self.camera_id}: {e}")
            return False
    
    def start(self):
        """Start capture thread"""
        if self.is_running:
            logger.warning(f"Camera {self.camera_id} already running")
            return
        
        if not self.is_connected:
            if not self.connect():
                return
        
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        logger.info(f"Camera {self.camera_id} capture started")
    
    def stop(self):
        """Stop capture thread"""
        self.is_running = False
        
        if self.capture_thread is not None:
            self.capture_thread.join(timeout=5)
        
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        
        self.is_connected = False
        logger.info(f"Camera {self.camera_id} stopped")
    
    def _capture_loop(self):
        """Main capture loop (runs in separate thread)"""
        consecutive_failures = 0
        max_failures = 10
        
        while self.is_running:
            try:
                if not self.is_connected:
                    logger.info(f"Attempting to reconnect camera {self.camera_id}")
                    if self.connect():
                        consecutive_failures = 0
                    else:
                        time.sleep(self.reconnect_delay)
                        continue
                
                ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    consecutive_failures += 1
                    logger.warning(f"Failed to read frame from camera {self.camera_id} ({consecutive_failures}/{max_failures})")
                    
                    if consecutive_failures >= max_failures:
                        logger.error(f"Too many failures for camera {self.camera_id}, reconnecting...")
                        self.is_connected = False
                        if self.cap is not None:
                            self.cap.release()
                            self.cap = None
                        time.sleep(self.reconnect_delay)
                        consecutive_failures = 0
                    continue
                
                # Reset failure counter on successful read
                consecutive_failures = 0
                
                # Update stats
                current_time = time.time()
                if self.last_frame_time is not None:
                    frame_interval = current_time - self.last_frame_time
                    self.fps = 1.0 / frame_interval if frame_interval > 0 else 0.0
                self.last_frame_time = current_time
                self.frame_count += 1
                
                # Put frame in queue (drop old frames if queue is full)
                try:
                    if self.frame_queue.full():
                        try:
                            self.frame_queue.get_nowait()
                        except Empty:
                            pass
                    self.frame_queue.put((frame, self.frame_count, current_time), block=False)
                except:
                    pass
                
            except Exception as e:
                logger.error(f"Capture loop error for camera {self.camera_id}: {e}")
                consecutive_failures += 1
                time.sleep(0.1)
    
    def get_frame(self, timeout: float = 1.0) -> Optional[tuple]:
        """
        Get latest frame from queue
        
        Args:
            timeout: Maximum time to wait for frame
            
        Returns:
            (frame, frame_number, timestamp) or None
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except Empty:
            return None
    
    def get_stats(self) -> Dict:
        """Get camera statistics"""
        return {
            'camera_id': self.camera_id,
            'is_connected': self.is_connected,
            'is_running': self.is_running,
            'frame_count': self.frame_count,
            'fps': round(self.fps, 2),
            'last_frame_time': self.last_frame_time
        }


class CameraManager:
    """
    Manage multiple camera connectors
    """
    
    def __init__(self):
        self.cameras: Dict[int, CameraConnector] = {}
        self._lock = threading.Lock()
    
    def add_camera(
        self,
        camera_id: int,
        source: str,
        camera_type: CameraType = CameraType.RTSP,
        auto_start: bool = True
    ) -> bool:
        """
        Add and optionally start a camera
        
        Args:
            camera_id: Unique camera identifier
            source: Camera source URL or path
            camera_type: Type of camera
            auto_start: Whether to start capture immediately
            
        Returns:
            True if camera added successfully
        """
        with self._lock:
            if camera_id in self.cameras:
                logger.warning(f"Camera {camera_id} already exists")
                return False
            
            connector = CameraConnector(
                camera_id=camera_id,
                source=source,
                camera_type=camera_type
            )
            
            self.cameras[camera_id] = connector
            
            if auto_start:
                connector.start()
            
            logger.info(f"Camera {camera_id} added to manager")
            return True
    
    def remove_camera(self, camera_id: int):
        """Remove and stop a camera"""
        with self._lock:
            if camera_id in self.cameras:
                self.cameras[camera_id].stop()
                del self.cameras[camera_id]
                logger.info(f"Camera {camera_id} removed from manager")
    
    def get_camera(self, camera_id: int) -> Optional[CameraConnector]:
        """Get camera connector by ID"""
        return self.cameras.get(camera_id)
    
    def get_all_stats(self) -> Dict[int, Dict]:
        """Get statistics for all cameras"""
        return {cid: cam.get_stats() for cid, cam in self.cameras.items()}
    
    def stop_all(self):
        """Stop all cameras"""
        with self._lock:
            for camera in self.cameras.values():
                camera.stop()
            logger.info("All cameras stopped")
