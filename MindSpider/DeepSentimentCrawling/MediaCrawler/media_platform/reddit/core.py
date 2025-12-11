import asyncio
from typing import List, Optional, Dict
from datetime import datetime

from base.base_crawler import AbstractCrawler
from media_platform.reddit.client import RedditClient
from database.models import WeiboNote, WeiboNoteComment
from tools.utils import utils
from var import crawler_type_var, source_keyword_var
import config

class RedditCrawler(AbstractCrawler):
    def __init__(self):
        self.client = RedditClient()
        self.platform = "reddit"

    async def launch_browser(self, chromium, playwright_proxy, user_agent, headless=True):
        """
        Dummy implementation for AbstractCrawler
        """
        pass

    async def start(self):
        """
        Start the crawler
        """
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
        elif crawler_type == "detail":
            # Not fully implemented yet, but structure is here
            pass
        else:
            pass

    async def search(self):
        """
        Search Reddit and map to WeiboNote with pagination
        """
        keyword = source_keyword_var.get()
        target_count = config.CRAWLER_MAX_NOTES_COUNT
        
        # 准备板块列表
        subreddits = []
        if hasattr(config, 'REDDIT_SUBREDDITS') and config.REDDIT_SUBREDDITS:
            subreddits = config.REDDIT_SUBREDDITS
            utils.logger.info(f"[RedditCrawler] Applied subreddit filter: {len(subreddits)} subreddits")
        else:
            utils.logger.warning("[RedditCrawler] REDDIT_SUBREDDITS config NOT found or empty.")

        utils.logger.info(f"[RedditCrawler] Starting search for keyword: {keyword}, target: {target_count}")

        try:
            total_crawled = 0
            after_cursor = None
            
            while total_crawled < target_count:
                # Calculate remaining needed, capped at 100 (API limit)
                limit = min(target_count - total_crawled, 100)
                
                # Fetch data from Reddit
                # Pass subreddits list directly to use URL-based filtering (r/sub1+sub2/...)
                search_data = await self.client.search(keyword, limit=limit, after=after_cursor, subreddits=subreddits)
                
                if not search_data:
                    utils.logger.error(f"[RedditCrawler] Search returned empty response for keyword: {keyword}")
                    break

                if 'data' not in search_data or 'children' not in search_data['data']:
                    utils.logger.error(f"[RedditCrawler] Invalid response structure. Keys found: {search_data.keys()}")
                    if 'error' in search_data:
                        utils.logger.error(f"[RedditCrawler] Reddit Error: {search_data['error']}")
                    break

                posts = search_data['data']['children']
                if not posts:
                    utils.logger.info(f"[RedditCrawler] No more posts found for keyword: {keyword}")
                    break
                    
                utils.logger.info(f"[RedditCrawler] Found {len(posts)} posts in this batch (Target: {target_count})")

                for post in posts:
                    post_data = post['data']
                    await self._process_post(post_data, keyword)
                    total_crawled += 1
                    
                    if total_crawled >= target_count:
                        break
                
                # Get next page cursor
                after_cursor = search_data['data'].get('after')
                if not after_cursor:
                    utils.logger.info("[RedditCrawler] No 'after' cursor, pagination finished.")
                    break
                    
                utils.logger.info(f"[RedditCrawler] Moving to next page. Cursor: {after_cursor}, Total: {total_crawled}")
                
                # Simple delay to be nice to the API
                await asyncio.sleep(1)

            utils.logger.info(f"[RedditCrawler] Search completed. Total processed: {total_crawled}")

        except Exception as e:
            utils.logger.error(f"[RedditCrawler] Search failed: {e}")

    async def _process_post(self, post_data: Dict, keyword: str):
        """
        Process a single Reddit post and save as WeiboNote
        """
        try:
            # 1. ID Conversion (Base36 -> Base10)
            reddit_id_str = post_data.get('id', '')
            if not reddit_id_str:
                return
            
            # Convert Base36 string to Base10 integer
            # Reddit IDs are like '1j2k3l', we treat them as base36 numbers
            # User requirement: Strip prefix (e.g., t3_)
            clean_id = reddit_id_str.split('_')[-1] if '_' in reddit_id_str else reddit_id_str
            
            try:
                note_id_int = int(clean_id, 36)
                note_id = note_id_int # Store as int for BigInteger column
            except ValueError:
                utils.logger.error(f"[RedditCrawler] Failed to convert ID {reddit_id_str} to int")
                return

            # 2. Content Mapping
            title = post_data.get('title', '')
            selftext = post_data.get('selftext', '')
            content = f"{title}\n{selftext}"

            # 3. Time Conversion
            create_time = int(post_data.get('created_utc', 0) * 1000) # Milliseconds
            create_date_time = datetime.fromtimestamp(post_data.get('created_utc', 0)).strftime('%Y-%m-%d %H:%M:%S')

            # 4. Create WeiboNote object (Mapping)
            note = WeiboNote()
            note.note_id = note_id
            note.content = content
            note.create_time = create_time
            note.create_date_time = create_date_time
            note.liked_count = str(post_data.get('ups', 0))
            note.comment_count = str(post_data.get('num_comments', 0))
            note.shared_count = "0" # Reddit doesn't have exact share count in public API usually
            
            # Author info
            note.user_id = post_data.get('author', 'unknown') # Reddit username as ID
            note.nickname = post_data.get('author', 'unknown')
            note.avatar = "" # No easy avatar URL in search results
            
            # URL
            permalink = post_data.get('permalink', '')
            note.note_url = f"https://www.reddit.com{permalink}"
            
            # CRITICAL: Source Keyword
            note.source_keyword = keyword
            
            # Extra fields
            note.ip_location = ""
            
            # Save to DB
            utils.logger.info(f"[RedditCrawler] Saving post {reddit_id_str} (mapped ID: {note_id})")
            await self._save_note(note)
            
            # 5. Fetch Comments (if enabled)
            if config.ENABLE_GET_COMMENTS:
                await self._process_comments(reddit_id_str, note_id)
            
        except Exception as e:
            utils.logger.error(f"[RedditCrawler] Error processing post: {e}")

    async def _process_comments(self, reddit_post_id: str, db_note_id: int):
        """
        Fetch and process comments for a post
        """
        try:
            # 1. Fetch from API
            # Reddit API returns [post_listing, comment_listing]
            response = await self.client.get_comments(reddit_post_id)
            
            if not response or len(response) < 2:
                return
            
            comment_listing = response[1]
            comments_data = comment_listing.get('data', {}).get('children', [])
            
            # 2. Limit count
            max_comments = config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES
            comments_data = comments_data[:max_comments]
            
            db_comments = []
            for comment_item in comments_data:
                data = comment_item.get('data')
                if not data or data.get('kind') == 'more': # 'more' is pagination token
                    continue
                    
                # ID Conversion
                c_id_str = data.get('id', '')
                if not c_id_str:
                    continue
                try:
                    c_id_int = int(c_id_str, 36)
                except:
                    continue
                    
                # Time
                create_time = int(data.get('created_utc', 0) * 1000)
                
                # Create Model
                comm = WeiboNoteComment()
                comm.comment_id = c_id_int
                comm.note_id = db_note_id
                comm.content = data.get('body', '')
                comm.user_id = data.get('author', 'unknown')
                comm.nickname = data.get('author', 'unknown')
                comm.avatar = ""
                comm.comment_like_count = str(data.get('ups', 0))
                comm.sub_comment_count = "0" # Not fetching children for now
                comm.parent_comment_id = "" # Top level
                comm.create_time = create_time
                comm.create_date_time = datetime.fromtimestamp(data.get('created_utc', 0)).strftime('%Y-%m-%d %H:%M:%S')
                
                db_comments.append(comm)
            
            # 3. Save
            if db_comments:
                from media_platform.reddit.store import batch_update_reddit_comments
                utils.logger.info(f"[RedditCrawler] Saving {len(db_comments)} comments for post {reddit_post_id}")
                await batch_update_reddit_comments(db_comments)
                
        except Exception as e:
            utils.logger.error(f"[RedditCrawler] Error processing comments for {reddit_post_id}: {e}")

    async def _save_note(self, note: WeiboNote):
        """
        Save note to database
        """
        # This assumes db_utils has a generic save or we use specific update_weibo_note
        # Since we are reusing WeiboNote, we should use the weibo store logic or generic logic.
        # Let's import the weibo store function or implement a simple save here.
        # For now, let's try to use a direct DB session or a store module.
        
        # Ideally we should have a store/reddit.py but we are mapping to Weibo tables.
        # So we can use store/weibo.py functions IF they are generic enough, 
        # OR just implement a simple insertion here using db_utils.
        
        # Let's create a helper in store/reddit.py that actually writes to weibo_note table
        from media_platform.reddit.store import update_reddit_note_as_weibo
        await update_reddit_note_as_weibo(note)

    async def get_specified_notes(self):
        pass

    async def get_creators_and_notes(self):
        pass
