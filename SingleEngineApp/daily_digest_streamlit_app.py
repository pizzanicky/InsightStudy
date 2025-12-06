import streamlit as st
import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from DailyDigest.core import run_digest_generation, run_crawl

st.set_page_config(page_title="Daily Digest", page_icon="📰", layout="wide")

st.title("📰 Daily Sentiment Digest")
st.markdown("一键爬取Reddit数据并生成情绪摘要分析")

# 渲染结果函数
def render_digest_result(result, keyword):
    """渲染摘要结果，包括卡片、摘要和热门讨论"""
    st.success(f"✅ 基于 {result['post_count']} 条帖子生成摘要")
    
    # Display Cover Card if available
    if result.get("cover_card"):
        card = result["cover_card"]
        
        # Determine color based on sentiment score
        score = float(card.get('sentiment_score', 5))
        if score >= 6:
            badge_color = "#10b981"  # Green
            badge_bg = "rgba(16, 185, 129, 0.2)"
        elif score <= 4:
            badge_color = "#ef4444"  # Red
            badge_bg = "rgba(239, 68, 68, 0.2)"
        else:
            badge_color = "#f59e0b"  # Amber
            badge_bg = "rgba(245, 158, 11, 0.2)"
            
        # Format date
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Generate HTML for the card
        html_card = f"""
        <style>
            .cover-card-container {{
                display: flex;
                justify-content: center;
                margin-bottom: 30px;
            }}
            .cover-card {{
                width: 375px;
                height: 500px;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                border-radius: 20px;
                padding: 60px 32px 32px 32px;
                color: white;
                font-family: 'Inter', system-ui, sans-serif;
                box-shadow: 0 20px 50px rgba(0,0,0,0.5);
                border: 1px solid rgba(255, 255, 255, 0.08);
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                position: relative;
                overflow: hidden;
            }}
            .cover-card::before {{
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                border-radius: 20px;
                padding: 1px;
                background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.02) 100%);
                -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
                -webkit-mask-composite: xor;
                mask-composite: exclude;
                pointer-events: none;
            }}
            .cover-card::after {{
                content: "";
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(circle, rgba(255,255,255,0.03) 0%, rgba(0,0,0,0) 70%);
                pointer-events: none;
            }}
            .card-header {{
                text-align: center;
                margin-bottom: 40px;
                z-index: 1;
            }}
            .ticker {{
                font-size: 48px;
                font-weight: 900;
                letter-spacing: 2px;
                line-height: 1;
                margin-bottom: 12px;
                color: #ffffff;
            }}
            .date {{
                font-size: 13px;
                color: #94a3b8;
                opacity: 0.6;
                font-weight: 400;
                letter-spacing: 1px;
            }}
            .card-body {{
                text-align: center;
                flex-grow: 1;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                z-index: 1;
            }}
            .sentiment-badge {{
                display: inline-block;
                padding: 10px 24px;
                border-radius: 30px;
                font-size: 18px;
                font-weight: 700;
                color: {badge_color};
                background-color: {badge_bg};
                margin-bottom: 28px;
                border: 2px solid {badge_color};
                letter-spacing: 2px;
            }}
            .headline {{
                font-size: 24px;
                font-weight: 700;
                line-height: 1.4;
                color: #f8fafc;
                max-width: 100%;
                text-wrap: balance;
                margin-bottom: 16px;
            }}
            .card-footer {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: center;
                margin-bottom: 24px;
                z-index: 1;
            }}
            .factor-tag {{
                background-color: rgba(30, 41, 59, 0.8);
                color: #e2e8f0;
                padding: 6px 14px;
                border-radius: 12px;
                font-size: 12px;
                border: 1px solid #475569;
                font-weight: 500;
            }}
            .brand-footer {{
                text-align: center;
                font-size: 10px;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 3px;
                border-top: 1px solid rgba(255, 255, 255, 0.05);
                padding-top: 20px;
                z-index: 1;
            }}
        </style>
        <div class="cover-card-container">
            <div class="cover-card">
                <div class="card-header">
                    <div class="ticker">{card.get('ticker', keyword)}</div>
                    <div class="date">{date_str}</div>
                </div>
                <div class="card-body">
                    <div class="sentiment-badge">{card.get('sentiment_label', 'N/A')}</div>
                    <div class="headline">{card.get('headline', 'Market Insight')}</div>
                </div>
                <div class="card-footer">
                    {''.join([f'<span class="factor-tag">{f}</span>' for f in card.get('key_factors', [])])}
                </div>
                <div class="brand-footer">
                    WGD Insight | Sentiment Data
                </div>
            </div>
        </div>
        """
        st.markdown(html_card, unsafe_allow_html=True)
    
    # Layout: Summary on left, Top Posts on right
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📝 Summary")
        st.markdown(result["summary"])
        
        # Add copyable code block
        with st.expander("Copy Full Analysis"):
            st.code(result["summary"], language="markdown")
        
    with col2:
        st.markdown("### 🔥 热门讨论")
        for post in result["top_posts"]:
            with st.expander(f"热度: {post['score']} | 💬 {post['comments']}"):
                st.write(post['content'])
                if post.get('url'):
                    st.markdown(f"[View on Reddit]({post['url']})")

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
    
    st.divider()
    
    # 爬取选项
    st.subheader("🕷️ 爬取选项")
    auto_crawl = st.checkbox("自动爬取数据", value=True, help="勾选后会在生成摘要前自动爬取最新数据")
    max_posts = st.slider("最大爬取帖子数", min_value=50, max_value=200, value=100, step=50)
    
    st.divider()
    
    generate_btn = st.button("🚀 生成 Digest", type="primary", use_container_width=True)

