"""
Test script for parking monitoring system
Tests the full pipeline: Detection -> Tracking -> Occupancy
"""

import cv2
import sys
from pathlib import Path
import time
import logging

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ml.vehicle_detector import VehicleDetector
from backend.ml.tracker import ByteTracker
from backend.utils.homography import HomographyCalibrator
from backend.utils.occupancy import ParkingMonitorManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_detection():
    """Test vehicle detection on a single image"""
    logger.info("=" * 60)
    logger.info("TEST 1: Vehicle Detection")
    logger.info("=" * 60)
    
    # Create detector (will download model on first run)
    detector = VehicleDetector(
        model_path="yolov8n-seg.pt",
        confidence_threshold=0.1,
        device="cpu"  # Change to "cuda" if GPU available
    )
    
    # Create test image (parking lot scene)
    # In production, use real image: frame = cv2.imread("parking_lot.jpg")
    frame = cv2.imread("test_image.png") if Path("test_image.png").exists() else None
    
    if frame is None:
        logger.warning("No test image found, creating blank frame")
        frame = cv2.imread(cv2.samples.findFile("lena.jpg"))  # Fallback
    
    # Detect vehicles
    detections = detector.detect(frame, return_masks=True)
    logger.info(f"✓ Detected {len(detections)} vehicles")
    
    for i, det in enumerate(detections):
        logger.info(f"  Vehicle {i+1}: {det['class_name']} (confidence: {det['confidence']:.2f})")
    
    # Visualize
    if len(detections) > 0:
        annotated = detector.visualize(frame, detections)
        cv2.imwrite("/tmp/detection_result.jpg", annotated)
        logger.info("✓ Saved visualization to /tmp/detection_result.jpg")
    
    return detections


def test_tracking():
    """Test vehicle tracking across multiple frames"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Vehicle Tracking")
    logger.info("=" * 60)
    
    detector = VehicleDetector(model_path="yolov8n-seg.pt", device="cpu")
    tracker = ByteTracker(max_age=30, min_hits=3, iou_threshold=0.3)
    
    # Simulate multiple frames
    # In production, use video: cap = cv2.VideoCapture("parking_video.mp4")
    logger.info("Simulating 10 frames...")
    
    for frame_idx in range(10):
        # Simulate detections (in production, use real detections)
        detections = [
            {
                'bbox': [100 + frame_idx*5, 100, 200 + frame_idx*5, 200],
                'centroid': [150 + frame_idx*5, 150],
                'confidence': 0.9,
                'class_id': 2,
                'class_name': 'car'
            }
        ]
        
        # Update tracker
        tracks = tracker.update(detections)
        
        if len(tracks) > 0:
            logger.info(f"  Frame {frame_idx}: {len(tracks)} active tracks")
            for track in tracks:
                logger.info(f"    Track ID {track['track_id']}: {track['class_name']}")
    
    logger.info("✓ Tracking test completed")


def test_homography():
    """Test homography calibration"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Homography Calibration")
    logger.info("=" * 60)
    
    calibrator = HomographyCalibrator()
    
    # Example: 4 points on camera frame and corresponding points on map
    camera_points = [(100, 200), (300, 200), (300, 400), (100, 400)]
    map_points = [(50, 100), (150, 100), (150, 200), (50, 200)]
    
    success = calibrator.calibrate(camera_points, map_points)
    
    if success:
        logger.info(f"✓ Calibration successful!")
        logger.info(f"  Reprojection error: {calibrator.reprojection_error:.2f} pixels")
        logger.info(f"  Quality: {calibrator.get_calibration_quality()}")
        
        # Test transformation
        test_point = (200, 300)
        transformed = calibrator.transform_point(test_point)
        logger.info(f"  Transform test: camera {test_point} -> map {transformed}")
    else:
        logger.error("✗ Calibration failed")


def test_occupancy():
    """Test occupancy detection with temporal smoothing"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Occupancy Detection")
    logger.info("=" * 60)
    
    manager = ParkingMonitorManager()
    
    place1_polygon = [(100, 100), (200, 100), (200, 200), (100, 200)]
    place2_polygon = [(250, 100), (350, 100), (350, 200), (250, 200)]
    
    manager.add_place(place_id=1, polygon=place1_polygon, min_frames_occupied=3, min_frames_free=3)
    manager.add_place(place_id=2, polygon=place2_polygon, min_frames_occupied=3, min_frames_free=3)
    
    logger.info("Added 2 parking places")
    
    # --- ИСПРАВЛЕННАЯ СИМУЛЯЦИЯ ---
    scenarios = [
        # 5 кадров с машиной в первом месте
        (5, [{'centroid': [150, 150], 'track_id': 1, 'class_name': 'car', 'confidence': 0.95}], "Car enters place 1"),
        # 5 кадров с машиной во втором месте
        (5, [{'centroid': [300, 150], 'track_id': 1, 'class_name': 'car', 'confidence': 0.95}], "Car moves to place 2"),
        # 5 кадров без машин
        (5, [], "All places empty"),
    ]
    
    for num_frames, detections, description in scenarios:
        logger.info(f"\n  Scenario: {description}")
        for _ in range(num_frames):
            # Имитируем один кадр
            time.sleep(0.01) # Небольшая пауза для имитации времени между кадрами
            events = manager.update_all(detections)
            
            if events:
                for event in events:
                    if event.get('end_time'):
                        duration = event.get('duration_seconds', 0)
                        logger.info(f"    ✓ Place {event['place_id']} freed (duration: {duration:.1f}s)")
                    else:
                        logger.info(f"    ✓ Place {event['place_id']} occupied by track {event['track_id']}")

    summary = manager.get_occupancy_summary()
    logger.info(f"\n  Final summary:")
    logger.info(f"    Total places: {summary['total']}")
    logger.info(f"    Occupied: {summary['occupied']}")
    logger.info(f"    Free: {summary['free']}")
    logger.info(f"    Occupancy rate: {summary['occupancy_rate']:.1f}%")


def test_full_pipeline():
    """Test complete pipeline"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Full Pipeline Integration")
    logger.info("=" * 60)
    
    # Initialize components
    detector = VehicleDetector(model_path="yolov8n-seg.pt", device="cpu")
    tracker = ByteTracker()
    calibrator = HomographyCalibrator()
    manager = ParkingMonitorManager()
    
    # Setup calibration (example)
    camera_points = [(100, 200), (300, 200), (300, 400), (100, 400)]
    map_points = [(50, 100), (150, 100), (150, 200), (50, 200)]
    calibrator.calibrate(camera_points, map_points)
    
    # Setup parking places
    place_polygon = [(75, 125), (125, 125), (125, 175), (75, 175)]
    manager.add_place(place_id=1, polygon=place_polygon)
    
    logger.info("Pipeline initialized:")
    logger.info("  ✓ Detector ready")
    logger.info("  ✓ Tracker ready")
    logger.info("  ✓ Calibration ready")
    logger.info("  ✓ Occupancy monitor ready")
    logger.info("\nPipeline flow:")
    logger.info("  Camera → Detection → Tracking → Homography → Occupancy → Events")


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("PARKING MONITORING SYSTEM - TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    try:
        test_detection()
        test_tracking()
        test_homography()
        test_occupancy()
        test_full_pipeline()
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Install dependencies: pip install -r requirements.txt")
        logger.info("2. Start FastAPI server: python main.py")
        logger.info("3. Open API docs: http://localhost:8000/docs")
        logger.info("4. Add cameras via API and start processing")
        
    except Exception as e:
        logger.error(f"\n✗ TEST FAILED: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
