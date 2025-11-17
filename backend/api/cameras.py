import base64
import cv2
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import logging

from backend.services.camera_connector import CameraType

logger = logging.getLogger(__name__)

router = APIRouter()


class CameraCreate(BaseModel):
    name: str
    rtsp_url: str
    connection_type: str = "rtsp"
    floor: int = 0


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    connection_type: Optional[str] = None
    floor: Optional[int] = None
    status: Optional[str] = None


@router.get("/")
async def list_cameras(request: Request):
    """Get list of all cameras"""
    camera_manager = request.app.state.camera_manager
    stats = camera_manager.get_all_stats()
    
    return {
        "cameras": [
            {
                "id": cam_id,
                **stats[cam_id]
            }
            for cam_id in stats
        ]
    }


@router.post("/")
async def create_camera(camera: CameraCreate, request: Request):
    """Add a new camera"""
    camera_manager = request.app.state.camera_manager
    
    # Generate camera ID (in production, this would come from DB)
    camera_id = len(camera_manager.cameras) + 1
    
    # Map connection type
    conn_type_map = {
        "rtsp": CameraType.RTSP,
        "http": CameraType.HTTP,
        "motion_activated": CameraType.MOTION_ACTIVATED,
        "file": CameraType.FILE
    }
    conn_type = conn_type_map.get(camera.connection_type, CameraType.RTSP)
    
    # Add camera
    success = camera_manager.add_camera(
        camera_id=camera_id,
        source=camera.rtsp_url,
        camera_type=conn_type,
        auto_start=True
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add camera")
    
    return {
        "id": camera_id,
        "name": camera.name,
        "status": "active"
    }


@router.get("/{camera_id}")
async def get_camera(camera_id: int, request: Request):
    """Get camera details"""
    camera_manager = request.app.state.camera_manager
    camera = camera_manager.get_camera(camera_id)
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    stats = camera.get_stats()
    return stats


@router.put("/{camera_id}")
async def update_camera(camera_id: int, camera: CameraUpdate, request: Request):
    """Update camera settings"""
    camera_manager = request.app.state.camera_manager
    cam = camera_manager.get_camera(camera_id)
    
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # In production, update DB and reconnect if needed
    return {"message": "Camera updated", "id": camera_id}


@router.delete("/{camera_id}")
async def delete_camera(camera_id: int, request: Request):
    """Delete camera"""
    camera_manager = request.app.state.camera_manager
    pipeline_manager = request.app.state.pipeline_manager
    
    # Stop and remove pipeline
    pipeline_manager.remove_pipeline(camera_id)
    
    # Remove camera
    camera_manager.remove_camera(camera_id)
    
    return {"message": "Camera deleted", "id": camera_id}


@router.post("/{camera_id}/start")
async def start_camera(camera_id: int, request: Request):
    """Start camera capture"""
    camera_manager = request.app.state.camera_manager
    camera = camera_manager.get_camera(camera_id)
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    camera.start()
    return {"message": "Camera started", "id": camera_id}


@router.post("/{camera_id}/stop")
async def stop_camera(camera_id: int, request: Request):
    """Stop camera capture"""
    camera_manager = request.app.state.camera_manager
    camera = camera_manager.get_camera(camera_id)
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    camera.stop()
    return {"message": "Camera stopped", "id": camera_id}


@router.get("/{camera_id}/stats")
async def get_camera_stats(camera_id: int, request: Request):
    """Get camera statistics"""
    camera_manager = request.app.state.camera_manager
    camera = camera_manager.get_camera(camera_id)
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    return camera.get_stats()

@router.get("/{camera_id}/frame")
async def get_camera_frame(camera_id: int, request: Request):
    """Get the latest frame from a camera"""
    camera_manager = request.app.state.camera_manager
    camera = camera_manager.get_camera(camera_id)
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # 1. Используем правильный метод get_frame()
    frame_data = camera.get_frame(timeout=1.0)
    
    if frame_data is None:
        raise HTTPException(status_code=404, detail="Frame not available from camera queue")
    
    # 2. Извлекаем кадр (первый элемент кортежа)
    frame = frame_data[0]
    
    # 3. Кодируем кадр в JPEG
    success, buffer = cv2.imencode('.jpg', frame)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode frame to JPEG")
    
    # 4. Кодируем в Base64 и преобразуем в строку для JSON
    frame_base64 = base64.b64encode(buffer).decode('utf-8')
    
    # 5. Возвращаем JSON, как ожидает фронтенд
    return JSONResponse(content={"frame": frame_base64})