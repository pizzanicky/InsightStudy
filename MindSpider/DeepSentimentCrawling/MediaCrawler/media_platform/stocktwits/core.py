import asyncio
from typing import Dict
from datetime import datetime

from base.base_crawler import AbstractCrawler
from media_platform.stocktwits.client import StocktwitsClient
from database.models import WeiboNote
from tools.utils import utils
from var import crawler_type_var, source_keyword_var
import config

class StocktwitsCrawler(AbstractCrawler):
    def __init__(self):
        self.client = StocktwitsClient()
        self.platform = "stocktwits"

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
        """
        Fetch Stocktwits stream with pagination
        """
        keyword = source_keyword_var.get()
        target_count = config.CRAWLER_MAX_NOTES_COUNT
        
        utils.logger.info(f"[StocktwitsCrawler] Starting crawl for symbol: {keyword}, target: {target_count}")
        
        total_crawled = 0
        max_id = None # Cursor for next page (id < max)
        
        while total_crawled < target_count:
            # Note: Stocktwits API doesn't support 'limit' > 30 effectively in some tier, but let's just loop.
            # Client expects max_id param for pagination
            
            data = await self.client.get_symbol_stream(keyword, max_id=max_id)
            if not data:
                utils.logger.info(f"[StocktwitsCrawler] No data returned or end of stream.")
                break

            messages = data.get('messages', [])
            if not messages:
                utils.logger.info(f"[StocktwitsCrawler] No more messages found.")
                break
                
            utils.logger.info(f"[StocktwitsCrawler] Found {len(messages)} messages in this batch. (Total: {total_crawled})")
            
            for msg in messages:
                await self._process_message(msg, keyword)
                total_crawled += 1
                
                # Update max_id to track the last seen ID for creating next cursor
                # Stocktwits pagination: max={id} returns messages with id < {id}
                current_id = int(msg.get('id', 0))
                if max_id is None or current_id < max_id:
                    max_id = current_id
                
                if total_crawled >= target_count:
                    break
            
            if total_crawled >= target_count:
                break
                
            # Sleep slightly
            await asyncio.sleep(1)
            
        utils.logger.info(f"[StocktwitsCrawler] Search completed. Total processed: {total_crawled}")
            
    async def _process_message(self, msg: Dict, keyword: str):
        try:
            # ID
            msg_id = msg.get('id')
            if not msg_id:
                return
            
            # Sentiment Extraction
            # entities -> sentiment -> basic (Bullish/Bearish)
            sentiment_tag = ""
            entities = msg.get('entities', {}) or {}
            sentiment_info = entities.get('sentiment', {}) or {}
            basic_sentiment = sentiment_info.get('basic', "")
            
            # Content
            body = msg.get('body', '')
            
            if basic_sentiment:
                content = f"【{basic_sentiment}】 {body}"
            else:
                content = body
                
            # Time
            # Created at: "2024-12-10T14:30:00Z"
            created_at_str = msg.get('created_at', '')
            create_time = 0
            if created_at_str:
                try:
                    dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    create_time = int(dt.timestamp() * 1000)
                except:
                    pass
            
            if create_time == 0:
                create_time = int(datetime.now().timestamp() * 1000)

            # User Info
            user = msg.get('user', {})
            user_id = str(user.get('id', 'unknown'))
            username = user.get('username', 'unknown')
            
            # Likes
            likes = msg.get('likes', {})
            like_count = str(likes.get('total', 0))
            
            # URL
            # https://stocktwits.com/{username}/message/{id}
            note_url = f"https://stocktwits.com/{username}/message/{msg_id}"
            
            # Create Model
            note = WeiboNote()
            note.note_id = int(msg_id)
            note.content = content
            note.create_time = create_time
            note.create_date_time = datetime.fromtimestamp(create_time/1000).strftime('%Y-%m-%d %H:%M:%S')
            note.liked_count = like_count
            note.comments_count = "0" # Not in stream list usually
            note.shared_count = "0"
            note.user_id = user_id
            note.nickname = username
            note.avatar = user.get('avatar_url', '')
            note.note_url = note_url
            note.source_keyword = keyword
            note.platform = "stocktwits" # Unified field we added
            
            await self._save_note(note)
            
        except Exception as e:
            utils.logger.error(f"[StocktwitsCrawler] Error processing message {msg.get('id')}: {e}")

    async def _save_note(self, note: WeiboNote):
        # Save to DB
        from media_platform.common.store import save_or_update_note
        await save_or_update_note(note)
