from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config.settings import settings
from backend.api import cameras, parking_places, zones, analytics, calibration

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global managers (will be initialized in lifespan)
camera_manager = None
pipeline_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global camera_manager, pipeline_manager
    
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize managers
    from backend.services.camera_connector import CameraManager
    from backend.services.processing_pipeline import PipelineManager
    
    camera_manager = CameraManager()
    pipeline_manager = PipelineManager()
    
    # Store in app state
    app.state.camera_manager = camera_manager
    app.state.pipeline_manager = pipeline_manager
    
    logger.info("Application started successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")
    if camera_manager:
        camera_manager.stop_all()
    if pipeline_manager:
        pipeline_manager.stop_all()
    logger.info("Application stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Intelligent parking monitoring system with ML-based vehicle detection",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(cameras.router, prefix="/api/cameras", tags=["Cameras"])
app.include_router(parking_places.router, prefix="/api/parking-places", tags=["Parking Places"])
app.include_router(zones.router, prefix="/api/zones", tags=["Zones"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(calibration.router, prefix="/api/calibration", tags=["Calibration"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "camera_manager": app.state.camera_manager is not None,
        "pipeline_manager": app.state.pipeline_manager is not None
    }


@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    camera_stats = app.state.camera_manager.get_all_stats() if app.state.camera_manager else {}
    pipeline_stats = app.state.pipeline_manager.get_all_stats() if app.state.pipeline_manager else {}
    
    return {
        "cameras": camera_stats,
        "pipelines": pipeline_stats
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
