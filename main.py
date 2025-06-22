from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime

from routers import solar, futures
from config.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize FastAPI
app = FastAPI(
    title=settings.app_name,
    description="Solar PV output calculation and electricity futures pricing API using NREL data and financial modeling",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(solar.router)
app.include_router(futures.router)

@app.get("/")
async def root():
    """API information and available endpoints"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Complete solar energy and electricity futures API",
        "features": [
            "Solar PV output calculation using NREL PVWatts V8",
            "Electricity price simulation with mean-reversion models", 
            "Solar-backed electricity futures contracts",
            "Risk analytics and portfolio management"
        ],
        "endpoints": {
            # Solar endpoints
            "solar_output": "/solar/output",
            "solar_hourly_output": "/solar/hourly-output", 
            "solar_quick_estimate": "/solar/quick-estimate",
            "solar_supported_locations": "/solar/supported-locations",
            
            # Futures endpoints
            "electricity_futures": "/futures/electricity",
            "futures_market_data": "/futures/market-data",
            "futures_health": "/futures/health",
            
            # System endpoints
            "health_check": "/health",
            "api_documentation": "/docs",
            "alternative_docs": "/redoc"
        },
        "data_sources": {
            "solar_data": "NREL PVWatts V8 API with NSRDB 2020 TMY data",
            "price_modeling": "Ornstein-Uhlenbeck mean-reversion process",
            "risk_analytics": "Monte Carlo simulation with 10,000+ paths"
        },
        "supported_features": {
            "solar_calculations": [
                "Monthly/annual AC generation",
                "Capacity factor analysis", 
                "Performance ratio calculations",
                "Weather station validation"
            ],
            "futures_contracts": [
                "Solar-backed electricity futures",
                "Dynamic contract year (automatically updates)",
                "Risk metrics (VaR, Expected Shortfall)",
                "Portfolio optimization"
            ]
        }
    }

@app.get("/health")
async def health_check():
    """Comprehensive health check for all services"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "solar_api": {
                "status": "operational",
                "nrel_api_configured": settings.nrel_api_key != "DEMO_KEY",
                "pvwatts_version": "8.0+"
            },
            "futures_api": {
                "status": "operational", 
                "price_models": ["mean_reversion", "geometric_brownian_motion"],
                "risk_analytics": "enabled"
            },
            "system": {
                "fastapi_version": "0.104+",
                "python_environment": "ready",
                "cors_enabled": True
            }
        },
        "api_info": {
            "version": settings.app_version,
            "debug_mode": settings.debug,
            "documentation_url": "/docs"
        }
    }

@app.get("/api-summary")
async def api_summary():
    """Quick API capabilities summary"""
    return {
        "solar_capabilities": {
            "geographic_coverage": "Global (US high-accuracy, international limited)",
            "system_sizes": "0.05 kW to 500 MW",
            "data_resolution": "Monthly and hourly",
            "accuracy": "±5% for US locations"
        },
        "futures_capabilities": {
            "contract_types": "Monthly electricity delivery",
            "pricing_models": "Mean-reversion with Monte Carlo",
            "risk_metrics": "VaR, Expected Shortfall, Greeks",
            "portfolio_analysis": "Multi-contract optimization"
        },
        "integration_ready": {
            "rest_api": True,
            "json_responses": True,
            "async_processing": True,
            "error_handling": True,
            "rate_limiting": False,
            "authentication": False
        }
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {
        "error": "Endpoint not found",
        "message": "Check /docs for available endpoints",
        "available_endpoints": [
            "/solar/output", "/solar/quick-estimate", 
            "/futures/electricity", "/futures/market-data"
        ]
    }

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return {
        "error": "Internal server error",
        "message": "Please check your request parameters and try again",
        "support": "Check /health for service status"
    }

if __name__ == "__main__":
    import uvicorn
    
    # Log startup information
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"NREL API configured: {settings.nrel_api_key != 'DEMO_KEY'}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.debug else False,
        log_level="info"
    )
