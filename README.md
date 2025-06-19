


solar_derivatives_api/
├── .venv/                      # Virtual environment 
├── main.py                     # FastAPI application entry point
├── config/
│   ├── __init__.py
│   └── settings.py            # Configuration settings
├── models/
│   ├── __init__.py
│   ├── solar_models.py        # Pydantic models for solar data
│   ├── pricing_models.py      # Financial derivative models
│   └── response_models.py     # API response models
├── services/
│   ├── __init__.py
│   ├── solar_service.py       # pvlib and PVWatts integration
│   ├── pricing_service.py     # Monte Carlo pricing engine
│   └── validation_service.py  # Data validation utilities
├── routers/
│   ├── __init__.py
│   ├── solar.py              # Solar-related endpoints
│   ├── derivatives.py        # Derivative pricing endpoints
│   └── health.py             # Health check endpoints
├── utils/
│   ├── __init__.py
│   ├── helpers.py            # Utility functions
│   └── exceptions.py         # Custom exception classes
├── tests/
│   ├── __init__.py
│   ├── test_main.py          # Main app tests
│   ├── test_solar_service.py # Solar service tests
│   └── test_pricing_service.py # Pricing service tests
├── static/                    # Static files (optional)
├── requirements.txt           # Project dependencies
├── requirements-dev.txt       # Development dependencies
├── .env                       # Environment variables (don't commit)
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore file
├── README.md                 # Project documentation
├── Dockerfile                # Docker configuration (optional)
└── docker-compose.yml        # Docker compose (optional)
