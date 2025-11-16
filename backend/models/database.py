from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class CameraStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    CALIBRATING = "calibrating"


class ConnectionType(str, enum.Enum):
    RTSP = "rtsp"
    HTTP = "http"
    MOTION_ACTIVATED = "motion_activated"
    OTHER = "other"


class PlaceType(str, enum.Enum):
    REGULAR = "regular"
    DISABLED = "disabled"
    FAMILY = "family"
    VIP = "vip"
    ELECTRIC = "electric"
    SHORT_TERM = "short_term"


class OccupancyStatus(str, enum.Enum):
    FREE = "free"
    OCCUPIED = "occupied"
    UNKNOWN = "unknown"


class Camera(Base):
    __tablename__ = "cameras"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    rtsp_url = Column(Text, nullable=True)
    connection_type = Column(SQLEnum(ConnectionType), default=ConnectionType.RTSP)
    status = Column(SQLEnum(CameraStatus), default=CameraStatus.INACTIVE)
    floor = Column(Integer, default=0)
    homography_matrix = Column(JSON, nullable=True)  # 3x3 matrix as list of lists
    calibration_points = Column(JSON, nullable=True)  # {camera: [[x,y],...], map: [[x,y],...]}
    last_frame_time = Column(DateTime, nullable=True)
    fps = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    detections = relationship("Detection", back_populates="camera", cascade="all, delete-orphan")


class ParkingZone(Base):
    __tablename__ = "parking_zones"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    floor = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    places = relationship("ParkingPlace", back_populates="zone", cascade="all, delete-orphan")


class ParkingPlace(Base):
    __tablename__ = "parking_places"
    
    id = Column(Integer, primary_key=True, index=True)
    polygon_map = Column(JSON, nullable=False)  # [[x1,y1], [x2,y2], ...] on map coordinates
    type = Column(SQLEnum(PlaceType), default=PlaceType.REGULAR)
    zone_id = Column(Integer, ForeignKey("parking_zones.id"), nullable=True)
    row = Column(String(50), nullable=True)
    current_status = Column(SQLEnum(OccupancyStatus), default=OccupancyStatus.FREE)
    last_status_change = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    zone = relationship("ParkingZone", back_populates="places")
    occupancy_events = relationship("OccupancyEvent", back_populates="place", cascade="all, delete-orphan")


class Detection(Base):
    __tablename__ = "detections"
    
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    frame_number = Column(Integer, nullable=False)
    
    # Detection data
    bbox = Column(JSON, nullable=False)  # [x1, y1, x2, y2] in camera coordinates
    bbox_map = Column(JSON, nullable=True)  # [x1, y1, x2, y2] in map coordinates (after homography)
    centroid = Column(JSON, nullable=False)  # [x, y] in camera coordinates
    centroid_map = Column(JSON, nullable=True)  # [x, y] in map coordinates
    confidence = Column(Float, nullable=False)
    class_id = Column(Integer, nullable=False)  # COCO class ID
    class_name = Column(String(50), nullable=False)
    
    # Tracking
    track_id = Column(Integer, nullable=True)
    
    # Segmentation
    mask = Column(JSON, nullable=True)  # Polygon points or RLE encoded mask
    
    # Relationships
    camera = relationship("Camera", back_populates="detections")


class OccupancyEvent(Base):
    __tablename__ = "occupancy_events"
    
    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(Integer, ForeignKey("parking_places.id"), nullable=False)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Vehicle info
    track_id = Column(Integer, nullable=True)
    vehicle_class = Column(String(50), nullable=True)
    
    # Relationships
    place = relationship("ParkingPlace", back_populates="occupancy_events")


class ParkingSchema(Base):
    __tablename__ = "parking_schemas"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    floor = Column(Integer, default=0)
    image_url = Column(Text, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AnalyticsCache(Base):
    __tablename__ = "analytics_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
