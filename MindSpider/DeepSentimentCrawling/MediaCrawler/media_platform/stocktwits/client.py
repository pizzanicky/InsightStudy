import asyncio
from typing import Dict, Optional, Any
import random
from loguru import logger
from curl_cffi.requests import AsyncSession

class StocktwitsClient:
    def __init__(self, proxies: Optional[Dict] = None):
        self.proxies = proxies
        # Stocktwits API is protected by WAF (Cloudflare/Incapsula often)
        # We mimic a browser request
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://stocktwits.com/",
            "Origin": "https://stocktwits.com",
        }
        self.timeout = 30
        self.cookies = {}
        
        logger.info("[StocktwitsClient] Initialized (curl_cffi)")

    async def get_symbol_stream(self, symbol: str, filter_type: str = "top", max_id: Optional[int] = None) -> Dict:
        """
        Fetch stream for a symbol.
        URL: https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json
        """
        # Clean symbol (remove $ if present)
        symbol = symbol.replace("$", "")
        
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
        
        # Check filter params if needed, currently just basic fetch
        params = {
            "filter": filter_type, 
            "limit": 30 # Default is usually 30
        }
        if max_id:
            params['max'] = max_id
        
        delay = random.uniform(1.0, 3.0)
        await asyncio.sleep(delay)
        
        async with AsyncSession(
            proxies=self.proxies,
            timeout=self.timeout,
            impersonate="chrome124", 
            cookies=self.cookies,
            verify=True
        ) as session:
            try:
                logger.info(f"[StocktwitsClient] Fetching stream: {symbol}")
                response = await session.get(url, params=params, headers=self.headers)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.warning(f"[StocktwitsClient] Symbol not found: {symbol}")
                    return {}
                elif response.status_code == 429:
                    logger.error(f"[StocktwitsClient] Rate Limit Exceeded")
                    return {}
                else:
                    logger.error(f"[StocktwitsClient] Error {response.status_code}: {response.text[:200]}")
                    return {}
            except Exception as e:
                logger.error(f"[StocktwitsClient] Request Failed: {e}")
                return {}
