import cv2
import numpy as np
from typing import Dict, List, Optional
import threading
import time
import logging
from datetime import datetime

from backend.ml.vehicle_detector import VehicleDetector
from backend.ml.tracker import ByteTracker
from backend.utils.homography import HomographyCalibrator
from backend.utils.occupancy import ParkingMonitorManager
from backend.services.camera_connector import CameraConnector
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """
    Main processing pipeline: Camera -> Detection -> Tracking -> Homography -> Occupancy
    """
    
    def __init__(
        self,
        camera_id: int,
        camera_connector: CameraConnector,
        parking_places: List[Dict],  # [{id, polygon}, ...]
        homography_matrix: Optional[List[List[float]]] = None
    ):
        """
        Initialize processing pipeline for a camera
        
        Args:
            camera_id: Camera identifier
            camera_connector: Camera connector instance
            parking_places: List of parking places with polygons
            homography_matrix: Optional pre-computed homography matrix
        """
        self.camera_id = camera_id
        self.camera = camera_connector
        
        # Initialize ML components
        self.detector = VehicleDetector(
            model_path=settings.YOLO_MODEL_PATH,
            confidence_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
            iou_threshold=settings.YOLO_IOU_THRESHOLD,
            device=settings.YOLO_DEVICE,
            vehicle_classes=settings.VEHICLE_CLASSES
        )
        
        self.tracker = ByteTracker(
            max_age=settings.MAX_AGE,
            min_hits=settings.MIN_HITS,
            iou_threshold=settings.IOU_THRESHOLD
        )
        
        self.homography = HomographyCalibrator()
        if homography_matrix is not None:
            self.homography.set_matrix(homography_matrix)
        
        # Initialize occupancy monitoring
        self.monitor_manager = ParkingMonitorManager()
        for place in parking_places:
            self.monitor_manager.add_place(
                place_id=place['id'],
                polygon=place['polygon'],
                min_frames_occupied=settings.MIN_FRAMES_OCCUPIED,
                min_frames_free=settings.MIN_FRAMES_FREE
            )
        
        # State
        self.is_running = False
        self.processing_thread: Optional[threading.Thread] = None
        self.frame_count = 0
        self.fps = 0.0
        self.last_process_time = None
        
        # Callbacks
        self.on_detections: Optional[callable] = None
        self.on_occupancy_change: Optional[callable] = None
        
        self._lock = threading.Lock()
    
    def set_homography_matrix(self, matrix: List[List[float]]):
        """Set homography matrix"""
        self.homography.set_matrix(matrix)
        logger.info(f"Homography matrix set for camera {self.camera_id}")
    
    def update_parking_places(self, parking_places: List[Dict]):
        """Update parking places"""
        # Clear existing
        for place_id in list(self.monitor_manager.monitors.keys()):
            self.monitor_manager.remove_place(place_id)
        
        # Add new
        for place in parking_places:
            self.monitor_manager.add_place(
                place_id=place['id'],
                polygon=place['polygon'],
                min_frames_occupied=settings.MIN_FRAMES_OCCUPIED,
                min_frames_free=settings.MIN_FRAMES_FREE
            )
        
        logger.info(f"Updated {len(parking_places)} parking places for camera {self.camera_id}")
    
    def start(self):
        """Start processing pipeline"""
        if self.is_running:
            logger.warning(f"Pipeline for camera {self.camera_id} already running")
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        logger.info(f"Processing pipeline started for camera {self.camera_id}")
    
    def stop(self):
        """Stop processing pipeline"""
        self.is_running = False
        if self.processing_thread is not None:
            self.processing_thread.join(timeout=5)
        logger.info(f"Processing pipeline stopped for camera {self.camera_id}")
    
    def _processing_loop(self):
        """Main processing loop"""
        frame_skip_counter = 0
        
        while self.is_running:
            try:
                start_time = time.time()
                
                # Get frame from camera
                frame_data = self.camera.get_frame(timeout=1.0)
                if frame_data is None:
                    continue
                
                frame, frame_number, timestamp = frame_data
                
                # Frame skipping for performance
                frame_skip_counter += 1
                if frame_skip_counter % (settings.FRAME_SKIP + 1) != 0:
                    continue
                
                # Process frame
                result = self._process_frame(frame, frame_number, timestamp)
                
                # Update FPS
                process_time = time.time() - start_time
                self.fps = 1.0 / process_time if process_time > 0 else 0.0
                self.last_process_time = datetime.now()
                self.frame_count += 1
                
                # Callbacks
                if result['detections'] and self.on_detections:
                    self.on_detections(result)
                
                if result['occupancy_events'] and self.on_occupancy_change:
                    self.on_occupancy_change(result['occupancy_events'])
                
            except Exception as e:
                logger.error(f"Processing loop error for camera {self.camera_id}: {e}", exc_info=True)
                time.sleep(0.1)
    
    def _process_frame(
        self,
        frame: np.ndarray,
        frame_number: int,
        timestamp: float
    ) -> Dict:
        """
        Process single frame through the pipeline
        
        Returns:
            {
                'camera_id': int,
                'frame_number': int,
                'timestamp': datetime,
                'detections': List[Dict],
                'tracks': List[Dict],
                'occupancy_states': Dict,
                'occupancy_events': List[Dict]
            }
        """
        dt = datetime.fromtimestamp(timestamp)
        
        # 1. Detection
        detections = self.detector.detect(frame, return_masks=True)
        
        # 2. Tracking
        tracks = self.tracker.update(detections)
        
        # Merge track_id into detections
        detection_to_track = {}
        for track in tracks:
            # Find matching detection by centroid proximity
            track_centroid = np.array(track['centroid'])
            min_dist = float('inf')
            best_det_idx = -1
            
            for i, det in enumerate(detections):
                det_centroid = np.array(det['centroid'])
                dist = np.linalg.norm(track_centroid - det_centroid)
                if dist < min_dist:
                    min_dist = dist
                    best_det_idx = i
            
            if best_det_idx >= 0 and min_dist < 50:  # 50 pixels threshold
                detection_to_track[best_det_idx] = track['track_id']
        
        # Add track_id to detections
        for i, det in enumerate(detections):
            det['track_id'] = detection_to_track.get(i)
        
        # 3. Homography transformation
        if self.homography.get_matrix() is not None:
            for det in detections:
                # Transform centroid
                centroid_map = self.homography.transform_point(tuple(det['centroid']))
                if centroid_map:
                    det['centroid_map'] = list(centroid_map)
                
                # Transform bbox
                bbox_map = self.homography.transform_bbox(tuple(det['bbox']))
                if bbox_map:
                    det['bbox_map'] = list(bbox_map)
        
        # 4. Occupancy detection
        # Use map coordinates if available, otherwise camera coordinates
        detections_for_occupancy = []
        for det in detections:
            det_copy = det.copy()
            if 'centroid_map' in det:
                det_copy['centroid'] = det['centroid_map']
            detections_for_occupancy.append(det_copy)
        
        occupancy_events = self.monitor_manager.update_all(detections_for_occupancy, dt)
        occupancy_states = self.monitor_manager.get_all_states()
        
        return {
            'camera_id': self.camera_id,
            'frame_number': frame_number,
            'timestamp': dt,
            'detections': detections,
            'tracks': tracks,
            'occupancy_states': occupancy_states,
            'occupancy_events': occupancy_events
        }
    
    def process_single_frame(self, frame: np.ndarray) -> Dict:
        """
        Process a single frame (for testing/debugging)
        
        Args:
            frame: Input frame
            
        Returns:
            Processing result
        """
        return self._process_frame(frame, 0, time.time())
    
    def get_stats(self) -> Dict:
        """Get pipeline statistics"""
        occupancy_summary = self.monitor_manager.get_occupancy_summary()
        
        return {
            'camera_id': self.camera_id,
            'is_running': self.is_running,
            'frame_count': self.frame_count,
            'fps': round(self.fps, 2),
            'last_process_time': self.last_process_time,
            'occupancy': occupancy_summary,
            'homography_calibrated': self.homography.get_matrix() is not None
        }


