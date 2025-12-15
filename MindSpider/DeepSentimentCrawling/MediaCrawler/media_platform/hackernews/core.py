import asyncio
from typing import Dict
from datetime import datetime

from base.base_crawler import AbstractCrawler
from media_platform.hackernews.client import HackerNewsClient
from database.models import WeiboNote
from tools.utils import utils
from var import crawler_type_var, source_keyword_var
import config

class HackerNewsCrawler(AbstractCrawler):
    def __init__(self):
        self.client = HackerNewsClient()
        self.platform = "hackernews"

    async def launch_browser(self, chromium, playwright_proxy, user_agent, headless=True):
        pass

    async def start(self):
        crawler_type = crawler_type_var.get()
        if crawler_type == "search":
            if config.KEYWORDS:
                keywords = config.KEYWORDS.split(',')
                for keyword in keywords:
                    keyword = keyword.strip()
                    if not keyword:
                        continue
                    source_keyword_var.set(keyword)
                    await self.search()

    async def search(self):
        keyword = source_keyword_var.get()
        target_count = config.CRAWLER_MAX_NOTES_COUNT
        
        utils.logger.info(f"[HackerNewsCrawler] Starting crawl for: {keyword}, target: {target_count}")
        
        # Calculate timestamp for last 24h/custom window? 
        # For now, let's just fetch recent. 
        # Algolia search_by_date sorts by date desc naturally.
        
        total_crawled = 0
        page = 0
        hits_per_page = 20
        
        while total_crawled < target_count:
            data = await self.client.search_stories(keyword, hits_per_page=hits_per_page, page=page)
            if not data:
                break
                
            hits = data.get('hits', [])
            if not hits:
                utils.logger.info(f"[HackerNewsCrawler] No more hits found.")
                break
            
            utils.logger.info(f"[HackerNewsCrawler] Found {len(hits)} stories on page {page}")
            
            for hit in hits:
                await self._process_hit(hit, keyword)
                total_crawled += 1
                if total_crawled >= target_count:
                    break
            
            if total_crawled >= target_count:
                break
                
            page += 1
            await asyncio.sleep(1) # Polite delay
            
        utils.logger.info(f"[HackerNewsCrawler] Search completed. Total processed: {total_crawled}")

    async def _process_hit(self, hit: Dict, keyword: str):
        try:
            # ID
            story_id = str(hit.get('objectID'))
            if not story_id:
                return
            
            # Content
            title = hit.get('title', '')
            url = hit.get('url', '')
            story_text = hit.get('story_text', '')
            
            content = f"【Title】 {title}"
            if story_text:
                content += f"\n\n{story_text}"
            
            # Time
            created_at_i = hit.get('created_at_i', 0)
            create_time = int(created_at_i * 1000) # ms
            
            # User
            author = hit.get('author', 'unknown')
            
            # Metrics
            points = str(hit.get('points', 0))
            num_comments = str(hit.get('num_comments', 0))
            
            # HN Link
            note_url = f"https://news.ycombinator.com/item?id={story_id}"
            
            # Create Model
            note = WeiboNote()
            note.note_id = int(story_id)
            note.content = content
            note.create_time = create_time
            note.create_date_time = datetime.fromtimestamp(create_time/1000).strftime('%Y-%m-%d %H:%M:%S')
            note.liked_count = points
            note.comments_count = num_comments
            note.shared_count = "0"
            note.user_id = author
            note.nickname = author
            note.avatar = "" 
            note.note_url = note_url
            note.source_keyword = keyword
            note.platform = "hackernews" 
            
            # Helper to save (using common store logic)
            from media_platform.common.store import save_or_update_note
            await save_or_update_note(note)
            
        except Exception as e:
            utils.logger.error(f"[HackerNewsCrawler] Error processing hit {hit.get('objectID')}: {e}")
