import httpx
from typing import Dict, Optional, Any
import asyncio
import random
from loguru import logger

class RedditClient:
    def __init__(self, proxies: Optional[Dict] = None):
        self.proxies = proxies
        
        # 使用完整的真实浏览器请求头，模拟Chrome浏览器
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            # 关键：添加Referer让请求看起来更真实
            "Referer": "https://www.reddit.com/",
        }
        self.timeout = 30
        
        # Session cookies - 有助于绕过某些检测
        self.cookies = {}
        
        logger.info("[RedditClient] 初始化完成 - 使用增强型浏览器头部（无需OAuth）")

    async def request(self, method: str, url: str, params: Optional[Dict] = None) -> Dict:
        """
        发送HTTP请求到Reddit JSON端点
        """
        # 添加随机延迟（2-4秒），避免被识别为机器人
        delay = random.uniform(2.0, 4.0)
        await asyncio.sleep(delay)
        
        async with httpx.AsyncClient(
            proxy=self.proxies,  # httpx使用proxy而不是proxies
            timeout=self.timeout,
            follow_redirects=True,
            cookies=self.cookies  # 使用session cookies
        ) as client:
            try:
                logger.info(f"[RedditClient] 请求URL: {url} | 方法: {method} | 参数: {params}")
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params
                )
                
                # 保存cookies用于后续请求
                if response.cookies:
                    self.cookies.update(dict(response.cookies))
                
                logger.info(f"[RedditClient] 响应状态: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info(f"[RedditClient] 成功获取数据 (前200字符): {response.text[:200]}")
                    return response.json()
                elif response.status_code == 403:
                    logger.error(f"[RedditClient] 403错误 - Reddit阻止了请求")
                    logger.error(f"[RedditClient] 响应内容: {response.text[:500]}")
                    logger.warning("[RedditClient] 建议：1) 检查是否开启VPN  2) 更换代理IP  3) 增加请求延迟")
                    raise httpx.HTTPStatusError(f"403 Forbidden", request=response.request, response=response)
                else:
                    response.raise_for_status()
                    return response.json()
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"[RedditClient] HTTP错误: {e.response.status_code}")
                logger.error(f"[RedditClient] 响应详情: {e.response.text[:500]}")
                raise
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
            # 限制URL长度，虽然大多数浏览器支持很长的URL，但为了保险起见，或者Reddit可能有已知的限制
            # 但通常几十个subreddit是用 + 连接没问题的
            joined_subs = "+".join(subreddits)
            url = f"https://old.reddit.com/r/{joined_subs}/search.json"
            # 此时 q 参数只需要关键词，不需要再写 subreddit:xxx
            
        params = {
            "q": keyword,
            "limit": limit,
            "sort": "new",
            "type": "link",  # 只搜索帖子，不包括子版块或用户
            "t": "all",  # 时间范围：all (全部)
            "restrict_sr": "on" if subreddits else "off" # 如果指定了板块，限制在该范围内
        }
        
        if after:
            params['after'] = after
            
        logger.info(f"[RedditClient] 搜索URL: {url} | Keyword: {keyword} | Subs: {len(subreddits) if subreddits else 0}")
        return await self.request("GET", url, params)

    async def get_comments(self, post_id: str) -> list:
        """
        获取指定帖子的评论
        post_id: 可以是带前缀的ID (如't3_xyz')或纯ID (如'xyz')
        """
        # 如果ID带有前缀 t3_，去掉前缀
        clean_id = post_id.split('_')[-1] if '_' in post_id else post_id
        
        # 同样使用old.reddit.com端点
        url = f"https://old.reddit.com/comments/{clean_id}.json"
        
        logger.info(f"[RedditClient] 获取帖子评论: {clean_id}")
        return await self.request("GET", url)