class PipelineManager:
    """
    Manage multiple processing pipelines
    """
    
    def __init__(self):
        self.pipelines: Dict[int, ProcessingPipeline] = {}
        self._lock = threading.Lock()
    
    def add_pipeline(
        self,
        camera_id: int,
        camera_connector: CameraConnector,
        parking_places: List[Dict],
        homography_matrix: Optional[List[List[float]]] = None,
        auto_start: bool = True
    ) -> bool:
        """Add and optionally start a processing pipeline"""
        with self._lock:
            if camera_id in self.pipelines:
                logger.warning(f"Pipeline for camera {camera_id} already exists")
                return False
            
            pipeline = ProcessingPipeline(
                camera_id=camera_id,
                camera_connector=camera_connector,
                parking_places=parking_places,
                homography_matrix=homography_matrix
            )
            
            self.pipelines[camera_id] = pipeline
            
            if auto_start:
                pipeline.start()
            
            logger.info(f"Pipeline added for camera {camera_id}")
            return True
    
    def remove_pipeline(self, camera_id: int):
        """Remove and stop a pipeline"""
        with self._lock:
            if camera_id in self.pipelines:
                self.pipelines[camera_id].stop()
                del self.pipelines[camera_id]
                logger.info(f"Pipeline removed for camera {camera_id}")
    
    def get_pipeline(self, camera_id: int) -> Optional[ProcessingPipeline]:
        """Get pipeline by camera ID"""
        return self.pipelines.get(camera_id)
    
    def get_all_stats(self) -> Dict[int, Dict]:
        """Get statistics for all pipelines"""
        return {cid: pipeline.get_stats() for cid, pipeline in self.pipelines.items()}
    
    def stop_all(self):
        """Stop all pipelines"""
        with self._lock:
            for pipeline in self.pipelines.values():
                pipeline.stop()
            logger.info("All pipelines stopped")
