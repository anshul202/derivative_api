from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
from enum import Enum

# Get current year dynamically
current_year = datetime.now().year

class DeliveryMonth(str, Enum):
    """Standard futures delivery months with dynamic current year"""
    JAN = f"{current_year}-01"
    FEB = f"{current_year}-02"
    MAR = f"{current_year}-03"
    APR = f"{current_year}-04"
    MAY = f"{current_year}-05"
    JUN = f"{current_year}-06"
    JUL = f"{current_year}-07"
    AUG = f"{current_year}-08"
    SEP = f"{current_year}-09"
    OCT = f"{current_year}-10"
    NOV = f"{current_year}-11"
    DEC = f"{current_year}-12"

class ElectricityFuturesRequest(BaseModel):
    """Request model for creating electricity futures contracts based on solar output"""
    
    # Solar system parameters (simplified from your existing solar models)
    latitude: float = Field(..., ge=-90, le=90, description="Solar farm latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Solar farm longitude")
    system_capacity_kw: float = Field(..., gt=0, description="Solar system capacity in kW")
    module_type: int = Field(1, ge=0, le=2, description="0=Standard, 1=Premium, 2=Thin film")
    array_type: int = Field(1, ge=0, le=4, description="Array mounting type")
    tilt: float = Field(20, ge=0, le=90, description="Panel tilt angle")
    azimuth: float = Field(180, ge=0, lt=360, description="Panel azimuth (180=south)")
    losses: float = Field(14, ge=-5, le=99, description="System losses %")
    
    # Electricity market parameters
    current_spot_price: float = Field(..., gt=0, description="Current electricity spot price $/MWh")
    price_volatility: float = Field(0.25, gt=0, le=2, description="Annual price volatility")
    mean_reversion_speed: float = Field(1.5, gt=0, description="Price mean reversion speed (kappa)")
    long_term_price_mean: float = Field(..., gt=0, description="Long-term electricity price $/MWh")
    
    # Futures contract specifications
    contract_months: int = Field(12, ge=1, le=24, description="Number of monthly contracts")
    risk_free_rate: float = Field(0.04, ge=0, le=0.2, description="Risk-free rate")
    monte_carlo_paths: int = Field(10000, ge=1000, le=100000, description="MC simulation paths")

class ElectricityFuturesContract(BaseModel):
    """Individual futures contract specification"""
    contract_symbol: str = Field(..., description="Futures contract symbol (e.g., SOLAR-JAN25)")
    delivery_month: str = Field(..., description="Contract delivery month")
    underlying_generation_mwh: float = Field(..., description="Expected solar generation MWh")
    futures_price: float = Field(..., description="Fair value futures price $/MWh")
    expected_revenue: float = Field(..., description="Expected contract revenue $")
    price_volatility: float = Field(..., description="Contract price volatility")
    delta: float = Field(..., description="Price sensitivity to spot price changes")
    contract_size: float = Field(..., description="Contract size in MWh")

class ElectricityFuturesResponse(BaseModel):
    """Complete futures pricing response"""
    
    # Solar generation profile
    monthly_solar_output_mwh: List[float] = Field(..., description="Monthly solar output in MWh")
    annual_generation_mwh: float = Field(..., description="Total annual generation")
    capacity_factor: float = Field(..., description="Solar capacity factor %")
    
    # Futures contracts
    futures_contracts: List[ElectricityFuturesContract] = Field(..., description="Monthly futures contracts")
    
    # Portfolio risk metrics
    total_portfolio_value: float = Field(..., description="Total portfolio value $")
    portfolio_volatility: float = Field(..., description="Portfolio volatility $")
    sharpe_ratio: float = Field(..., description="Risk-adjusted return ratio")
    value_at_risk_95: float = Field(..., description="95% Value at Risk $")
    expected_shortfall_95: float = Field(..., description="95% Expected Shortfall $")
    
    # Market data
    correlation_solar_price: float = Field(..., description="Solar generation vs price correlation")
    seasonal_premium: List[float] = Field(..., description="Monthly seasonal price premiums")
    
    # Metadata
    pricing_timestamp: datetime = Field(..., description="When pricing was calculated")
    model_parameters: dict = Field(..., description="Model calibration parameters")
