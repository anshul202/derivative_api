
## Support

For questions, issues, or feature requests:
- Create an issue on GitHub
- Check the [API documentation](https://chainfly-derivative-finance.onrender.com/docs)
- Review the [health endpoint](https://chainfly-derivative-finance.onrender.com/health) for service status

---
---

## Financial Models

### Price Simulation
- **Mean-Reversion Model**: Ornstein-Uhlenbeck process for electricity prices
- **Monte Carlo Simulation**: 10,000+ path generation for robust statistics
- **Risk Analytics**: Value-at-Risk, Expected Shortfall, and Greeks calculation

### Futures Pricing
- **Solar Generation Weighting**: Higher generation months carry more weight
- **Risk Premium Adjustment**: Time-to-delivery risk compensation
- **Currency Conversion**: Real-time USD/INR exchange rates

## Geographic Coverage

- **Solar Data**: Global coverage via NREL (US high-accuracy, international limited)
- **Electricity Prices**: India (IEX live data) with international modeling support
- **Weather Data**: NSRDB 2020 TMY satellite-derived data

## Security & Performance

- **Input Validation**: Comprehensive Pydantic validation for all endpoints
- **Error Handling**: Graceful fallbacks and informative error messages  
- **Caching**: 5-minute price caching for performance optimization
- **CORS**: Enabled for cross-origin web application integration

## Deployment

The API is deployed on Render with:
- Automatic deployments from GitHub
- Environment variable management
- Health monitoring and uptime tracking
- Scalable infrastructure

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.


## Acknowledgments

- [NREL](https://www.nrel.gov/) for PVWatts V8 API and solar resource data
- [IEX India](https://www.iexindia.com/) for electricity market data
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [Render](https://render.com/) for reliable deployment platform

