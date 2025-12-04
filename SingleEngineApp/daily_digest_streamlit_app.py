import streamlit as st
import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from DailyDigest.core import run_digest_generation

st.set_page_config(page_title="Daily Digest", page_icon="📰", layout="wide")

st.title("📰 Daily Sentiment Digest")
st.markdown("Generate a lightweight summary of Reddit sentiment for the last 24 hours.")

# Sidebar configuration
with st.sidebar:
    st.header("Configuration")
    
    # Check for query params (compatible with both old and new Streamlit versions)
    try:
        # Try new API (Streamlit >= 1.18.0)
        query_params = st.query_params
        default_keyword = query_params.get("query", "")
        auto_run = query_params.get("auto_search", "false").lower() == "true"
    except AttributeError:
        # Fallback to old API (Streamlit < 1.18.0)
        query_params = st.experimental_get_query_params()
        default_keyword = query_params.get("query", [""])[0]
        auto_run = query_params.get("auto_search", ["false"])[0].lower() == "true"
    
    keyword = st.text_input("Keyword", value=default_keyword, placeholder="e.g., IONQ, TSLA")
    hours = st.slider("Time Window (Hours)", min_value=1, max_value=72, value=24)
    
    generate_btn = st.button("Generate Digest", type="primary")

if generate_btn or (auto_run and keyword):
    if not keyword:
        st.error("Please enter a keyword.")
    else:
        with st.spinner(f"Analyzing sentiment for '{keyword}'..."):
            try:
                result = run_digest_generation(keyword, hours)
                
                if result["success"]:
                    st.success(f"Digest generated based on {result['post_count']} posts.")
                    
                    # Layout: Summary on left, Top Posts on right
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown("### 📝 Summary")
                        st.markdown(result["summary"])
                        
                    with col2:
                        st.markdown("### 🔥 Top Posts")
                        for post in result["top_posts"]:
                            with st.expander(f"Score: {post['score']} | 💬 {post['comments']}"):
                                st.write(post['content'])
                                if post.get('url'):
                                    st.markdown(f"[View on Reddit]({post['url']})")
                else:
                    st.warning(result["message"])
                    if "No posts found" in result["message"]:
                        st.info("Tip: Run the crawler first to fetch data.")
                        
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

else:
    st.info("Enter a keyword in the sidebar and click 'Generate Digest' to start.")
