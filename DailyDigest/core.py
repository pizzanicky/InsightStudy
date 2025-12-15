import sys
import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select, and_
from loguru import logger

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

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

# Import Google Gemini SDK
import google.generativeai as genai

class SimpleLLM:
    """Simple wrapper around Google Gemini API"""
    def __init__(self):
        # Load Google Gemini config from environment
        api_key = os.getenv("GOOGLE_API_KEY")
        model_name = os.getenv("GOOGLE_MODEL_NAME", "gemini-2.0-flash-exp")
        
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not configured in .env file")
        
        # Configure Google Gemini
        genai.configure(api_key=api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
        
        logger.info(f"[SimpleLLM] Initialized Google Gemini: {model_name}")
    
    def chat(self, prompt: str) -> str:
        """Simple chat interface using Google Gemini"""
        try:
            logger.info(f"[SimpleLLM] Sending request to {self.model_name}")
            
            # Generate content using Gemini
            response = self.model.generate_content(prompt)
            
            # Extract text from response
            if response and response.text:
                logger.info(f"[SimpleLLM] Received response ({len(response.text)} chars)")
                return response.text
            else:
                logger.error("[SimpleLLM] Empty response from Gemini")
                raise ValueError("Empty response from Gemini API")
                
        except Exception as e:
            logger.error(f"[SimpleLLM] Error calling Gemini API: {e}")
            raise

class DailyDigest:
    def __init__(self):
        self.llm = SimpleLLM()
    
    async def _run_media_crawler_subprocess(self, platform: str, keyword: str, max_count: int):
        """
        Helper to run the MediaCrawler subprocess with config patching
        """
        import subprocess
        import shutil
        import re
        
        # Paths
        temp_config_path = media_crawler_root / "config" / "base_config_temp.py"
        original_config_path = media_crawler_root / "config" / "base_config.py"
        backup_path = media_crawler_root / "config" / "base_config_backup.py"

        try:
            # 1. Update Config
            # Backup
            shutil.copy(original_config_path, backup_path)
            
            # Read & Modify
            with open(original_config_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            modified_content = original_content
            # Note: We only replace KEYWORDS and MAX_NOTES_COUNT. Platform is passed via CLI.
            # But the Crawler reads config.KEYWORDS.
            modified_content = re.sub(r'KEYWORDS = .*', f'KEYWORDS = "{keyword}"', modified_content)
            modified_content = re.sub(r'CRAWLER_MAX_NOTES_COUNT = .*', f'CRAWLER_MAX_NOTES_COUNT = {max_count}', modified_content)
            
            with open(original_config_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            # 2. Run Subprocess
            cmd = [
                'python3',
                str(media_crawler_root / 'main.py'),
                '--platform', platform,
                '--lt', 'qrcode',
                '--type', 'search',
                '--save_data_option', 'postgresql'
            ]
            
            logger.info(f"[DailyDigest] Running {platform} crawler: {' '.join(cmd)}")
            
            res = subprocess.run(
                cmd,
                cwd=str(media_crawler_root),
                capture_output=True,
                text=True,
                timeout=120 if platform == 'reddit' else 60
            )

            # 3. Restore Config
            shutil.move(backup_path, original_config_path)
            
            # 4. Log Output
            tag = platform.upper()
            logger.info(f"[DailyDigest] --- {tag} STDOUT ---\n{res.stdout or ''}")
            if res.stderr:
                logger.warning(f"[DailyDigest] --- {tag} STDERR ---\n{res.stderr}")

            return res

        except Exception as e:
            logger.error(f"[DailyDigest] Error in _run_media_crawler_subprocess for {platform}: {e}")
            # Ensure config restore if error
            if backup_path.exists():
                 try:
                     shutil.move(backup_path, original_config_path)
                 except:
                     pass
            raise e

    async def crawl_reddit(self, keyword: str, max_count: int = 100):
        """
        专门负责 Reddit 爬取及 Fallback 逻辑
        """
        try:
            res = await self._run_media_crawler_subprocess('reddit', keyword, max_count)
            
            # Check 403 / Block
            combined_output = (res.stdout or "") + (res.stderr or "")
            crawler_blocked = False
            if "403" in combined_output and ("Block" in combined_output or "whoa there" in combined_output or "Reddit" in combined_output):
                logger.error("[DailyDigest] Reddit Crawler detected 403 Forbidden/Blocked.")
                crawler_blocked = True

            # Check Database for results
            posts = await self.get_recent_posts(keyword, hours=24) # Simply check total count? Or filter by platform?
            # Ideally filter by platform='reddit', but get_recent_posts just filters by keyword. 
            # It's an approximation.
            post_count = len(posts) # This counts both reddit and stocktwits if already ran, but here we assume sequential
            
            # Fallback Logic (Reddit Specific)
            # Only if NO posts found AND (Blocked or Error)
            if post_count == 0 and (crawler_blocked or res.returncode != 0):
                logger.warning(f"[DailyDigest] Reddit crawler failed/blocked. Attempting Tavily fallback...")
                success, msg, count = await self.crawl_reddit_via_tavily(keyword, max_count)
                return success, msg, count
            
            return True, "Reddit Crawl Finished", post_count
            
        except Exception as e:
            logger.error(f"[DailyDigest] crawl_reddit exception: {e}")
            return False, str(e), 0

    async def crawl_stocktwits(self, keyword: str, max_count: int = 100):
        """
        专门负责 Stocktwits 爬取
        """
        try:
            res = await self._run_media_crawler_subprocess('stocktwits', keyword, max_count)
            return True, "Stocktwits Crawl Finished", 0 # Count check omitted for simplicity or can add later
        except Exception as e:
            logger.error(f"[DailyDigest] crawl_stocktwits exception: {e}")
            return False, str(e), 0

    async def run_crawlers(self, keyword: str, max_count: int = 100):
        """
        Orchestrator: Run Reddit then Stocktwits
        """
        logger.info(f"[DailyDigest] Starting Multi-Platform Crawl for: {keyword}")
        
        # 1. Reddit
        r_success, r_msg, r_count = await self.crawl_reddit(keyword, max_count)
        
        # 2. Stocktwits (Sequential)
        # No wait needed per user request
        s_success, s_msg, s_count = await self.crawl_stocktwits(keyword, max_count)
        
        total_msg = f"Reddit: {r_msg} | Stocktwits: {s_msg}"
        return (r_success or s_success), total_msg, (r_count + s_count)

    async def crawl_reddit_via_tavily(self, keyword: str, max_results: int = 20):
        """
        Fallback: Use Tavily API to search Reddit when crawler is blocked.
        """
        try:
            from tavily import TavilyClient
            api_key = os.getenv("TAVILY_API_KEY") or settings.TAVILY_API_KEY
            
            if not api_key:
                logger.warning("TAVILY_API_KEY not found, skipping fallback.")
                return False, "未配置 Tavily API Key", 0
                
            client = TavilyClient(api_key=api_key)
            
            response = client.search(
                query=f'site:reddit.com "{keyword}"',
                search_depth="advanced",
                max_results=max_results,
                include_raw_content=False,
                days=3 # RESTRICT to last 3 days to avoid old posts.
            )
            
            results = response.get('results', [])
            if not results:
                logger.warning("Tavily returned no results.")
                return False, "Tavily 未找到结果", 0
            
            logger.info(f"[DailyDigest] Tavily found {len(results)} results (Last 3 days). Saving to DB...")
            
            saved_count = 0
            async with get_session() as session:
                for item in results:
                    # 创建伪造的 WeiboNote (Reddit Post)
                    url = item.get('url', '')
                    content = item.get('content', '')
                    title = item.get('title', '')
                    
                    # 简单的去重/ID生成逻辑
                    import hashlib
                    note_id_hash = int(hashlib.md5(url.encode()).hexdigest(), 16) % (10**16) # 生成一个大整数ID
                    
                    # 检查是否存在
                    stmt = select(WeiboNote).where(WeiboNote.note_id == note_id_hash)
                    existing = (await session.execute(stmt)).scalar_one_or_none()
                    
                    current_ts = int(datetime.now().timestamp() * 1000)
                    
                    # Try to parse real publish date from Tavily
                    pub_date_str = item.get('published_date')
                    real_create_time = current_ts # Default to NOW because we filtered by `days=3`
                    
                    if pub_date_str:
                        try:
                            dt = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                            real_create_time = int(dt.timestamp() * 1000)
                        except:
                            pass
                    
                    if existing:
                        existing.last_modify_ts = current_ts
                        existing.source_keyword = keyword
                    else:
                        new_note = WeiboNote(
                            note_id=note_id_hash,
                            note_url=url,
                            content=f"{title}\n\n{content}", # 合并标题和摘要
                            source_keyword=keyword,
                            nickname="RedditUser (Via Tavily)",
                            user_id="tavily_search",
                            avatar="",
                            liked_count="0",
                            comments_count="0",
                            shared_count="0",
                            add_ts=current_ts,
                            last_modify_ts=current_ts,
                            create_time=real_create_time, 
                            create_date_time=datetime.fromtimestamp(real_create_time/1000).strftime("%Y-%m-%d %H:%M:%S")
                        )
                        session.add(new_note)
                        saved_count += 1
                
                await session.commit()
            
            return True, "Success", saved_count

        except Exception as e:
            logger.error(f"[DailyDigest] Tavily fallback failed: {e}")
            return False, str(e), 0

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
                # Strict Filtering: Only include posts created within the time window
                # We use create_time (post publish time) instead of add_ts (crawl time) for accuracy
                stmt = select(WeiboNote).where(
                    and_(
                        WeiboNote.source_keyword == keyword,
                        WeiboNote.create_time >= time_threshold
                    )
                ).order_by(WeiboNote.create_time.desc())
                
                result = await session.execute(stmt)
                posts = result.scalars().all()
                
                logger.info(f"Found {len(posts)} posts for keyword '{keyword}' in the last {hours} hours")
                
                # 诊断逻辑：如果没找到帖子，检查是否有数据但关键词不匹配
                if not posts:
                    logger.info("No posts found matching keyword strictly. Running diagnostics...")
                    
                    # 1. 检查最近1小时是否有任何数据插入
                    diag_stmt = select(WeiboNote).order_by(WeiboNote.add_ts.desc()).limit(5)
                    diag_res = await session.execute(diag_stmt)
                    recent_posts = diag_res.scalars().all()
                    
                    if recent_posts:
                        logger.info(f"Diagnostics: Found {len(recent_posts)} recent posts in DB (ignoring keyword):")
                        for p in recent_posts:
                            logger.info(f" - ID: {p.note_id}, Keyword: '{p.source_keyword}', TS: {p.add_ts}, Time: {datetime.fromtimestamp(p.add_ts/1000)}")
                    else:
                        logger.warning("Diagnostics: DB is empty or no recent posts found at all. Crawler might have failed.")
                
                return posts
        except Exception as e:
            logger.exception(f"Error fetching posts: {e}")
            return []

    def format_posts_for_llm(self, posts):
        """
        Format posts into a text string for the LLM.
        保护隐私：不包含用户ID和来源信息
        """
        if not posts:
            return "No posts found."
            
        formatted_text = ""
        for i, post in enumerate(posts[:50]): # 限制到50条帖子避免超过token限制
            # 数据映射: 
            # content -> 标题 + 内容
            # liked_count -> 评分/点赞数
            # comments_count -> 评论数
            # 为保护隐私，不显示作者信息
            
            formatted_text += f"帖子 {i+1}:\n"
            formatted_text += f"链接: {post.note_url}\n"
            formatted_text += f"内容: {post.content}\n"
            formatted_text += f"互动数据: {post.liked_count}赞, {post.comments_count}评论\n"
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
                # Robust extraction: Split by the start of the JSON code block
                if "```json" in response_text:
                    parts = response_text.split("```json")
                    summary = parts[0].strip()
                    json_text = parts[-1].split("```")[0].strip() # Take content between ```json and next ```
                    try:
                        cover_card_data = json.loads(json_text)
                    except:
                         # Fallback if json is malformed, try finding brace
                         match = re.search(r'(\{.*\})', json_text, re.DOTALL)
                         if match:
                             cover_card_data = json.loads(match.group(1))
                else:
                    # Fallback logic if no code block found
                    last_brace_idx = response_text.rfind('{')
                    if last_brace_idx != -1:
                        json_text = response_text[last_brace_idx:]
                        if json_text.strip().endswith("}"):
                             try:
                                 cover_card_data = json.loads(json_text)
                                 summary = response_text[:last_brace_idx].strip()
                             except:
                                 pass
            except Exception as e:
                logger.warning(f"Failed to parse cover card JSON: {e}")

            return {
                "success": True,
                "date": datetime.now().strftime("%Y-%m-%d"),
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

# Helper functions for synchronous execution (e.g. from Streamlit)
def run_crawl(keyword: str, max_count: int = 100):
    """
    同步执行爬取
    返回: (success: bool, message: str, post_count: int)
    """
    clear_engine_cache()
    digest = DailyDigest()
    return asyncio.run(digest.run_crawlers(keyword, max_count))

def run_digest_generation(keyword: str, hours: int = 24):
    """
    同步执行摘要生成
    """
    # Clear engine cache to avoid "attached to a different loop" error
    # because asyncio.run creates a new loop each time
    clear_engine_cache()
    digest = DailyDigest()
    result = asyncio.run(digest.generate_digest(keyword, hours))
    
    # 如果生成成功，保存到历史记录
    if result.get('success'):
        try:
            from DailyDigest.models import save_digest_history
            success, history_id = save_digest_history(keyword, result)
            if success:
                logger.info(f"Saved digest history with ID: {history_id}")
                result['history_id'] = history_id
        except Exception as e:
            logger.warning(f"Failed to save history: {e}")
    
    return result

def run_crawl_and_digest(keyword: str, hours: int = 24, max_count: int = 100):
    """
    一键执行：爬取 + 生成摘要
    返回: {
        "crawl_success": bool,
        "crawl_message": str,
        "post_count": int,
        "digest_result": dict  # 摘要结果
    }
    """
    # Step 1: 爬取
    crawl_success, crawl_message, post_count = run_crawl(keyword, max_count)
    
    if not crawl_success:
        return {
            "crawl_success": False,
            "crawl_message": crawl_message,
            "post_count": 0,
            "digest_result": {
                "success": False,
                "message": "爬取失败，无法生成摘要"
            }
        }
    
    # Step 2: 生成摘要
    digest_result = run_digest_generation(keyword, hours)
    
    return {
        "crawl_success": True,
        "crawl_message": crawl_message,
        "post_count": post_count,
        "digest_result": digest_result
    }

if __name__ == "__main__":
    # Test run
    if len(sys.argv) > 1:
        kw = sys.argv[1]
        print(run_digest_generation(kw))
    else:
        print("Please provide a keyword")