if generate_btn or (auto_run and keyword):
    if not keyword:
        st.error("请输入关键词")
    else:
        if auto_crawl:
            # 分开调用爬取和生成，实现同步进度显示
            with st.status("🔄 正在处理...", expanded=True) as status:
                # 步骤1: 爬取数据
                st.write("📡 步骤 1/2: 爬取Reddit数据...")
                
                try:
                    # 调用爬取函数
                    crawl_success, crawl_message, post_count = run_crawl(keyword, max_posts)
                    
                    # 显示爬取结果
                    if crawl_success:
                        st.write(f"✅ {crawl_message}")
                        
                        # 步骤2: 生成摘要
                        st.write(f"📊 步骤 2/2: 生成情绪摘要...")
                        
                        # 调用生成函数
                        digest_result = run_digest_generation(keyword, hours)
                        
                        # 检查摘要生成结果
                        if digest_result["success"]:
                            status.update(label="✅ 处理完成！", state="complete", expanded=False)
                            result = digest_result
                        else:
                            status.update(label="⚠️ 摘要生成失败", state="error")
                            st.error(digest_result["message"])
                            result = None
                    else:
                        status.update(label="❌ 爬取失败", state="error")
                        st.error(crawl_message)
                        result = None
                        
                except Exception as e:
                    status.update(label="❌ 处理失败", state="error")
                    st.error(f"发生错误: {str(e)}")
                    result = None
            
            # 显示结果
            if result and result["success"]:
                render_digest_result(result, keyword)
        else:
            # 仅生成摘要（使用已有数据）
            with st.spinner(f"正在分析 '{keyword}' 的情绪..."):
                try:
                    result = run_digest_generation(keyword, hours)
                    
                    if result["success"]:
                        render_digest_result(result, keyword)
                        
                    else:
                        st.warning(result["message"])
                        if "No posts found" in result["message"]:
                            st.info("提示: 请先勾选'自动爬取数据'或手动运行爬虫获取数据")
                            
                except Exception as e:
                    st.error(f"发生错误: {str(e)}")

else:
    st.info("👈 在侧边栏输入关键词并点击'生成 Digest'开始")
