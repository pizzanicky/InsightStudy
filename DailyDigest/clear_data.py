
import sys
from pathlib import Path
import asyncio
from sqlalchemy import text

# Add paths
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

media_crawler_root = project_root / "MindSpider" / "DeepSentimentCrawling" / "MediaCrawler"
sys.path.append(str(media_crawler_root))

# Import Digest Session
try:
    from DailyDigest.models import get_db_session as get_digest_session
except ImportError as e:
    print(f"Error importing DailyDigest models: {e}")
    exit(1)

# Import Crawler Session
# Note: Crawler uses async session
try:
    from MindSpider.DeepSentimentCrawling.MediaCrawler.database.db_session import get_session as get_crawler_session
except ImportError as e:
    print(f"Error importing Crawler session: {e}")
    exit(1)

def clear_digest_history():
    print("Clearing Digest History...")
    session = get_digest_session()
    try:
        # Check if table exists first to avoid error if it's empty/missing (though model should create it)
        session.execute(text("TRUNCATE TABLE digest_history RESTART IDENTITY CASCADE;"))
        session.commit()
        print("✅ Digest History cleared.")
    except Exception as e:
        # If table doesn't exist, it might throw an error, which is fine-ish
        print(f"❌ Failed to clear Digest History (or table empty): {e}")
        session.rollback()
    finally:
        session.close()

async def clear_crawler_data():
    print("Clearing Crawler Data (WeiboNote)...")
    try:
        async with get_crawler_session() as session:
            # Note: WeiboNote table is 'weibo_note'
            await session.execute(text("TRUNCATE TABLE weibo_note RESTART IDENTITY CASCADE;"))
            await session.commit()
            print("✅ Crawler Data (WeiboNote) cleared.")
    except Exception as e:
        print(f"❌ Failed to clear Crawler Data: {e}")

if __name__ == "__main__":
    clear_digest_history()
    asyncio.run(clear_crawler_data())
