import numpy as np
from typing import List, Dict, Optional, Tuple
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class KalmanFilter:
    """
    Simple Kalman filter for 2D tracking (x, y, vx, vy)
    """
    
    def __init__(self):
        # State: [x, y, vx, vy]
        self.x = np.zeros(4)
        
        # State covariance
        self.P = np.eye(4) * 1000
        
        # Process noise
        self.Q = np.eye(4)
        self.Q[0:2, 0:2] *= 0.01
        self.Q[2:4, 2:4] *= 0.01
        
        # Measurement noise
        self.R = np.eye(2) * 10
        
        # State transition matrix
        self.F = np.eye(4)
        self.F[0, 2] = 1
        self.F[1, 3] = 1
        
        # Measurement matrix
        self.H = np.zeros((2, 4))
        self.H[0, 0] = 1
        self.H[1, 1] = 1
    
    def predict(self):
        """Predict next state"""
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x[:2]
    
    def update(self, measurement: np.ndarray):
        """Update with measurement"""
        y = measurement - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P
        return self.x[:2]


class Track:
    """
    Single track object
    """
    
    _id_counter = 0
    
    def __init__(self, detection: Dict, track_id: Optional[int] = None):
        if track_id is None:
            self.track_id = Track._id_counter
            Track._id_counter += 1
        else:
            self.track_id = track_id
        
        self.kalman = KalmanFilter()
        centroid = np.array(detection['centroid'])
        self.kalman.x[:2] = centroid
        
        self.bbox = detection['bbox']
        self.centroid = centroid
        self.confidence = detection['confidence']
        self.class_id = detection['class_id']
        self.class_name = detection['class_name']
        
        self.age = 0
        self.hits = 1
        self.time_since_update = 0
        
        self.history = deque(maxlen=30)
        self.history.append(centroid)
    
    def predict(self):
        """Predict next position"""
        predicted = self.kalman.predict()
        self.age += 1
        self.time_since_update += 1
        return predicted
    
    def update(self, detection: Dict):
        """Update track with new detection"""
        centroid = np.array(detection['centroid'])
        self.kalman.update(centroid)
        
        self.bbox = detection['bbox']
        self.centroid = centroid
        self.confidence = detection['confidence']
        self.class_id = detection['class_id']
        self.class_name = detection['class_name']
        
        self.hits += 1
        self.time_since_update = 0
        self.history.append(centroid)
    
    def get_state(self) -> Dict:
        """Get current track state"""
        return {
            'track_id': self.track_id,
            'bbox': self.bbox,
            'centroid': self.centroid.tolist(),
            'confidence': self.confidence,
            'class_id': self.class_id,
            'class_name': self.class_name,
            'age': self.age,
            'hits': self.hits
        }


class ByteTracker:
    """
    ByteTrack-style multi-object tracker
    """
    
    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3
    ):
        """
        Initialize tracker
        
        Args:
            max_age: Maximum frames to keep track without detection
            min_hits: Minimum detections to confirm track
            iou_threshold: IoU threshold for matching
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        
        self.tracks: List[Track] = []
        self.frame_count = 0
    
    def update(self, detections: List[Dict]) -> List[Dict]:
        """
        Update tracks with new detections
        
        Args:
            detections: List of detections from detector
            
        Returns:
            List of active tracks with track_id
        """
        self.frame_count += 1
        
        # Predict all tracks
        for track in self.tracks:
            track.predict()
        
        if len(detections) == 0:
            # Remove old tracks
            self.tracks = [t for t in self.tracks if t.time_since_update < self.max_age]
            return self._get_active_tracks()
        
        # Match detections to tracks
        matched, unmatched_dets, unmatched_tracks = self._match(detections)
        
        # Update matched tracks
        for det_idx, track_idx in matched:
            self.tracks[track_idx].update(detections[det_idx])
        
        # Create new tracks for unmatched detections
        for det_idx in unmatched_dets:
            self.tracks.append(Track(detections[det_idx]))
        
        # Remove old tracks
        self.tracks = [t for t in self.tracks if t.time_since_update < self.max_age]
        
        return self._get_active_tracks()
    
    def _match(
        self,
        detections: List[Dict]
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Match detections to tracks using IoU
        
        Returns:
            matched: List of (detection_idx, track_idx) pairs
            unmatched_detections: List of detection indices
            unmatched_tracks: List of track indices
        """
        if len(self.tracks) == 0:
            return [], list(range(len(detections))), []
        
        # Compute IoU matrix
        iou_matrix = np.zeros((len(detections), len(self.tracks)))
        
        for d, det in enumerate(detections):
            for t, track in enumerate(self.tracks):
                iou_matrix[d, t] = self._iou(det['bbox'], track.bbox)
        
        # Greedy matching
        matched = []
        unmatched_dets = list(range(len(detections)))
        unmatched_tracks = list(range(len(self.tracks)))
        
        while len(unmatched_dets) > 0 and len(unmatched_tracks) > 0:
            # Find best match
            max_iou = 0
            best_det = -1
            best_track = -1
            
            for d in unmatched_dets:
                for t in unmatched_tracks:
                    if iou_matrix[d, t] > max_iou:
                        max_iou = iou_matrix[d, t]
                        best_det = d
                        best_track = t
            
            if max_iou < self.iou_threshold:
                break
            
            matched.append((best_det, best_track))
            unmatched_dets.remove(best_det)
            unmatched_tracks.remove(best_track)
        
        return matched, unmatched_dets, unmatched_tracks
    
    def _iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate IoU between two bboxes"""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        # Intersection
        x_min = max(x1_min, x2_min)
        y_min = max(y1_min, y2_min)
        x_max = min(x1_max, x2_max)
        y_max = min(y1_max, y2_max)
        
        if x_max < x_min or y_max < y_min:
            return 0.0
        
        intersection = (x_max - x_min) * (y_max - y_min)
        
        # Union
        area1 = (x1_max - x1_min) * (y1_max - y1_min)
        area2 = (x2_max - x2_min) * (y2_max - y2_min)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _get_active_tracks(self) -> List[Dict]:
        """Get tracks that meet min_hits requirement"""
        active = []
        for track in self.tracks:
            if track.hits >= self.min_hits or self.frame_count <= self.min_hits:
                active.append(track.get_state())
        return active
    
    def reset(self):
        """Reset tracker"""
        self.tracks = []
        self.frame_count = 0
        Track._id_counter = 0
