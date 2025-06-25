from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional  # Add Optional here
from datetime import datetime


class SolarSystemRequest(BaseModel):
    """Request model for PVWatts solar system configuration"""
    latitude: float = Field(..., ge=-89.8, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    system_capacity: float = Field(1.0, gt=0.05, le=500000, description="System capacity in kW")
    
    # PVWatts required parameters
    module_type: int = Field(1, ge=0, le=2, description="Module type: 0=Standard, 1=Premium, 2=Thin film")
    array_type: int = Field(1, ge=0, le=4, description="Array type: 0=Fixed open rack, 1=Fixed roof mount, 2=1-axis, 3=1-axis backtracked, 4=2-axis")
    tilt: float = Field(20, ge=0, le=90, description="Tilt angle in degrees")
    azimuth: float = Field(180, ge=0, lt=360, description="Azimuth angle in degrees")
    losses: float = Field(14, ge=-5, le=99, description="System losses in percent")
    
    # Optional PVWatts parameters
    dc_ac_ratio: float = Field(1.2, gt=0, description="DC to AC ratio")
    gcr: float = Field(0.4, ge=0.01, le=0.99, description="Ground coverage ratio")
    inv_eff: float = Field(96, ge=90, le=99.5, description="Inverter efficiency at rated power")
    
    # Advanced options (PVWatts V8 features)
    bifaciality: Optional[float] = Field(None, ge=0, le=1, description="Bifacial ratio (0.65-0.9)")
    albedo: Optional[float] = Field(None, gt=0, lt=1, description="Ground reflectance")
    
    @validator('azimuth')
    def validate_azimuth(cls, v):
        return v % 360

class PVWattsResponse(BaseModel):
    """Direct response from PVWatts V8 API"""
    # Monthly generation data
    ac_monthly: List[float] = Field(..., description="Monthly AC generation in kWh")
    dc_monthly: List[float] = Field(..., description="Monthly DC generation in kWh")
    poa_monthly: List[float] = Field(..., description="Monthly plane-of-array irradiance")
    solrad_monthly: List[float] = Field(..., description="Monthly solar radiation")
    
    # Annual totals
    ac_annual: float = Field(..., description="Annual AC generation in kWh")
    solrad_annual: float = Field(..., description="Annual solar radiation")
    capacity_factor: float = Field(..., description="Capacity factor as percentage")
    
    # System and location info
    station_info: Dict[str, Any] = Field(..., description="Weather station information")
    system_inputs: Dict[str, Any] = Field(..., description="System parameters used")
    
    # Metadata
    timestamp: datetime = Field(..., description="Response timestamp")
    pvwatts_version: str = Field(..., description="PVWatts version used")

class HourlyPVWattsRequest(SolarSystemRequest):
    """Request for hourly PVWatts data"""
    timeframe: str = Field("hourly", pattern="^(monthly|hourly)$", description="Data resolution")
    dataset: str = Field("nsrdb", pattern="^(nsrdb|tmy2|tmy3|intl)$", description="Climate dataset")

class HourlyPVWattsResponse(BaseModel):
    """Hourly PVWatts response"""
    hourly_ac: List[float] = Field(..., description="Hourly AC generation in kWh")
    hourly_dc: List[float] = Field(..., description="Hourly DC generation in kWh")
    timestamps: List[str] = Field(..., description="Hourly timestamps")
    monthly_summary: PVWattsResponse = Field(..., description="Monthly aggregated data")
