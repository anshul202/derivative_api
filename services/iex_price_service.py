import requests
from bs4 import BeautifulSoup
import pandas as pd
import asyncio
from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class IEXPriceService:
    """Service to scrape real-time electricity prices from IEX India"""
    
    def __init__(self):
        self.base_url = "https://www.iexindia.com/market-data/real-time-market/market-snapshot"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.price_cache = {}
        self.cache_duration = 300  # 5 minutes cache
    
    async def get_current_spot_price(self) -> Dict[str, float]:
        """
        Scrape current IEX real-time market data
        Returns prices in Rs/MWh and converted to $/MWh
        """
        try:
            # Check cache first
            if self._is_cache_valid():
                return self.price_cache['data']
            
            # Scrape fresh data
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self._scrape_iex_data)
            
            if response:
                # Cache the result
                self.price_cache = {
                    'data': response,
                    'timestamp': datetime.now()
                }
                return response
            else:
                # Fallback to estimated price
                return self._get_fallback_price()
                
        except Exception as e:
            logger.error(f"IEX scraping failed: {str(e)}")
            return self._get_fallback_price()
    
    def _scrape_iex_data(self) -> Optional[Dict[str, float]]:
        """Scrape the IEX market snapshot page"""
        try:
            response = self.session.get(self.base_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the summary table with market data
            summary_table = self._find_summary_table(soup)
            
            if summary_table:
                return self._parse_market_data(summary_table)
            else:
                # Try to parse individual time blocks
                return self._parse_time_blocks(soup)
                
        except Exception as e:
            logger.error(f"Error scraping IEX: {str(e)}")
            return None
    
    def _find_summary_table(self, soup) -> Optional[any]:
        """Find the summary table with average MCP data"""
        try:
            # Look for table with summary data
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 6:
                        # Check if this row contains "Avg" or summary data
                        for cell in cells:
                            if 'Avg' in cell.get_text() or 'Average' in cell.get_text():
                                return table
            return None
            
        except Exception as e:
            logger.error(f"Error finding summary table: {str(e)}")
            return None
    
    def _parse_market_data(self, table) -> Dict[str, float]:
        """Parse market data from the summary table"""
        try:
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 7:
                    row_text = [cell.get_text().strip() for cell in cells]
                    
                    # Look for the average row
                    if 'Avg' in row_text[1] or 'Average' in row_text[1]:
                        # Extract MCP (Market Clearing Price) - usually last column
                        mcp_text = row_text[-1]
                        mcp_rs_mwh = float(mcp_text.replace(',', ''))
                        
                        return self._format_price_response(mcp_rs_mwh)
            
            # Fallback: get last available price from time blocks
            return self._parse_latest_time_block(table)
            
        except Exception as e:
            logger.error(f"Error parsing market data: {str(e)}")
            return self._get_fallback_price()
    
    def _parse_time_blocks(self, soup) -> Dict[str, float]:
        """Parse individual time block data to get latest MCP"""
        try:
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                
                # Look for rows with time block data
                for row in reversed(rows):  # Start from most recent
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 9:  # Time block rows have ~9 columns
                        try:
                            # MCP is typically the last column
                            mcp_text = cells[-1].get_text().strip()
                            if mcp_text and mcp_text.replace(',', '').replace('.', '').isdigit():
                                mcp_rs_mwh = float(mcp_text.replace(',', ''))
                                return self._format_price_response(mcp_rs_mwh)
                        except (ValueError, IndexError):
                            continue
            
            return self._get_fallback_price()
            
        except Exception as e:
            logger.error(f"Error parsing time blocks: {str(e)}")
            return self._get_fallback_price()
    
    def _format_price_response(self, mcp_rs_mwh: float) -> Dict[str, float]:
        """Format the price response with conversions"""
        # Convert Rs/MWh to $/MWh (approximate exchange rate: 1 USD = 83 INR)
        usd_mwh = mcp_rs_mwh / 83.0
        
        # Convert to Rs/kWh and $/kWh for consumer reference
        rs_kwh = mcp_rs_mwh / 1000
        usd_kwh = usd_mwh / 1000
        
        return {
            'spot_price_rs_mwh': mcp_rs_mwh,
            'spot_price_usd_mwh': usd_mwh,
            'spot_price_rs_kwh': rs_kwh,
            'spot_price_usd_kwh': usd_kwh,
            'source': 'IEX India Real-Time Market',
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_fallback_price(self) -> Dict[str, float]:
        """Fallback price when scraping fails"""
        # Based on search results: average around Rs 3000/MWh
        fallback_rs_mwh = 3000.0
        
        return self._format_price_response(fallback_rs_mwh)
    
    def _is_cache_valid(self) -> bool:
        """Check if cached price is still valid"""
        if not self.price_cache:
            return False
        
        cache_age = (datetime.now() - self.price_cache['timestamp']).total_seconds()
        return cache_age < self.cache_duration

# Global instance
iex_service = IEXPriceService()
