
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Also add the MediaCrawler root (where base/ is located)
# Since the crawler code assumes base is importable directly
media_crawler_root = project_root / "MindSpider" / "DeepSentimentCrawling" / "MediaCrawler"
sys.path.append(str(media_crawler_root))

from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit.client import RedditClient

async def test_curl_cffi():
    print("🚀 Testing RedditClient with curl_cffi...")
    
    client = RedditClient()
    
    # Test simple search
    keyword = "test"
    print(f"📡 Searching for '{keyword}'...")
    
    try:
        result = await client.search(keyword, limit=2)
        
        if result and 'data' in result:
            posts = result['data']['children']
            print(f"✅ Success! Found {len(posts)} posts.")
            if posts:
                print(f"   First post title: {posts[0]['data'].get('title')}")
        else:
            print("⚠️ Request succeeded but no data found.")
            
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_curl_cffi())
