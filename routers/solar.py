from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any
import logging

from models.solar_models import (
    SolarSystemRequest, PVWattsResponse, HourlyPVWattsRequest, HourlyPVWattsResponse
)
from services.solar_service import PVWattsService
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/solar", tags=["Solar Output - PVWatts"])

def get_pvwatts_service():
    """Get PVWatts service with API key"""
    settings = get_settings()
    return PVWattsService(settings.nrel_api_key)

@router.post("/output", response_model=PVWattsResponse)
async def get_solar_output(
    request: SolarSystemRequest,
    service: PVWattsService = Depends(get_pvwatts_service)
) -> PVWattsResponse:
    """
    Calculate solar PV system output using NREL PVWatts V8 API
    
    Returns monthly AC/DC generation, capacity factor, and detailed
    performance metrics using the latest NSRDB weather data.
    """
    try:
        logger.info(f"PVWatts request: {request.latitude}, {request.longitude}, {request.system_capacity}kW")
        
        result = await service.get_monthly_output(request)
        
        logger.info(f"PVWatts result: {result.ac_annual:.1f} kWh/year, CF: {result.capacity_factor:.1f}%")
        return result
        
    except Exception as e:
        logger.error(f"PVWatts calculation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PVWatts API error: {str(e)}")

@router.post("/hourly-output", response_model=HourlyPVWattsResponse)
async def get_hourly_solar_output(
    request: HourlyPVWattsRequest,
    service: PVWattsService = Depends(get_pvwatts_service)
) -> HourlyPVWattsResponse:
    """
    Get detailed hourly solar output from PVWatts V8 API
    
    Provides 8760 hourly generation values for detailed analysis.
    """[3]
    try:
        logger.info(f"PVWatts hourly request: {request.latitude}, {request.longitude}")
        
        result = await service.get_hourly_output(request)
        
        logger.info(f"PVWatts hourly result: {len(result.hourly_ac)} data points")
        return result
        
    except Exception as e:
        logger.error(f"PVWatts hourly calculation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PVWatts hourly API error: {str(e)}")

@router.get("/quick-estimate")
async def quick_solar_estimate(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
    capacity: float = Query(1.0, gt=0, le=100, description="System capacity in kW"),
    service: PVWattsService = Depends(get_pvwatts_service)
) -> Dict[str, Any]:
    """
    Quick solar estimate using default PVWatts parameters
    
    Simplified endpoint for rapid estimates with standard system configuration.
    """
    try:
        # Create request with default parameters
        request = SolarSystemRequest(
            latitude=latitude,
            longitude=longitude,
            system_capacity=capacity,
            module_type=1,  # Premium modules
            array_type=1,   # Fixed roof mount
            tilt=20,        # Moderate tilt
            azimuth=180,    # South-facing
            losses=14       # Standard losses
        )
        
        result = await service.get_monthly_output(request)
        
        # Return simplified response
        return {
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "weather_station": result.station_info
            },
            "system": {
                "capacity_kw": capacity,
                "configuration": "Premium modules, roof-mounted, south-facing"
            },
            "annual_performance": {
                "ac_generation_kwh": result.ac_annual,
                "capacity_factor_percent": result.capacity_factor,
                "specific_yield_kwh_per_kw": result.ac_annual / capacity
            },
            "monthly_generation_kwh": result.ac_monthly,
            "data_source": f"PVWatts {result.pvwatts_version}",
            "timestamp": result.timestamp.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quick estimate failed: {str(e)}")

@router.get("/supported-locations")
async def get_supported_locations():
    """
    Information about PVWatts data coverage and supported locations
    """
    return {
        "data_coverage": {
            "primary": "United States (NSRDB 2020 TMY data)",
            "international": "Limited international coverage via TMY2/TMY3",
            "weather_data_year": "2020 Typical Meteorological Year"
        },
        "datasets": {
            "nsrdb": "NREL National Solar Radiation Database (recommended)",
            "tmy2": "TMY2 data for some international locations", 
            "tmy3": "TMY3 data for some international locations",
            "intl": "International data where available"
        },
        "data_resolution": {
            "spatial": "Approximately 4km grid resolution",
            "temporal": "Hourly data available"
        },
        "api_limits": {
            "max_system_size_kw": 500000,
            "min_system_size_kw": 0.05,
            "search_radius_miles": 100
        }
    }
