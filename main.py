from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import logging
import os
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

# Setup templates directory
if not os.path.exists("templates"):
    os.makedirs("templates")

# Setup static directory  
if not os.path.exists("static"):
    os.makedirs("static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(solar.router)
app.include_router(futures.router)

# ✅ ADD FRONTEND ROUTE
@app.get("/frontend", response_class=HTMLResponse)
async def frontend_interface(request: Request):
    """Serve the frontend interface for the API"""
    return templates.TemplateResponse("index.html", {"request": request})

# Your existing endpoints...
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
            "Live IEX India price integration",
            "Risk analytics and portfolio management",
            "Dual currency support (USD/INR)"
        ],
        "endpoints": {
            # Solar endpoints
            "solar_output": "/solar/output",
            "solar_hourly_output": "/solar/hourly-output", 
            "solar_quick_estimate": "/solar/quick-estimate",
            "solar_supported_locations": "/solar/supported-locations",
            
            # Futures endpoints  
            "electricity_futures": "/futures/electricity",
            "current_electricity_price": "/futures/current-price",
            "futures_market_data": "/futures/market-data",
            "futures_health": "/futures/health",
            
            # Frontend
            "web_interface": "/frontend",
            
            # System endpoints
            "health_check": "/health",
            "api_summary": "/api-summary",
            "api_documentation": "/docs",
            "alternative_docs": "/redoc"
        }
    }

# Your existing health check and other endpoints...


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
                "pvwatts_version": "8.0+",
                "endpoints": ["/solar/output", "/solar/quick-estimate", "/solar/hourly-output"]
            },
            "futures_api": {
                "status": "operational", 
                "price_models": ["mean_reversion"],
                "risk_analytics": "enabled",
                "iex_integration": "live price fetching",
                "currency_support": ["USD", "INR"],
                "endpoints": ["/futures/electricity", "/futures/current-price"]
            },
            "system": {
                "fastapi_version": "0.104+",
                "python_environment": "ready",
                "cors_enabled": True,
                "error_handling": "JSONResponse format"
            }
        },
        "api_info": {
            "version": settings.app_version,
            "debug_mode": settings.debug,
            "documentation_url": "/docs",
            "total_endpoints": 10
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
            "accuracy": "±5% for US locations",
            "weather_data": "NSRDB 2020 TMY satellite data"
        },
        "futures_capabilities": {
            "contract_types": "Monthly electricity delivery",
            "pricing_models": "Mean-reversion with Monte Carlo",
            "risk_metrics": "VaR, Expected Shortfall, Greeks",
            "portfolio_analysis": "Multi-contract optimization",
            "price_sources": "IEX India live market data",
            "currencies": ["USD", "INR"]
        },
        "integration_ready": {
            "rest_api": True,
            "json_responses": True,
            "async_processing": True,
            "error_handling": True,
            "live_data_feeds": True,
            "dual_currency": True,
            "rate_limiting": False,
            "authentication": False
        },
        "market_coverage": {
            "solar_resource": "Global coverage via NREL",
            "electricity_markets": "India (IEX) with international pricing",
            "currencies": "USD (international) and INR (India)",
            "contract_years": "Dynamic (current year + future)"
        }
    }

# FIXED Error handlers - return JSONResponse instead of dict
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint not found",
            "message": "Check /docs for available endpoints",
            "available_endpoints": [
                "/solar/output", 
                "/solar/quick-estimate", 
                "/futures/electricity", 
                "/futures/current-price",
                "/futures/market-data",
                "/health",
                "/api-summary"
            ],
            "documentation": "/docs"
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "Please check your request parameters and try again",
            "support": "Check /health for service status",
            "timestamp": datetime.now().isoformat(),
            "suggestion": "Verify API parameters and try again"
        }
    )

# Add a catch-all for method not allowed
@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=405,
        content={
            "error": "Method not allowed",
            "message": f"Method {request.method} not allowed for {request.url.path}",
            "allowed_methods": ["GET", "POST"],
            "documentation": "/docs"
        }
    )

if __name__ == "__main__":
    import uvicorn
    
    # Log startup information
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"NREL API configured: {settings.nrel_api_key != 'DEMO_KEY'}")
    logger.info("Available endpoints:")
    logger.info("  Solar: /solar/output, /solar/quick-estimate, /solar/hourly-output")
    logger.info("  Futures: /futures/electricity, /futures/current-price")
    logger.info("  System: /health, /api-summary, /docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.debug else False,
        log_level="info"
    )
