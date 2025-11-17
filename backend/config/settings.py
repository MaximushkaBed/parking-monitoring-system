from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Parking Monitoring System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/parking_db"
    
    # ML Models
    YOLO_MODEL_PATH: str = "yolov8n-seg.pt"  # or yolov11s-seg.pt, yolov11m-seg.pt
    YOLO_CONFIDENCE_THRESHOLD: float = 0.5
    YOLO_IOU_THRESHOLD: float = 0.45
    YOLO_DEVICE: str = "cuda"  # or "cpu"
    
    # Detection classes (COCO dataset)
    VEHICLE_CLASSES: list[int] = [2, 3, 5, 7]  # car, motorcycle, bus, truck
    
    # Tracking
    TRACKER_TYPE: str = "bytetrack"  # or "botsort"
    MAX_AGE: int = 30  # frames to keep track without detection
    MIN_HITS: int = 3  # minimum detections to confirm track
    IOU_THRESHOLD: float = 0.3
    
    # Temporal Smoothing
    MIN_FRAMES_OCCUPIED: int = 5  # frames to confirm occupation
    MIN_FRAMES_FREE: int = 5  # frames to confirm free
    DEBOUNCE_WINDOW_SEC: int = 3  # seconds
    
    # Camera Processing
    FRAME_SKIP: int = 2  # process every N-th frame
    MAX_CAMERAS: int = 10
    RTSP_TIMEOUT_SEC: int = 10
    RECONNECT_DELAY_SEC: int = 5
    
    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30
    
    # Analytics
    LONG_STAY_THRESHOLD_HOURS: int = 24
    HEATMAP_RESOLUTION: int = 50  # pixels
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
