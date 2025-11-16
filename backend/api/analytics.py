from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/current")
async def get_current_occupancy(request: Request):
    """Get current parking occupancy"""
    pipeline_manager = request.app.state.pipeline_manager
    
    all_stats = pipeline_manager.get_all_stats()
    
    total_occupied = 0
    total_free = 0
    total_places = 0
    
    for camera_id, stats in all_stats.items():
        occupancy = stats.get('occupancy', {})
        total_occupied += occupancy.get('occupied', 0)
        total_free += occupancy.get('free', 0)
        total_places += occupancy.get('total', 0)
    
    return {
        "total": total_places,
        "occupied": total_occupied,
        "free": total_free,
        "occupancy_rate": (total_occupied / total_places * 100) if total_places > 0 else 0.0,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/history")
async def get_occupancy_history(
    period: str = "day",  # day, week, month
    zone_id: Optional[int] = None
):
    """Get historical occupancy data"""
    # In production, fetch from analytics_cache table
    return {
        "period": period,
        "data": []
    }


@router.get("/anomalies")
async def get_anomalies(
    threshold_hours: int = 24
):
    """Get list of anomalies (long-stay vehicles)"""
    # In production, query occupancy_events table
    return {
        "anomalies": [],
        "threshold_hours": threshold_hours
    }


@router.get("/average-duration")
async def get_average_duration(
    zone_id: Optional[int] = None,
    days: int = 7
):
    """Get average parking duration"""
    # In production, calculate from occupancy_events
    return {
        "average_duration_minutes": 45,
        "zone_id": zone_id,
        "period_days": days
    }


@router.get("/turnover")
async def get_turnover(
    zone_id: Optional[int] = None,
    days: int = 7
):
    """Get parking turnover rate"""
    # In production, calculate from occupancy_events
    return {
        "turnover_rate": 8.5,  # vehicles per day per place
        "zone_id": zone_id,
        "period_days": days
    }


@router.get("/popular-zones")
async def get_popular_zones(days: int = 7):
    """Get most popular zones"""
    # In production, aggregate from occupancy_events
    return {
        "zones": [],
        "period_days": days
    }
