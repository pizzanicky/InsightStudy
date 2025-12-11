
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Also add the MediaCrawler root
media_crawler_root = project_root / "MindSpider" / "DeepSentimentCrawling" / "MediaCrawler"
sys.path.append(str(media_crawler_root))

from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.stocktwits.client import StocktwitsClient

async def test_stocktwits():
    print("🚀 Testing StocktwitsClient...")
    
    client = StocktwitsClient()
    symbol = "AAPL" # Use a popular symbol
    
    print(f"📡 Fetching stream for ${symbol}...")
    
    try:
        data = await client.get_symbol_stream(symbol)
        
        messages = data.get('messages', [])
        print(f"✅ Found {len(messages)} messages.")
        
        if messages:
            msg = messages[0]
            print("\n📝 First Message:")
            print(f"User: {msg['user']['username']}")
            print(f"Body: {msg['body']}")
            
            entities = msg.get('entities', {}) or {}
            sentiment = entities.get('sentiment', {})
            if sentiment:
                 print(f"Sentiment: {sentiment.get('basic')}")
            else:
                 print("Sentiment: None")
                 
            print(f"Created At: {msg['created_at']}")
            
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_stocktwits())
