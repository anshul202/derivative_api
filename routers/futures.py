from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime
import numpy as np
from typing import List

from models.pricing_models import (
    ElectricityFuturesRequest, 
    ElectricityFuturesResponse, 
    ElectricityFuturesContract
)
from services.futures_service import futures_service
from services.solar_service import PVWattsService
from config.settings import get_settings
from models.solar_models import SolarSystemRequest

router = APIRouter(prefix="/futures", tags=["Electricity Futures"])

@router.post("/electricity", response_model=ElectricityFuturesResponse)
async def create_electricity_futures(
    request: ElectricityFuturesRequest,
    background_tasks: BackgroundTasks
) -> ElectricityFuturesResponse:
    """
    Create electricity futures contracts based on solar generation and price simulation
    
    This endpoint integrates:
    1. Solar generation forecasting (PVWatts)
    2. Electricity price simulation (mean-reversion model)
    3. Futures contract pricing (Monte Carlo)
    4. Risk analytics (VaR, ES, Greeks)
    """
    try:
        # 1. Get solar generation forecast using existing solar service
        settings = get_settings()
        solar_service = PVWattsService(settings.nrel_api_key)
        
        # Create solar request from futures request
        solar_request = SolarSystemRequest(
            latitude=request.latitude,
            longitude=request.longitude,
            system_capacity=request.system_capacity_kw,
            module_type=request.module_type,
            array_type=request.array_type,
            tilt=request.tilt,
            azimuth=request.azimuth,
            losses=request.losses
        )
        
        solar_output = await solar_service.get_monthly_output(solar_request)
        monthly_generation_mwh = [kwh / 1000 for kwh in solar_output.ac_monthly]
        
        # 2. Simulate electricity price paths
        price_paths = futures_service.simulate_mean_reverting_prices(
            s0=request.current_spot_price,
            kappa=request.mean_reversion_speed,
            theta=request.long_term_price_mean,
            sigma=request.price_volatility,
            T=request.contract_months / 12,
            n_steps=request.contract_months,
            n_paths=request.monte_carlo_paths
        )
        
        # 3. Calculate futures fair values
        time_to_delivery = [(i + 1) / 12 for i in range(request.contract_months)]
        futures_prices, price_volatilities = futures_service.calculate_futures_fair_value(
            price_paths, 
            monthly_generation_mwh,
            request.risk_free_rate,
            time_to_delivery
        )
        
        # 4. Generate revenue simulations for risk analysis
        revenue_simulations = []
        for path in price_paths:
            monthly_revenues = []
            for month in range(min(12, request.contract_months)):
                generation = monthly_generation_mwh[month] if month < len(monthly_generation_mwh) else 0
                price = futures_prices[month] if month < len(futures_prices) else path[month + 1] if month + 1 < len(path) else path[-1]
                revenue = generation * price
                monthly_revenues.append(revenue)
            revenue_simulations.append(monthly_revenues)
        
        # 5. Create futures contracts
        futures_contracts = []
        month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                      "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        
        # Get current year dynamically
        current_year = datetime.now().year
        year_suffix = str(current_year)[-2:]  # Get last 2 digits (e.g., "25" for 2025)
        
        for month in range(min(12, request.contract_months)):
            if month < len(futures_prices) and month < len(monthly_generation_mwh):
                greeks = futures_service.calculate_greeks(
                    futures_prices[month],
                    request.current_spot_price,
                    price_volatilities[month] if month < len(price_volatilities) else 0.25,
                    time_to_delivery[month] if month < len(time_to_delivery) else (month + 1) / 12
                )
                
                contract = ElectricityFuturesContract(
                    contract_symbol=f"SOLAR-{month_names[month]}{year_suffix}",  # Dynamic year
                    delivery_month=f"{current_year}-{month+1:02d}",  # Dynamic year
                    underlying_generation_mwh=monthly_generation_mwh[month],
                    futures_price=futures_prices[month],
                    expected_revenue=monthly_generation_mwh[month] * futures_prices[month],
                    price_volatility=price_volatilities[month] if month < len(price_volatilities) else 0.25,
                    delta=greeks["delta"],
                    contract_size=monthly_generation_mwh[month]
                )
                futures_contracts.append(contract)
        
        # 6. Calculate portfolio risk metrics
        risk_metrics = futures_service.calculate_portfolio_risk_metrics(revenue_simulations)
        
        # 7. Calculate correlation between solar and prices
        if len(monthly_generation_mwh) >= 12 and len(futures_prices) >= 12:
            solar_seasonal = np.array(monthly_generation_mwh[:12])
            price_seasonal = np.array(futures_prices[:12])
            correlation = np.corrcoef(solar_seasonal, price_seasonal)[0, 1] if len(solar_seasonal) > 1 and len(price_seasonal) > 1 else 0.0
        else:
            correlation = 0.0
        
        return ElectricityFuturesResponse(
            monthly_solar_output_mwh=monthly_generation_mwh,
            annual_generation_mwh=sum(monthly_generation_mwh),
            capacity_factor=solar_output.capacity_factor,
            futures_contracts=futures_contracts,
            total_portfolio_value=sum(c.expected_revenue for c in futures_contracts),
            portfolio_volatility=risk_metrics["revenue_volatility"],
            sharpe_ratio=risk_metrics["sharpe_ratio"],
            value_at_risk_95=risk_metrics["value_at_risk_95"],
            expected_shortfall_95=risk_metrics["expected_shortfall_95"],
            correlation_solar_price=float(correlation),
            seasonal_premium=risk_metrics["seasonal_premium"],
            pricing_timestamp=datetime.now(),
            model_parameters={
                "kappa": request.mean_reversion_speed,
                "theta": request.long_term_price_mean,
                "sigma": request.price_volatility,
                "monte_carlo_paths": request.monte_carlo_paths
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Futures pricing failed: {str(e)}")

@router.get("/market-data")
async def get_futures_market_data():
    """Get current electricity futures market data and benchmarks"""
    current_year = datetime.now().year
    
    return {
        "market_overview": {
            "description": "Solar-backed electricity futures market",
            "trading_unit": "MWh",
            "price_currency": "USD",
            "settlement": "Physical delivery",
            "current_year": current_year  # Show current year in market data
        },
        "typical_parameters": {
            "spot_price_range": "$30-150/MWh",
            "volatility_range": "20-40% annually",
            "mean_reversion_speed": "1.0-3.0",
            "seasonal_premium": "Summer +15%, Winter -10%"
        },
        "contract_specifications": {
            "delivery_months": [f"{current_year}-{month+1:02d}" for month in range(12)],  # Dynamic months
            "contract_symbols": [f"SOLAR-{name}{str(current_year)[-2:]}" for name in 
                               ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                                "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]],
            "minimum_contract_size": "1 MWh",
            "tick_size": "$0.01/MWh",
            "daily_price_limit": "±$50/MWh"
        }
    }

@router.get("/health")
async def futures_health_check():
    """Health check for futures service"""
    current_year = datetime.now().year
    return {
        "status": "healthy",
        "service": "electricity_futures",
        "current_year": current_year,
        "contract_year": current_year,
        "timestamp": datetime.now()
    }
