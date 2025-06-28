from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime
import numpy as np
from typing import List
import logging

from models.pricing_models import (
    ElectricityFuturesRequest, 
    ElectricityFuturesResponse, 
    ElectricityFuturesContract
)
from services.futures_service import futures_service
from services.solar_service import PVWattsService
from services.iex_price_service import iex_service  # Add IEX service import
from config.settings import get_settings
from models.solar_models import SolarSystemRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/futures", tags=["Electricity Futures"])

from fastapi.responses import StreamingResponse
import io
import csv

# Add this new endpoint to your existing futures router
@router.post("/electricity-csv")
async def export_futures_csv(request: ElectricityFuturesRequest):
    """Export futures results as CSV file for financial analysis"""
    try:
        # Get the futures data using existing function
        background_tasks = BackgroundTasks()
        result = await create_electricity_futures(request, background_tasks)
        
        # Create CSV content in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            "Contract Symbol", "Delivery Month", "Generation (MWh)", 
            "Futures Price ($/MWh)", "Expected Revenue ($)", "Price Volatility", "Delta"
        ])
        
        # Write contract data
        for contract in result.futures_contracts:
            writer.writerow([
                contract.contract_symbol,
                contract.delivery_month,
                round(contract.underlying_generation_mwh, 2),
                round(contract.futures_price, 2),
                round(contract.expected_revenue, 2),
                round(contract.price_volatility, 4),
                round(contract.delta, 4)
            ])
        
        # Add portfolio summary section
        writer.writerow([])  # Empty row
        writer.writerow(["PORTFOLIO SUMMARY"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Portfolio Value ($)", f"{result.total_portfolio_value:,.2f}"])
        writer.writerow(["Annual Generation (MWh)", f"{result.annual_generation_mwh:.2f}"])
        writer.writerow(["Capacity Factor (%)", f"{result.capacity_factor:.2f}"])
        writer.writerow(["Portfolio Volatility ($)", f"{result.portfolio_volatility:,.2f}"])
        writer.writerow(["Sharpe Ratio", f"{result.sharpe_ratio:.4f}"])
        writer.writerow(["95% Value at Risk ($)", f"{result.value_at_risk_95:,.2f}"])
        writer.writerow(["95% Expected Shortfall ($)", f"{result.expected_shortfall_95:,.2f}"])
        
        # Add model parameters section
        writer.writerow([])
        writer.writerow(["MODEL PARAMETERS"])
        writer.writerow(["Parameter", "Value"])
        for key, value in result.model_parameters.items():
            writer.writerow([key.replace('_', ' ').title(), str(value)])
        
        # Convert to bytes for download
        output.seek(0)
        csv_content = output.getvalue()
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=solar_futures_analysis.csv"
            }
        )
        
    except Exception as e:
        logger.error(f"CSV export failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"CSV export failed: {str(e)}")
    


@router.post("/electricity", response_model=ElectricityFuturesResponse)
async def create_electricity_futures(
    request: ElectricityFuturesRequest,
    background_tasks: BackgroundTasks
) -> ElectricityFuturesResponse:
    """
    Create electricity futures contracts with live IEX spot prices if current_spot_price is not provided
    
    This endpoint integrates:
    1. Live IEX price fetching (if current_spot_price is None)
    2. Solar generation forecasting (PVWatts) with bifacial enhancement
    3. Electricity price simulation (mean-reversion model)
    4. Futures contract pricing (Monte Carlo)
    5. Risk analytics (VaR, ES, Greeks)

    """
    try:
        # 1. Get live IEX spot price if not provided
        if request.current_spot_price is None:
            iex_data = await iex_service.get_current_spot_price()
            current_price = iex_data['spot_price_usd_mwh']  # Use USD for international compatibility
            logger.info(f"Fetched live IEX price: ${current_price:.2f}/MWh (₹{iex_data['spot_price_rs_mwh']:.2f}/MWh)")
        else:
            current_price = request.current_spot_price
        
        # 2. Auto-estimate long-term mean if not provided
        if request.long_term_price_mean is None:
            long_term_mean = current_price * 0.95  # Slight discount for long-term
        else:
            long_term_mean = request.long_term_price_mean
        
        # 3. Get solar generation forecast using existing solar service
        settings = get_settings()
        solar_service = PVWattsService(settings.nrel_api_key)
        
        # ✅ FIXED: Create solar request with ALL parameters including bifaciality and albedo
        solar_request = SolarSystemRequest(
            latitude=request.latitude,
            longitude=request.longitude,
            system_capacity=request.system_capacity_kw,
            module_type=request.module_type,
            array_type=request.array_type,
            tilt=request.tilt,
            azimuth=request.azimuth,
            losses=request.losses,
            
            # ✅ ADD BIFACIAL PARAMETERS THAT WERE MISSING
            bifaciality=getattr(request, 'bifaciality', None),
            albedo=getattr(request, 'albedo', None),
            dc_ac_ratio=getattr(request, 'dc_ac_ratio', 1.2),
            gcr=getattr(request, 'gcr', 0.4),
            inv_eff=getattr(request, 'inv_eff', 96.0)
        )
        
        # ✅ ADD DEBUG LOGGING
        logger.info(f"🔍 Futures request bifaciality: {getattr(request, 'bifaciality', None)}")
        logger.info(f"🔍 Futures request albedo: {getattr(request, 'albedo', None)}")
        logger.info(f"🔍 Solar request created with bifaciality={solar_request.bifaciality}, albedo={solar_request.albedo}")
        
        solar_output = await solar_service.get_monthly_output(solar_request)
        monthly_generation_mwh = [kwh / 1000 for kwh in solar_output.ac_monthly]
        
        # ✅ ADD GENERATION DEBUG LOGGING
        logger.info(f"📊 Monthly generation MWh: {[round(x, 2) for x in monthly_generation_mwh]}")
        logger.info(f"📊 Annual generation: {sum(monthly_generation_mwh):.2f} MWh")
        logger.info(f"📊 Capacity factor: {solar_output.capacity_factor:.2f}%")
        
        # 4. Simulate electricity price paths using current_price (from IEX or user input)
        price_paths = futures_service.simulate_mean_reverting_prices(
            s0=current_price,  # Use fetched or provided price
            kappa=request.mean_reversion_speed,
            theta=long_term_mean,  # Use calculated or provided long-term mean
            sigma=request.price_volatility,
            T=request.contract_months / 12,
            n_steps=request.contract_months,
            n_paths=request.monte_carlo_paths
        )
        
        # 5. Calculate futures fair values
        time_to_delivery = [(i + 1) / 12 for i in range(request.contract_months)]
        futures_prices, price_volatilities = futures_service.calculate_futures_fair_value(
            price_paths, 
            monthly_generation_mwh,
            request.risk_free_rate,
            time_to_delivery
        )
        
        # ✅ ADD FUTURES PRICING DEBUG LOGGING
        logger.info(f"💰 Average futures price: ${np.mean(futures_prices):.2f}/MWh")
        logger.info(f"💰 Futures price range: ${min(futures_prices):.2f} - ${max(futures_prices):.2f}/MWh")
        
        # 6. Generate revenue simulations for risk analysis
        revenue_simulations = []
        for path in price_paths:
            monthly_revenues = []
            for month in range(min(12, request.contract_months)):
                generation = monthly_generation_mwh[month] if month < len(monthly_generation_mwh) else 0
                price = futures_prices[month] if month < len(futures_prices) else path[month + 1] if month + 1 < len(path) else path[-1]
                revenue = generation * price
                monthly_revenues.append(revenue)
            revenue_simulations.append(monthly_revenues)
        
        # 7. Create futures contracts
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
                    current_price,  # Use current_price instead of request.current_spot_price
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
        
        # 8. Calculate portfolio risk metrics
        risk_metrics = futures_service.calculate_portfolio_risk_metrics(revenue_simulations)
        
        # 9. Calculate correlation between solar and prices
        if len(monthly_generation_mwh) >= 12 and len(futures_prices) >= 12:
            solar_seasonal = np.array(monthly_generation_mwh[:12])
            price_seasonal = np.array(futures_prices[:12])
            correlation = np.corrcoef(solar_seasonal, price_seasonal)[0, 1] if len(solar_seasonal) > 1 and len(price_seasonal) > 1 else 0.0
        else:
            correlation = 0.0
        
        # ✅ ADD FINAL PORTFOLIO DEBUG LOGGING
        total_portfolio_value = sum(c.expected_revenue for c in futures_contracts)
        logger.info(f"🎯 Total portfolio value: ${total_portfolio_value:,.2f}")
        
        return ElectricityFuturesResponse(
            monthly_solar_output_mwh=monthly_generation_mwh,
            annual_generation_mwh=sum(monthly_generation_mwh),
            capacity_factor=solar_output.capacity_factor,
            futures_contracts=futures_contracts,
            total_portfolio_value=total_portfolio_value,
            portfolio_volatility=risk_metrics["revenue_volatility"],
            sharpe_ratio=risk_metrics["sharpe_ratio"],
            value_at_risk_95=risk_metrics["value_at_risk_95"],
            expected_shortfall_95=risk_metrics["expected_shortfall_95"],
            correlation_solar_price=float(correlation),
            seasonal_premium=risk_metrics["seasonal_premium"],
            pricing_timestamp=datetime.now(),
            model_parameters={
                "kappa": request.mean_reversion_speed,
                "theta": long_term_mean,  # Use calculated long_term_mean
                "sigma": request.price_volatility,
                "monte_carlo_paths": request.monte_carlo_paths,
                "current_spot_price_source": "IEX_live" if request.current_spot_price is None else "user_provided",
                "bifaciality": getattr(request, 'bifaciality', None),
                "albedo": getattr(request, 'albedo', None)
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Futures pricing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Futures pricing failed: {str(e)}")

# Add new endpoint to check current IEX prices
@router.get("/current-price")
async def get_current_electricity_price():
    """Get current IEX electricity spot price"""
    try:
        price_data = await iex_service.get_current_spot_price()
        return {
            "current_prices": price_data,
            "note": "Prices updated every 15 minutes from IEX India",
            "usage": "Use spot_price_usd_mwh for futures pricing"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Price fetch failed: {str(e)}")

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
            "current_year": current_year,
            "price_source": "IEX India (auto-fetched if not provided)"
        },
        "typical_parameters": {
            "spot_price_range": "$30-150/MWh",
            "volatility_range": "20-40% annually",
            "mean_reversion_speed": "1.0-3.0",
            "seasonal_premium": "Summer +15%, Winter -10%"
        },
        "contract_specifications": {
            "delivery_months": [f"{current_year}-{month+1:02d}" for month in range(12)],
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
        "price_integration": "IEX India live prices",
        "timestamp": datetime.now()
    }
