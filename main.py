from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime

from routers import solar
from config.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize FastAPI
app = FastAPI(
    title=settings.app_name,
    description="Solar PV output calculation using NREL PVWatts V8 API",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router
app.include_router(solar.router)

@app.get("/")
async def root():
    """API information"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Solar PV system output calculation using PVWatts V8",
        "endpoints": {
            "monthly_output": "/solar/output",
            "hourly_output": "/solar/hourly-output",
            "quick_estimate": "/solar/quick-estimate",
            "supported_locations": "/solar/supported-locations"
        },
        "data_source": "NREL PVWatts V8 API with NSRDB 2020 TMY data",
        "api_documentation": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "api_key_configured": settings.nrel_api_key != "DEMO_KEY"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
