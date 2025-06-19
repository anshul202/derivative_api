import requests
import asyncio
import pandas as pd
from typing import Dict, Any, List
import logging
from datetime import datetime, timedelta
from models.solar_models import (
    SolarSystemRequest, PVWattsResponse, HourlyPVWattsRequest, HourlyPVWattsResponse
)

logger = logging.getLogger(__name__)

class PVWattsService:
    """Service for PVWatts V8 API integration only"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://developer.nrel.gov/api/pvwatts/v8.json"
        self.timeout = 30
    
    async def get_monthly_output(self, request: SolarSystemRequest) -> PVWattsResponse:
        """Get monthly solar output from PVWatts V8 API"""[3]
        try:
            # Prepare API parameters
            params = self._build_api_params(request, timeframe="monthly")
            
            # Make async API call
            response_data = await self._make_api_request(params)
            
            # Format response
            return self._format_monthly_response(response_data, request)
            
        except Exception as e:
            logger.error(f"PVWatts monthly request failed: {str(e)}")
            raise
    
    async def get_hourly_output(self, request: HourlyPVWattsRequest) -> HourlyPVWattsResponse:
        """Get hourly solar output from PVWatts V8 API"""[3]
        try:
            # Prepare API parameters for hourly data
            params = self._build_api_params(request, timeframe="hourly")
            params["dataset"] = request.dataset
            
            # Make async API call
            response_data = await self._make_api_request(params)
            
            # Format hourly response
            return self._format_hourly_response(response_data, request)
            
        except Exception as e:
            logger.error(f"PVWatts hourly request failed: {str(e)}")
            raise
    
    def _build_api_params(self, request: SolarSystemRequest, timeframe: str = "monthly") -> Dict[str, Any]:
        """Build PVWatts API parameters from request"""[3]
        params = {
            "api_key": self.api_key,
            "lat": request.latitude,
            "lon": request.longitude,
            "system_capacity": request.system_capacity,
            "module_type": request.module_type,
            "losses": request.losses,
            "array_type": request.array_type,
            "tilt": request.tilt,
            "azimuth": request.azimuth,
            "dc_ac_ratio": request.dc_ac_ratio,
            "gcr": request.gcr,
            "inv_eff": request.inv_eff,
            "timeframe": timeframe,
            "dataset": "nsrdb",  # Use latest NSRDB data
            "radius": 100  # Search radius for weather station
        }
        
        # Add optional parameters if provided
        if request.bifaciality is not None:
            params["bifaciality"] = request.bifaciality
        
        if request.albedo is not None:
            params["albedo"] = request.albedo
            
        return params
    
    async def _make_api_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make async request to PVWatts API"""
        loop = asyncio.get_event_loop()
        
        def make_request():
            response = requests.get(
                self.base_url, 
                params=params, 
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        
        response_data = await loop.run_in_executor(None, make_request)
        
        # Check for API errors
        if "errors" in response_data and response_data["errors"]:
            raise ValueError(f"PVWatts API errors: {response_data['errors']}")
        
        # Log warnings if any
        if "warnings" in response_data and response_data["warnings"]:
            logger.warning(f"PVWatts API warnings: {response_data['warnings']}")
        
        return response_data
    
    def _format_monthly_response(self, data: Dict[str, Any], request: SolarSystemRequest) -> PVWattsResponse:
        """Format PVWatts monthly response"""[3]
        outputs = data["outputs"]
        
        return PVWattsResponse(
            ac_monthly=outputs["ac_monthly"],
            dc_monthly=outputs["dc_monthly"],
            poa_monthly=outputs["poa_monthly"],
            solrad_monthly=outputs["solrad_monthly"],
            ac_annual=outputs["ac_annual"],
            solrad_annual=outputs["solrad_annual"],
            capacity_factor=outputs["capacity_factor"],
            station_info=data["station_info"],
            system_inputs=data["inputs"],
            timestamp=datetime.now(),
            pvwatts_version=data.get("version", "8.0.0")
        )
    
    def _format_hourly_response(self, data: Dict[str, Any], request: HourlyPVWattsRequest) -> HourlyPVWattsResponse:
        """Format PVWatts hourly response"""
        outputs = data["outputs"]
        
        # Generate timestamps for the year (8760 hours)
        start_date = datetime(2020, 1, 1)  # PVWatts uses TMY data
        timestamps = []
        for hour in range(8760):
            timestamp = start_date + timedelta(hours=hour)
            timestamps.append(timestamp.strftime("%Y-%m-%dT%H:%M:%S"))
        
        # Create monthly summary from hourly data
        hourly_ac = outputs["ac"]
        hourly_dc = outputs["dc"]
        
        # Aggregate to monthly
        df = pd.DataFrame({
            "ac": hourly_ac,
            "dc": hourly_dc,
            "timestamp": pd.to_datetime(timestamps)
        })
        
        monthly_groups = df.groupby(df["timestamp"].dt.month)
        monthly_ac = monthly_groups["ac"].sum().tolist()
        monthly_dc = monthly_groups["dc"].sum().tolist()
        
        # Calculate other monthly values
        poa_monthly = outputs.get("poa_monthly", [0] * 12)
        solrad_monthly = outputs.get("solrad_monthly", [0] * 12)
        
        monthly_summary = PVWattsResponse(
            ac_monthly=monthly_ac,
            dc_monthly=monthly_dc,
            poa_monthly=poa_monthly,
            solrad_monthly=solrad_monthly,
            ac_annual=sum(monthly_ac),
            solrad_annual=outputs.get("solrad_annual", 0),
            capacity_factor=outputs.get("capacity_factor", 0),
            station_info=data["station_info"],
            system_inputs=data["inputs"],
            timestamp=datetime.now(),
            pvwatts_version=data.get("version", "8.0.0")
        )
        
        return HourlyPVWattsResponse(
            hourly_ac=hourly_ac,
            hourly_dc=hourly_dc,
            timestamps=timestamps,
            monthly_summary=monthly_summary
        )
