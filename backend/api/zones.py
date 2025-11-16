from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ZoneCreate(BaseModel):
    name: str
    description: Optional[str] = None
    floor: int = 0


class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    floor: Optional[int] = None


@router.get("/")
async def list_zones():
    """Get list of all zones"""
    return {"zones": []}


@router.post("/")
async def create_zone(zone: ZoneCreate):
    """Create a new zone"""
    return {"id": 1, **zone.dict()}


@router.get("/{zone_id}")
async def get_zone(zone_id: int):
    """Get zone details"""
    return {"id": zone_id}


@router.put("/{zone_id}")
async def update_zone(zone_id: int, zone: ZoneUpdate):
    """Update zone"""
    return {"id": zone_id, "message": "Updated"}


@router.delete("/{zone_id}")
async def delete_zone(zone_id: int):
    """Delete zone"""
    return {"message": "Deleted", "id": zone_id}
