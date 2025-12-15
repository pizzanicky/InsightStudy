import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

# Add MediaCrawler to sys.path
media_crawler_root = project_root / "MindSpider" / "DeepSentimentCrawling" / "MediaCrawler"
sys.path.append(str(media_crawler_root))

from media_platform.hackernews.client import HackerNewsClient

async def test_hn():
    client = HackerNewsClient()
    keyword = "TSLA"
    
    print(f"Searching HN for: {keyword}")
    data = await client.search_stories(keyword, hits_per_page=5)
    
    if data:
        print(f"Success! Found {len(data.get('hits', []))} hits.")
        for hit in data.get('hits', []):
            print(f"- [{hit.get('created_at')}] {hit.get('title')} (Points: {hit.get('points')})")
            print(f"  URL: {hit.get('url')}")
    else:
        print("Failed to fetch data or no results.")

if __name__ == "__main__":
    asyncio.run(test_hn())
