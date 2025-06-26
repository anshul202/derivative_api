import requests
import asyncio
import pandas as pd
import hashlib
import json
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
from models.solar_models import (
    SolarSystemRequest, PVWattsResponse, HourlyPVWattsRequest, HourlyPVWattsResponse
)

logger = logging.getLogger(__name__)

class PVWattsService:
    """Enhanced PVWatts V8 API service with caching and performance optimizations"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://developer.nrel.gov/api/pvwatts/v8.json"
        self.timeout = 30
        
        # Initialize caching system
        self.pvwatts_cache = {}
        self.cache_duration = 3600  # 1 hour for solar data
        self.max_cache_size = 1000  # Limit cache to prevent memory issues
        
        # Performance metrics
        self.api_call_count = 0
        self.cache_hit_count = 0
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get caching performance statistics"""
        total_requests = self.api_call_count + self.cache_hit_count
        hit_rate = (self.cache_hit_count / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "total_requests": total_requests,
            "api_calls": self.api_call_count,
            "cache_hits": self.cache_hit_count,
            "cache_hit_rate_percent": round(hit_rate, 2),
            "cached_entries": len(self.pvwatts_cache),
            "cache_size_limit": self.max_cache_size
        }
    
    def _generate_cache_key(self, request: SolarSystemRequest, timeframe: str = "monthly") -> str:
        """Generate unique cache key for PVWatts request"""
        cache_data = {
            # Core parameters
            'lat': round(request.latitude, 4),  # Round to ~11m precision
            'lon': round(request.longitude, 4),
            'capacity': request.system_capacity,
            'module_type': request.module_type,
            'array_type': request.array_type,
            'tilt': request.tilt,
            'azimuth': request.azimuth,
            'losses': request.losses,
            'dc_ac_ratio': request.dc_ac_ratio,
            'gcr': request.gcr,
            'inv_eff': request.inv_eff,
            'timeframe': timeframe
        }
        
        # Add optional parameters if present
        if request.bifaciality is not None:
            cache_data['bifaciality'] = request.bifaciality
        if request.albedo is not None:
            cache_data['albedo'] = round(request.albedo, 3)
            
        # Generate stable hash
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if PVWatts cache entry is still valid"""
        if cache_key not in self.pvwatts_cache:
            return False
        
        cache_entry = self.pvwatts_cache[cache_key]
        cache_age = (datetime.now() - cache_entry['timestamp']).total_seconds()
        return cache_age < self.cache_duration
    
    def _cleanup_cache(self) -> None:
        """Remove expired entries and enforce cache size limits"""
        now = datetime.now()
        
        # Remove expired entries
        expired_keys = []
        for key, entry in self.pvwatts_cache.items():
            cache_age = (now - entry['timestamp']).total_seconds()
            if cache_age >= self.cache_duration:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.pvwatts_cache[key]
        
        # Enforce size limit (remove oldest entries)
        if len(self.pvwatts_cache) > self.max_cache_size:
            # Sort by timestamp and remove oldest
            sorted_entries = sorted(
                self.pvwatts_cache.items(),
                key=lambda x: x[1]['timestamp']
            )
            
            entries_to_remove = len(self.pvwatts_cache) - self.max_cache_size
            for i in range(entries_to_remove):
                key = sorted_entries[i][0]
                del self.pvwatts_cache[key]
        
        logger.debug(f"Cache cleanup complete. Current size: {len(self.pvwatts_cache)}")
    
    def _apply_bifacial_enhancement(self, 
                                  base_generation: List[float], 
                                  bifaciality: Optional[float], 
                                  albedo: Optional[float]) -> List[float]:
        """Apply bifacial gain calculation if PVWatts doesn't support it"""
        if bifaciality is None or albedo is None:
            return base_generation
        
        # Enhanced bifacial model based on research
        # Albedo impact: higher albedo = more rear-side irradiance
        albedo_factor = max(0, min(1, (albedo - 0.15) / 0.55))  # Normalize 0.15-0.7 to 0-1
        
        # Bifacial gain model: 5-25% depending on conditions
        base_gain = 0.05  # Minimum bifacial gain (5%)
        max_additional_gain = 0.20  # Maximum additional gain from high albedo
        
        bifacial_gain = bifaciality * (base_gain + max_additional_gain * albedo_factor)
        
        logger.info(f"Applied bifacial enhancement: {bifacial_gain:.1%} gain "
                   f"(bifaciality={bifaciality}, albedo={albedo})")
        
        return [gen * (1 + bifacial_gain) for gen in base_generation]

    async def get_monthly_output(self, request: SolarSystemRequest) -> PVWattsResponse:
        """Get monthly solar output with caching and bifacial enhancement"""
        try:
            # Generate cache key and check cache
            cache_key = self._generate_cache_key(request, "monthly")
            
            if self._is_cache_valid(cache_key):
                self.cache_hit_count += 1
                logger.info(f"PVWatts cache HIT for key: {cache_key[:8]}...")
                return self.pvwatts_cache[cache_key]['data']
            
            # Cache miss - make API call
            self.api_call_count += 1
            logger.info(f"PVWatts cache MISS - calling API for key: {cache_key[:8]}...")
            
            # Prepare API parameters
            params = self._build_api_params(request, timeframe="monthly")
            
            # Make API call
            response_data = await self._make_api_request(params)
            
            # Format basic response
            result = self._format_monthly_response(response_data, request)
            
            # Apply bifacial enhancement if needed (in case PVWatts doesn't support it)
            if request.bifaciality is not None and request.albedo is not None:
                enhanced_ac_monthly = self._apply_bifacial_enhancement(
                    result.ac_monthly, request.bifaciality, request.albedo
                )
                enhanced_dc_monthly = self._apply_bifacial_enhancement(
                    result.dc_monthly, request.bifaciality, request.albedo
                )
                
                # Update result with enhanced values
                result.ac_monthly = enhanced_ac_monthly
                result.dc_monthly = enhanced_dc_monthly
                result.ac_annual = sum(enhanced_ac_monthly)
                result.capacity_factor = (result.ac_annual / 
                                        (request.system_capacity * 8760)) * 100
            
            # Cache the result
            self.pvwatts_cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now()
            }
            
            # Periodic cache cleanup
            if len(self.pvwatts_cache) % 50 == 0:  # Every 50 entries
                self._cleanup_cache()
            
            return result
            
        except Exception as e:
            logger.error(f"PVWatts monthly request failed: {str(e)}")
            raise

    async def get_hourly_output(self, request: HourlyPVWattsRequest) -> HourlyPVWattsResponse:
        """Get hourly solar output with caching"""
        try:
            # Generate cache key for hourly data
            cache_key = self._generate_cache_key(request, "hourly")
            
            if self._is_cache_valid(cache_key):
                self.cache_hit_count += 1
                logger.info(f"PVWatts hourly cache HIT for key: {cache_key[:8]}...")
                return self.pvwatts_cache[cache_key]['data']
            
            # Cache miss - make API call
            self.api_call_count += 1
            logger.info(f"PVWatts hourly cache MISS - calling API for key: {cache_key[:8]}...")
            
            # Prepare API parameters for hourly data
            params = self._build_api_params(request, timeframe="hourly")
            params["dataset"] = request.dataset
            
            # Make API call
            response_data = await self._make_api_request(params)
            
            # Format hourly response
            result = self._format_hourly_response(response_data, request)
            
            # Cache the result
            self.pvwatts_cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"PVWatts hourly request failed: {str(e)}")
            raise
    
    def _build_api_params(self, request: SolarSystemRequest, timeframe: str = "monthly") -> Dict[str, Any]:
        """Build optimized PVWatts API parameters"""
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
        
        # Add optional parameters if provided (may not be supported by public PVWatts)
        if request.bifaciality is not None:
            params["bifaciality"] = request.bifaciality
        
        if request.albedo is not None:
            params["albedo"] = request.albedo
            
        return params
    
    async def _make_api_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make async request to PVWatts API with improved error handling"""
        loop = asyncio.get_event_loop()
        
        def make_request():
            try:
                response = requests.get(
                    self.base_url, 
                    params=params, 
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                raise TimeoutError(f"PVWatts API timeout after {self.timeout}s")
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 422:
                    raise ValueError(f"Invalid PVWatts parameters: {e.response.text}")
                elif e.response.status_code == 429:
                    raise ValueError("PVWatts rate limit exceeded (1000/hour)")
                else:
                    raise ValueError(f"PVWatts HTTP error: {e}")
            except requests.exceptions.RequestException as e:
                raise ConnectionError(f"PVWatts connection error: {e}")
        
        response_data = await loop.run_in_executor(None, make_request)
        
        # Enhanced error checking
        if "errors" in response_data and response_data["errors"]:
            error_msg = "; ".join(response_data["errors"])
            raise ValueError(f"PVWatts API errors: {error_msg}")
        
        # Log warnings with more detail
        if "warnings" in response_data and response_data["warnings"]:
            warning_msg = "; ".join(response_data["warnings"])
            logger.warning(f"PVWatts API warnings: {warning_msg}")
        
        return response_data
    
    def _format_monthly_response(self, data: Dict[str, Any], request: SolarSystemRequest) -> PVWattsResponse:
        """Format PVWatts monthly response with validation"""
        try:
            outputs = data["outputs"]
            
            # Validate essential outputs exist
            required_fields = ["ac_monthly", "dc_monthly", "ac_annual", "capacity_factor"]
            for field in required_fields:
                if field not in outputs:
                    raise ValueError(f"Missing required PVWatts output: {field}")
            
            return PVWattsResponse(
                ac_monthly=outputs["ac_monthly"],
                dc_monthly=outputs["dc_monthly"],
                poa_monthly=outputs.get("poa_monthly", [0] * 12),
                solrad_monthly=outputs.get("solrad_monthly", [0] * 12),
                ac_annual=outputs["ac_annual"],
                solrad_annual=outputs.get("solrad_annual", 0),
                capacity_factor=outputs["capacity_factor"],
                station_info=data.get("station_info", {}),
                system_inputs=data.get("inputs", {}),
                timestamp=datetime.now(),
                pvwatts_version=data.get("version", "8.0.0")
            )
        except KeyError as e:
            raise ValueError(f"Invalid PVWatts response structure: missing {e}")
    
    def _format_hourly_response(self, data: Dict[str, Any], request: HourlyPVWattsRequest) -> HourlyPVWattsResponse:
        """Format PVWatts hourly response with efficient processing"""
        try:
            outputs = data["outputs"]
            
            # Validate hourly data
            if "ac" not in outputs or "dc" not in outputs:
                raise ValueError("Missing hourly AC or DC data in PVWatts response")
            
            hourly_ac = outputs["ac"]
            hourly_dc = outputs["dc"]
            
            if len(hourly_ac) != 8760 or len(hourly_dc) != 8760:
                raise ValueError(f"Expected 8760 hourly values, got AC:{len(hourly_ac)} DC:{len(hourly_dc)}")
            
            # Generate timestamps efficiently
            start_date = datetime(2020, 1, 1)  # PVWatts uses TMY data
            timestamps = [
                (start_date + timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M:%S")
                for hour in range(8760)
            ]
            
            # Efficient monthly aggregation using pandas
            df = pd.DataFrame({
                "ac": hourly_ac,
                "dc": hourly_dc,
                "month": pd.date_range(start_date, periods=8760, freq='H').month
            })
            
            monthly_summary = df.groupby('month').agg({
                'ac': 'sum',
                'dc': 'sum'
            })
            
            monthly_ac = monthly_summary['ac'].tolist()
            monthly_dc = monthly_summary['dc'].tolist()
            
            # Create monthly summary object
            monthly_summary_obj = PVWattsResponse(
                ac_monthly=monthly_ac,
                dc_monthly=monthly_dc,
                poa_monthly=outputs.get("poa_monthly", [0] * 12),
                solrad_monthly=outputs.get("solrad_monthly", [0] * 12),
                ac_annual=sum(monthly_ac),
                solrad_annual=outputs.get("solrad_annual", 0),
                capacity_factor=outputs.get("capacity_factor", 0),
                station_info=data.get("station_info", {}),
                system_inputs=data.get("inputs", {}),
                timestamp=datetime.now(),
                pvwatts_version=data.get("version", "8.0.0")
            )
            
            return HourlyPVWattsResponse(
                hourly_ac=hourly_ac,
                hourly_dc=hourly_dc,
                timestamps=timestamps,
                monthly_summary=monthly_summary_obj
            )
            
        except Exception as e:
            logger.error(f"Error formatting hourly response: {str(e)}")
            raise ValueError(f"Failed to process hourly PVWatts data: {str(e)}")
