import numpy as np
from typing import List, Tuple
from math import sqrt, exp
from datetime import datetime
from numpy.random import default_rng

class ElectricityFuturesService:
    """Advanced electricity futures pricing service with solar integration"""
    
    def __init__(self, random_seed: int = 42):
        self.rng = default_rng(random_seed)
        
    def simulate_mean_reverting_prices(
        self, 
        s0: float, 
        kappa: float, 
        theta: float, 
        sigma: float, 
        T: float, 
        n_steps: int, 
        n_paths: int
    ) -> np.ndarray:
        """
        Simulate electricity prices using Ornstein-Uhlenbeck mean-reversion model
        
        dS = κ(θ - S)dt + σdW
        
        Perfect for electricity markets where prices revert to marginal cost
        """
        dt = T / n_steps
        paths = np.empty((n_paths, n_steps + 1))
        paths[:, 0] = s0
        
        # Pre-calculate drift and diffusion terms for efficiency
        drift_factor = exp(-kappa * dt)
        mean_factor = theta * (1 - drift_factor)
        vol_factor = sigma * sqrt((1 - exp(-2 * kappa * dt)) / (2 * kappa))
        
        for t in range(1, n_steps + 1):
            z = self.rng.standard_normal(n_paths)
            paths[:, t] = paths[:, t-1] * drift_factor + mean_factor + vol_factor * z
            
            # Electricity prices cannot be negative
            paths[:, t] = np.maximum(paths[:, t], 0.01)
            
        return paths
    
    def calculate_futures_fair_value(
        self, 
        spot_price_paths: np.ndarray, 
        solar_generation: List[float],
        risk_free_rate: float,
        time_to_delivery: List[float]
    ) -> Tuple[List[float], List[float]]:
        """
        Calculate fair value of electricity futures using solar generation weighting
        
        Fair Value = E[Spot Price at Delivery] * Solar Generation Weight
        """
        futures_prices = []
        price_volatilities = []
        
        for month, (generation, ttd) in enumerate(zip(solar_generation, time_to_delivery)):
            if month + 1 < spot_price_paths.shape[1]:
                # Extract prices at delivery time for this month
                delivery_prices = spot_price_paths[:, month + 1]
                
                # Weight by solar generation (more generation = higher impact)
                generation_weight = generation / max(solar_generation) if max(solar_generation) > 0 else 1.0
                weighted_prices = delivery_prices * generation_weight
                
                # Calculate risk-adjusted fair value
                expected_price = np.mean(weighted_prices)
                price_vol = np.std(weighted_prices)
                
                # Add risk premium for longer-dated contracts
                risk_premium = 0.02 * ttd * expected_price  # 2% annual risk premium
                fair_value = expected_price + risk_premium
                
                futures_prices.append(fair_value)
                price_volatilities.append(price_vol)
            else:
                # Fallback for edge cases
                futures_prices.append(spot_price_paths[0, 0])
                price_volatilities.append(spot_price_paths[0, 0] * 0.25)
                
        return futures_prices, price_volatilities
    
    def calculate_greeks(
        self, 
        futures_price: float, 
        spot_price: float, 
        volatility: float,
        time_to_delivery: float
    ) -> dict:
        """Calculate futures Greeks for risk management"""
        
        # Delta: sensitivity to spot price changes
        # For futures, delta approaches 1 as time to delivery approaches 0
        delta = 0.7 + 0.3 * exp(-2 * time_to_delivery)
        
        # Gamma: convexity measure
        gamma = 0.1 * exp(-time_to_delivery) / spot_price if spot_price > 0 else 0
        
        # Theta: time decay
        theta = -0.05 * futures_price * time_to_delivery
        
        # Vega: volatility sensitivity
        vega = futures_price * sqrt(time_to_delivery) * 0.4
        
        return {
            "delta": delta,
            "gamma": gamma,
            "theta": theta,
            "vega": vega
        }
    
    def calculate_portfolio_risk_metrics(
        self, 
        revenue_simulations: List[List[float]]
    ) -> dict:
        """Calculate comprehensive portfolio risk metrics"""
        
        if not revenue_simulations or not revenue_simulations[0]:
            return {
                "mean_revenue": 0.0,
                "revenue_volatility": 0.0,
                "sharpe_ratio": 0.0,
                "value_at_risk_95": 0.0,
                "expected_shortfall_95": 0.0,
                "seasonal_premium": [0.0] * 12
            }
        
        # Convert to numpy for easier calculations
        revenues = np.array(revenue_simulations)
        annual_revenues = np.sum(revenues, axis=1)
        
        # Basic statistics
        mean_revenue = np.mean(annual_revenues)
        revenue_std = np.std(annual_revenues)
        
        # Risk metrics
        sorted_revenues = np.sort(annual_revenues)
        var_95_index = int(0.05 * len(sorted_revenues))
        
        value_at_risk = sorted_revenues[var_95_index] if var_95_index < len(sorted_revenues) else sorted_revenues[0]
        expected_shortfall = np.mean(sorted_revenues[:var_95_index]) if var_95_index > 0 else sorted_revenues[0]
        
        # Sharpe ratio (assuming risk-free rate already accounted for)
        sharpe_ratio = mean_revenue / revenue_std if revenue_std > 0 else 0
        
        # Seasonal analysis
        monthly_means = np.mean(revenues, axis=0)
        avg_monthly = np.mean(monthly_means) if len(monthly_means) > 0 else 1.0
        seasonal_premium = [float(m / avg_monthly - 1) for m in monthly_means] if avg_monthly > 0 else [0.0] * len(monthly_means)
        
        # Ensure we have 12 months of seasonal data
        while len(seasonal_premium) < 12:
            seasonal_premium.append(0.0)
        
        return {
            "mean_revenue": float(mean_revenue),
            "revenue_volatility": float(revenue_std),
            "sharpe_ratio": float(sharpe_ratio),
            "value_at_risk_95": float(value_at_risk),
            "expected_shortfall_95": float(expected_shortfall),
            "seasonal_premium": seasonal_premium[:12]
        }

# Global service instance
futures_service = ElectricityFuturesService()
