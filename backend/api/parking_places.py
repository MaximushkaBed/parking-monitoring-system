from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class ParkingPlaceCreate(BaseModel):
    polygon_map: List[List[float]]  # [[x1,y1], [x2,y2], ...]
    type: str = "regular"
    zone_id: Optional[int] = None
    row: Optional[str] = None


class ParkingPlaceUpdate(BaseModel):
    polygon_map: Optional[List[List[float]]] = None
    type: Optional[str] = None
    zone_id: Optional[int] = None
    row: Optional[str] = None


@router.get("/")
async def list_parking_places():
    """Get list of all parking places"""
    # In production, fetch from DB
    return {"parking_places": []}


@router.post("/")
async def create_parking_place(place: ParkingPlaceCreate):
    """Create a new parking place"""
    # In production, save to DB
    return {"id": 1, **place.dict()}


@router.get("/{place_id}")
async def get_parking_place(place_id: int):
    """Get parking place details"""
    # In production, fetch from DB
    return {"id": place_id}


@router.put("/{place_id}")
async def update_parking_place(place_id: int, place: ParkingPlaceUpdate):
    """Update parking place"""
    # In production, update DB
    return {"id": place_id, "message": "Updated"}


@router.delete("/{place_id}")
async def delete_parking_place(place_id: int):
    """Delete parking place"""
    # In production, delete from DB
    return {"message": "Deleted", "id": place_id}


@router.get("/{place_id}/occupancy")
async def get_place_occupancy(place_id: int, request: Request):
    """Get current occupancy status of a parking place"""
    pipeline_manager = request.app.state.pipeline_manager
    
    # Get status from all pipelines
    all_stats = pipeline_manager.get_all_stats()
    
    for camera_id, stats in all_stats.items():
        occupancy_states = stats.get('occupancy', {})
        # Find place in occupancy states
        # In production, this would be more sophisticated
    
    return {"place_id": place_id, "status": "free"}


@router.post("/bulk-create")
async def bulk_create_parking_places(places: List[ParkingPlaceCreate]):
    """Create multiple parking places at once"""
    # In production, bulk insert to DB
    return {"created": len(places)}
