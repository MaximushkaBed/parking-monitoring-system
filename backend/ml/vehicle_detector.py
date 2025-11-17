import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class VehicleDetector:
    """
    Vehicle detection and segmentation using YOLOv11-Seg
    """
    
    def __init__(
        self,
        model_path: str = "yolov8n-seg.pt",
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        device: str = "cuda",
        vehicle_classes: List[int] = [2, 3, 5, 7]  # car, motorcycle, bus, truck
    ):
        """
        Initialize YOLO detector
        
        Args:
            model_path: Path to YOLO model weights
            confidence_threshold: Minimum confidence for detection
            iou_threshold: IoU threshold for NMS
            device: 'cuda' or 'cpu'
            vehicle_classes: COCO class IDs for vehicles
        """
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.vehicle_classes = vehicle_classes
        self.device = device
        
        try:
            self.model = YOLO(model_path)
            self.model.to(device)
            logger.info(f"Loaded YOLO model from {model_path} on {device}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
        
        # COCO class names
        self.class_names = {
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck"
        }
    
    def detect(
        self,
        frame: np.ndarray,
        return_masks: bool = True
    ) -> List[Dict]:
        """
        Detect vehicles in frame
        
        Args:
            frame: Input image (BGR format)
            return_masks: Whether to return segmentation masks
            
        Returns:
            List of detections with format:
            {
                'bbox': [x1, y1, x2, y2],
                'centroid': [cx, cy],
                'confidence': float,
                'class_id': int,
                'class_name': str,
                'mask': [[x1,y1], [x2,y2], ...] or None  # polygon points
            }
        """
        try:
            # Run inference
            results = self.model.predict(
                frame,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                classes=self.vehicle_classes,
                verbose=False
            )
            
            detections = []
            
            if len(results) == 0:
                return detections
            
            result = results[0]
            
            # Extract boxes
            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
                confidences = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy().astype(int)
                
                # Extract masks if available
                masks = None
                if return_masks and result.masks is not None:
                    masks = result.masks.xy  # List of polygon points for each mask
                
                for i in range(len(boxes)):
                    bbox = boxes[i].tolist()
                    class_id = int(class_ids[i])
                    
                    # Calculate centroid
                    cx = (bbox[0] + bbox[2]) / 2
                    cy = (bbox[1] + bbox[3]) / 2
                    
                    detection = {
                        'bbox': bbox,
                        'centroid': [cx, cy],
                        'confidence': float(confidences[i]),
                        'class_id': class_id,
                        'class_name': self.class_names.get(class_id, f"class_{class_id}"),
                        'mask': None
                    }
                    
                    # Add mask if available
                    if masks is not None and i < len(masks):
                        mask_points = masks[i].tolist()
                        detection['mask'] = mask_points
                    
                    detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []
    
    def detect_batch(
        self,
        frames: List[np.ndarray],
        return_masks: bool = True
    ) -> List[List[Dict]]:
        """
        Batch detection for multiple frames
        
        Args:
            frames: List of input images
            return_masks: Whether to return segmentation masks
            
        Returns:
            List of detection lists for each frame
        """
        try:
            results = self.model.predict(
                frames,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                classes=self.vehicle_classes,
                verbose=False
            )
            
            all_detections = []
            
            for result in results:
                detections = []
                
                if result.boxes is not None:
                    boxes = result.boxes.xyxy.cpu().numpy()
                    confidences = result.boxes.conf.cpu().numpy()
                    class_ids = result.boxes.cls.cpu().numpy().astype(int)
                    
                    masks = None
                    if return_masks and result.masks is not None:
                        masks = result.masks.xy
                    
                    for i in range(len(boxes)):
                        bbox = boxes[i].tolist()
                        class_id = int(class_ids[i])
                        cx = (bbox[0] + bbox[2]) / 2
                        cy = (bbox[1] + bbox[3]) / 2
                        
                        detection = {
                            'bbox': bbox,
                            'centroid': [cx, cy],
                            'confidence': float(confidences[i]),
                            'class_id': class_id,
                            'class_name': self.class_names.get(class_id, f"class_{class_id}"),
                            'mask': None
                        }
                        
                        if masks is not None and i < len(masks):
                            detection['mask'] = masks[i].tolist()
                        
                        detections.append(detection)
                
                all_detections.append(detections)
            
            return all_detections
            
        except Exception as e:
            logger.error(f"Batch detection error: {e}")
            return [[] for _ in frames]
    
    def visualize(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        show_masks: bool = True,
        show_labels: bool = True
    ) -> np.ndarray:
        """
        Visualize detections on frame
        
        Args:
            frame: Input image
            detections: List of detections from detect()
            show_masks: Whether to draw segmentation masks
            show_labels: Whether to draw labels
            
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        
        for det in detections:
            bbox = det['bbox']
            x1, y1, x2, y2 = map(int, bbox)
            
            # Draw bounding box
            color = (0, 255, 0)  # Green
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw mask
            if show_masks and det['mask'] is not None:
                mask_points = np.array(det['mask'], dtype=np.int32)
                overlay = annotated.copy()
                cv2.fillPoly(overlay, [mask_points], color)
                annotated = cv2.addWeighted(annotated, 0.7, overlay, 0.3, 0)
                cv2.polylines(annotated, [mask_points], True, color, 2)
            
            # Draw label
            if show_labels:
                label = f"{det['class_name']} {det['confidence']:.2f}"
                (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated, (x1, y1 - label_h - 10), (x1 + label_w, y1), color, -1)
                cv2.putText(annotated, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            
            # Draw centroid
            cx, cy = map(int, det['centroid'])
            cv2.circle(annotated, (cx, cy), 5, (0, 0, 255), -1)
        
        return annotated
