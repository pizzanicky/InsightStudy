import sys
import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select, and_
from loguru import logger

# Setup paths
project_root = Path(__file__).resolve().parents[1]
media_crawler_root = project_root / "MindSpider" / "DeepSentimentCrawling" / "MediaCrawler"

# Add MediaCrawler to sys.path for its internal imports
if str(media_crawler_root) not in sys.path:
    sys.path.append(str(media_crawler_root))

# Import root config.py using importlib to avoid naming conflict
import importlib.util
config_path = project_root / "config.py"
spec = importlib.util.spec_from_file_location("root_config", config_path)
root_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(root_config)
settings = root_config.settings

# Import database modules
from MindSpider.DeepSentimentCrawling.MediaCrawler.database.db_session import get_session, clear_engine_cache
from MindSpider.DeepSentimentCrawling.MediaCrawler.database.models import WeiboNote

# Import prompt
from DailyDigest.prompts import DAILY_DIGEST_PROMPT

# Import LLM Client
from InsightEngine.llms.base import LLMClient

class SimpleLLM:
    """Simple wrapper around LLMClient for easy use"""
    def __init__(self):
        # Load LLM config from environment
        api_key = settings.INSIGHT_ENGINE_API_KEY or os.getenv("INSIGHT_ENGINE_API_KEY")
        base_url = settings.INSIGHT_ENGINE_BASE_URL or os.getenv("INSIGHT_ENGINE_BASE_URL")
        model_name = settings.INSIGHT_ENGINE_MODEL_NAME or os.getenv("INSIGHT_ENGINE_MODEL_NAME", "gpt-4")
        
        if not api_key:
            raise ValueError("INSIGHT_ENGINE_API_KEY is not configured")
        
        self.client = LLMClient(api_key=api_key, model_name=model_name, base_url=base_url)
    
    def chat(self, prompt: str) -> str:
        """Simple chat interface"""
        return self.client.invoke(system_prompt="You are a helpful assistant.", user_prompt=prompt)

class DailyDigest:
    def __init__(self):
        self.llm = SimpleLLM()

    async def get_recent_posts(self, keyword: str, hours: int = 24):
        """
        Fetch posts for the given keyword from the last N hours.
        """
        try:
            # Calculate time threshold (milliseconds timestamp)
            time_threshold = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
            
            async with get_session() as session:
                if not session:
                    logger.error("Failed to get database session")
                    return []

                # Query WeiboNote (which stores Reddit data)
                # Filter by source_keyword and add_ts (crawled time) or create_time (post time)
                # Using add_ts is safer for "recently crawled"
                stmt = select(WeiboNote).where(
                    and_(
                        WeiboNote.source_keyword == keyword,
                        WeiboNote.add_ts >= time_threshold
                    )
                ).order_by(WeiboNote.add_ts.desc())
                
                result = await session.execute(stmt)
                posts = result.scalars().all()
                
                logger.info(f"Found {len(posts)} posts for keyword '{keyword}' in the last {hours} hours")
                return posts
        except Exception as e:
            logger.exception(f"Error fetching posts: {e}")
            return []

    def format_posts_for_llm(self, posts):
        """
        Format posts into a text string for the LLM.
        """
        if not posts:
            return "No posts found."
            
        formatted_text = ""
        for i, post in enumerate(posts[:50]): # Limit to 50 posts to avoid token limits
            # Reddit data mapping: 
            # content -> Title + Selftext
            # nickname -> Author
            # liked_count -> Score
            # comments_count -> Num Comments
            
            formatted_text += f"Post {i+1}:\n"
            formatted_text += f"Content: {post.content}\n"
            formatted_text += f"Author: {post.nickname}\n"
            formatted_text += f"Score: {post.liked_count}, Comments: {post.comments_count}\n"
            formatted_text += "-" * 20 + "\n"
            
        return formatted_text

    async def generate_digest(self, keyword: str, hours: int = 24):
        """
        Generate the daily digest for the keyword.
        """
        # 1. Fetch posts
        posts = await self.get_recent_posts(keyword, hours)
        
        if not posts:
            return {
                "success": False,
                "message": f"No posts found for keyword '{keyword}' in the last {hours} hours. Please run the crawler first."
            }
            
        # 2. Format for LLM
        posts_text = self.format_posts_for_llm(posts)
        
        # 3. Construct Prompt
        prompt = DAILY_DIGEST_PROMPT.format(keyword=keyword, hours=hours, posts_text=posts_text)
        
        # 4. Call LLM
        try:
            logger.info(f"Generating summary for '{keyword}'...")
            logger.info(f"Prompt length: {len(prompt)} characters")
            
            import time
            start_time = time.time()
            response_text = self.llm.chat(prompt)
            end_time = time.time()
            logger.info(f"LLM call took {end_time - start_time:.2f} seconds")
            
            # Parse JSON from the end
            import json
            import re
            
            summary = response_text
            cover_card_data = {}
            
            try:
                # Find the last JSON object
                # We look for the last '{' which likely starts the JSON
                last_brace_idx = response_text.rfind('{')
                if last_brace_idx != -1:
                    json_text = response_text[last_brace_idx:]
                    # Remove any trailing markdown code block markers
                    json_text = re.sub(r'```\s*$', '', json_text).strip()
                    
                    cover_card_data = json.loads(json_text)
                    summary = response_text[:last_brace_idx].strip()
            except Exception as e:
                logger.warning(f"Failed to parse cover card JSON: {e}")

            return {
                "success": True,
                "summary": summary,
                "cover_card": cover_card_data,
                "post_count": len(posts),
                "top_posts": [
                    {
                        "content": p.content[:100] + "...", 
                        "score": p.liked_count, 
                        "comments": p.comments_count,
                        "url": p.note_url
                    } 
                    for p in sorted(posts, key=lambda x: int(x.liked_count or 0), reverse=True)[:5]
                ]
            }
        except Exception as e:
            logger.exception(f"Error generating summary: {e}")
            return {
                "success": False,
                "message": f"Error generating summary: {str(e)}"
            }

# Helper function for synchronous execution (e.g. from Streamlit)
def run_digest_generation(keyword: str, hours: int = 24):
    # Clear engine cache to avoid "attached to a different loop" error
    # because asyncio.run creates a new loop each time
    clear_engine_cache()
    digest = DailyDigest()
    return asyncio.run(digest.generate_digest(keyword, hours))

if __name__ == "__main__":
    # Test run
    if len(sys.argv) > 1:
        kw = sys.argv[1]
        print(run_digest_generation(kw))
    else:
        print("Please provide a keyword")
