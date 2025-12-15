import asyncio
from typing import Dict, Optional, Any
import time
from loguru import logger
from curl_cffi.requests import AsyncSession

class HackerNewsClient:
    def __init__(self, proxies: Optional[Dict] = None):
        self.proxies = proxies
        self.base_url = "https://hn.algolia.com/api/v1/search_by_date"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://hn.algolia.com/",
        }
        self.timeout = 30
        
        logger.info("[HackerNewsClient] Initialized (curl_cffi)")

    async def search_stories(self, keyword: str, hits_per_page: int = 20, page: int = 0, min_timestamp: Optional[int] = None) -> Dict:
        """
        Search HN stories by keyword using Algolia API.
        URL: https://hn.algolia.com/api/v1/search_by_date
        """
        params = {
            "query": keyword,
            "tags": "story",
            "hitsPerPage": hits_per_page,
            "page": page
        }
        
        # Add time filter if provided (Algolia expects numericFilters)
        if min_timestamp:
            # timestamp in API is seconds
            params["numericFilters"] = f"created_at_i>{min_timestamp}"

        async with AsyncSession(
            proxies=self.proxies,
            timeout=self.timeout,
            impersonate="chrome124", 
            verify=True
        ) as session:
            try:
                logger.info(f"[HackerNewsClient] Searching: {keyword} (page {page})")
                response = await session.get(self.base_url, params=params, headers=self.headers)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"[HackerNewsClient] Error {response.status_code}: {response.text[:200]}")
                    return {}
            except Exception as e:
                logger.error(f"[HackerNewsClient] Request Failed: {e}")
                return {}
