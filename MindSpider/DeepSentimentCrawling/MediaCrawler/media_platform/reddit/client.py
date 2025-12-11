import asyncio
from typing import Dict, Optional, Any
import random
from loguru import logger
from curl_cffi.requests import AsyncSession

class RedditClient:
    def __init__(self, proxies: Optional[Dict] = None):
        self.proxies = proxies
        # Minimal headers - let curl_cffi handle the rest via impersonate
        self.headers = {}
        self.timeout = 30
        self.cookies = {}
        
        logger.info("[RedditClient] 初始化完成 - 使用 curl_cffi (Chrome impersonation)")

    async def request(self, method: str, url: str, params: Optional[Dict] = None) -> Dict:
        """
        发送HTTP请求到Reddit JSON端点 (using curl_cffi)
        """
        # 添加随机延迟（2-4秒），避免被识别为机器人
        delay = random.uniform(2.0, 4.0)
        await asyncio.sleep(delay)
        
        # impersonate="chrome124" is a more recent browser fingerprint
        async with AsyncSession(
            proxies=self.proxies,
            timeout=self.timeout,
            impersonate="chrome124",
            cookies=self.cookies,
            verify=True 
        ) as session:
            try:
                logger.info(f"[RedditClient] 请求URL: {url} | 方法: {method} | 参数: {params}")
                
                response = await session.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params
                )
                
                # Update cookies
                if response.cookies:
                    self.cookies.update(dict(response.cookies))
                
                logger.info(f"[RedditClient] 响应状态: {response.status_code}")
                
                if response.status_code == 200:
                    # curl_cffi response.text is a property/method just like requests
                    # logger.info(f"[RedditClient] 成功获取数据 (前200字符): {response.text[:200]}")
                    return response.json()
                elif response.status_code == 403:
                    logger.error(f"[RedditClient] 403错误 - Reddit阻止了请求 (尽管使用了curl_cffi)")
                    logger.error(f"[RedditClient] 响应内容: {response.text[:500]}")
                    # Raise generic exception
                    raise Exception(f"403 Forbidden: {url}")
                else:
                    response.raise_for_status()
                    return response.json()
                    
            except Exception as e:
                logger.error(f"[RedditClient] 请求失败: {e}")
                raise

    async def search(self, keyword: str, limit: int = 100, after: str = None, subreddits: list = None) -> dict:
        """
        在Reddit搜索关键词
        使用old.reddit.com端点，更稳定且不易被阻止
        支持分页 (after)
        支持限定板块 (subreddits) -> 使用 r/sub1+sub2/search 路径
        """
        # 默认搜索全站
        url = "https://old.reddit.com/search.json"
        
        # 如果指定了板块，则构建限定范围的搜索URL
        # 格式: https://old.reddit.com/r/sub1+sub2+sub3/search.json
        if subreddits and len(subreddits) > 0:
            joined_subs = "+".join(subreddits)
            url = f"https://old.reddit.com/r/{joined_subs}/search.json"
            
        params = {
            "q": keyword,
            "limit": limit,
            "sort": "new",
            "type": "link",  # 只搜索帖子
            "t": "all",  # 时间范围
            "restrict_sr": "on" if subreddits else "off"
        }
        
        if after:
            params['after'] = after
            
        logger.info(f"[RedditClient] 搜索URL: {url} | Keyword: {keyword} | Subs: {len(subreddits) if subreddits else 0}")
        return await self.request("GET", url, params)

    async def get_comments(self, post_id: str) -> list:
        """
        获取指定帖子的评论
        """
        clean_id = post_id.split('_')[-1] if '_' in post_id else post_id
        url = f"https://old.reddit.com/comments/{clean_id}.json"
        
        logger.info(f"[RedditClient] 获取帖子评论: {clean_id}")
        return await self.request("GET", url)
