import asyncio
from typing import Dict, Optional, Any
import random
import re
import html
import time
from datetime import datetime
from loguru import logger
from curl_cffi.requests import AsyncSession
import feedparser

class RedditClient:
    def __init__(self, proxies: Optional[Dict] = None):
        self.proxies = proxies
        # Minimal headers - let curl_cffi handle the rest via impersonate
        self.headers = {}
        self.timeout = 30
        self.cookies = {}
        
        logger.info("[RedditClient] 初始化完成 - RSS Mode (curl_cffi + feedparser)")

    async def request(self, method: str, url: str, params: Optional[Dict] = None) -> str:
        """
        发送HTTP请求 (using curl_cffi) returning TEXT content for RSS parsing
        """
        delay = random.uniform(2.0, 4.0)
        await asyncio.sleep(delay)
        
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
                
                if response.cookies:
                    self.cookies.update(dict(response.cookies))
                
                logger.info(f"[RedditClient] 响应状态: {response.status_code}")
                
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 403:
                    logger.error(f"[RedditClient] 403错误 via RSS")
                    raise Exception(f"403 Forbidden: {url}")
                else:
                    response.raise_for_status()
                    return response.text
                    
            except Exception as e:
                logger.error(f"[RedditClient] 请求失败: {e}")
                raise

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags and unescape entities"""
        if not text:
            return ""
        # Unescape HTML entities first (&amp; -> &, etc.)
        text = html.unescape(text)
        # Remove tags
        clean = re.sub(r'<[^>]+>', '', text)
        return clean.strip()

    async def search(self, keyword: str, limit: int = 100, after: str = None, subreddits: list = None) -> dict:
        """
        Search Reddit using RSS Feed to bypass blocking.
        Returns a dict structure mimicking the old JSON API so core.py works unchanged.
        """
        # RSS Endpoint
        base_url = "https://www.reddit.com/search.rss"
        if subreddits and len(subreddits) > 0:
            joined_subs = "+".join(subreddits)
            base_url = f"https://www.reddit.com/r/{joined_subs}/search.rss"
            
        params = {
            "q": keyword,
            "sort": "new",
            "limit": 100 # RSS usually allows up to 100
        }
        if after:
            params["after"] = after
            params["count"] = 100 # Helps with pagination context
        
        logger.info(f"[RedditClient] RSS Search: {base_url} | Keyword: {keyword}")
        
        try:
            xml_content = await self.request("GET", base_url, params)
            
            # Parse RSS
            feed = feedparser.parse(xml_content)
            
            if feed.bozo:
                logger.warning(f"[RedditClient] RSS Parsing Warning: {feed.bozo_exception}")

            children = []
            for entry in feed.entries:
                # Map RSS entry to JSON-like 'data' dict
                
                # ID: Extract from id tag (usually url) or link
                # RSS id: <id>https://www.reddit.com/r/stocks/comments/1hba.../title/</id>
                # We need a clean ID.
                # Try to extract t3_xxxxx or just use hash?
                # Link: https://www.reddit.com/r/stocks/comments/1hba5y7/title/
                # ID is '1hba5y7'
                
                post_id = ""
                if hasattr(entry, 'link'):
                    match = re.search(r'/comments/([a-zA-Z0-9]+)/', entry.link)
                    if match:
                        post_id = match.group(1).lower()
                
                if not post_id:
                    continue # Skip if cant parse ID needed for DB
                
                # Content
                title = entry.title if hasattr(entry, 'title') else ""
                # Summary is usually HTML content
                raw_summary = entry.summary if hasattr(entry, 'summary') else ""
                # Some feeds allow content tag
                if hasattr(entry, 'content'):
                    raw_summary = entry.content[0].value
                
                selftext = self._strip_html(raw_summary)
                
                # Time
                # entry.published_parsed is a struct_time
                created_utc = 0
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    created_utc = time.mktime(entry.published_parsed)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    created_utc = time.mktime(entry.updated_parsed)
                
                # Author
                author = "unknown"
                if hasattr(entry, 'author'):
                    # RSS author format: "/u/username"
                    author = entry.author.replace('/u/', '')
                    
                # Permalink (relative to reddit.com expected by some logic?)
                # core.py does: note.note_url = f"https://www.reddit.com{permalink}"
                # But RSS gives full link. We can strip domain or adjust core.
                # Let's adjust permalink to be relative path to match old JSON behavior
                permalink = entry.link.replace("https://www.reddit.com", "").replace("https://old.reddit.com", "")
                
                post_data = {
                    'data': {
                        'id': post_id,
                        'title': title,
                        'selftext': selftext,
                        'created_utc': created_utc,
                        'author': author,
                        'permalink': permalink,
                        'ups': 0, # RSS doesn't have live votes
                        'num_comments': 0 # RSS doesn't have live comment count
                    }
                }
                children.append(post_data)

            logger.info(f"[RedditClient] RSS Parsed: Found {len(children)} items")
            
            # Construct JSON-like response wrapper
            # Reddit's 'after' cursor is usually t3_id. 
            # We take the last post found to provide continuity.
            next_cursor = None
            if children:
                last_post_id = children[-1]['data']['id']
                if not last_post_id.startswith('t3_'):
                    next_cursor = f"t3_{last_post_id}"
                else:
                    next_cursor = last_post_id

            return {
                'data': {
                    'children': children,
                    'after': next_cursor
                }
            }
            
        except Exception as e:
            logger.error(f"[RedditClient] RSS Search Logic Failed: {e}")
            return {'data': {'children': [], 'after': None}}

    async def get_comments(self, post_id: str) -> list:
        """
        RSS doesn't support fetching comments easily (requires scraping HTML).
        Returning empty to prevent errors if enabled.
        """
        logger.warning("[RedditClient] get_comments is NOT supported in RSS mode.")
        return []
