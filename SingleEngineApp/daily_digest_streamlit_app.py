import streamlit as st
import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from DailyDigest.core import run_digest_generation, run_crawl
from DailyDigest.email_service import send_report_email

st.set_page_config(page_title="Daily Digest", page_icon="📰", layout="wide")

st.title("📰 Daily Sentiment Digest")
st.markdown("一键爬取Reddit、Stocktwits数据并生成情绪摘要分析")

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
        # Use date from result if available, otherwise STRICTLY require it (no fallback to now for history correctness)
        raw_date_str = str(result.get('date') or "Unknown Date")
        date_str = raw_date_str.split(" ")[0]
        
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
                min-height: 520px;
                background: linear-gradient(145deg, #1e293b, #0f172a);
                border-radius: 20px;
                padding: 35px 25px 50px 25px;
                color: white;
                font-family: 'Inter', system-ui, sans-serif;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
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
            .card-header {{
                text-align: center;
                margin-bottom: 30px;
                z-index: 1;
            }}
            .ticker {{
                font-size: 42px;
                font-weight: 900;
                letter-spacing: 2px;
                line-height: 1;
                margin-bottom: 8px;
                color: #ffffff;
            }}
            .date {{
                font-size: 12px;
                color: #94a3b8;
                opacity: 0.7;
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
                padding: 8px 20px;
                border-radius: 30px;
                font-size: 16px;
                font-weight: 700;
                color: {badge_color};
                background-color: {badge_bg};
                margin-bottom: 8px;
                border: 2px solid {badge_color};
                letter-spacing: 1px;
            }}
            .sentiment-badge-en {{
                font-size: 12px;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 2px;
                margin-bottom: 15px;
                font-weight: 600;
            }}
            .score-display {{
                font-size: 14px;
                font-weight: 600;
                color: #e2e8f0;
                margin-bottom: 20px;
                letter-spacing: 1px;
            }}
            .headline {{
                font-size: 22px;
                font-weight: 700;
                line-height: 1.3;
                color: #f8fafc;
                margin-bottom: 8px;
            }}
            .headline-en {{
                font-size: 14px;
                font-weight: 400;
                line-height: 1.4;
                color: #94a3b8;
                margin-bottom: 25px;
                font-style: italic;
            }}
            .card-footer {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                justify-content: center;
                margin-bottom: 20px;
                z-index: 1;
            }}
            .factor-tag {{
                background-color: rgba(30, 41, 59, 0.8);
                color: #e2e8f0;
                padding: 5px 12px;
                border-radius: 10px;
                font-size: 11px;
                border: 1px solid #475569;
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .factor-en {{
                font-size: 9px;
                color: #94a3b8;
                margin-top: 2px;
            }}
            .brand-footer {{
                text-align: center;
                font-size: 9px;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 3px;
                border-top: 1px solid rgba(255, 255, 255, 0.05);
                padding-top: 15px;
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
                    <div class="sentiment-badge-en">{card.get('sentiment_label_en', '')}</div>
                    <div class="score-display">{score:.1f}/10</div>
                    <div class="headline">{card.get('headline', 'Market Insight')}</div>
                    <div class="headline-en">{card.get('headline_en', '')}</div>
                </div>
                <div class="card-footer">
                    {''.join([f'<div class="factor-tag"><span>{f}</span><span class="factor-en">{en}</span></div>' 
                              for f, en in zip(card.get('key_factors', []), card.get('key_factors_en', ['']*3))])}
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
        
        # 添加免责声明
        st.markdown("---")
        st.markdown(
            "<p style='text-align: center; font-size: 12px; color: #94a3b8; opacity: 0.8; margin: 10px 0;'>"
            "基于网络公开信息汇总，不构成任何投资建议"
            "</p>",
            unsafe_allow_html=True
        )
        
        # Add copyable code block
        with st.expander("Copy Full Analysis"):
            # 在复制的文本中也包含免责声明
            full_text = result["summary"] + "\n\n---\n\n基于网络公开信息汇总，不构成任何投资建议"
            st.code(full_text, language="markdown")
        
    with col2:
        st.markdown("### 🔥 热门讨论")
        for post in result["top_posts"]:
            with st.expander(f"热度: {post['score']} | 💬 {post['comments']}"):
                st.write(post['content'])

    
    # --- Email Report Section ---
    st.divider()
    st.subheader("📧 Send Report via Email")
    
    # --- Address Book Logic ---
    import json
    from pathlib import Path
    
    RECIPIENTS_FILE = Path("SingleEngineApp/recipients.json")
    if not RECIPIENTS_FILE.exists():
        RECIPIENTS_FILE = Path("recipients.json") # Fallback relative path
        
    def load_recipients():
        if RECIPIENTS_FILE.exists():
            try:
                with open(RECIPIENTS_FILE, "r") as f:
                    return json.load(f)
            except:
                return []
        return []

    recipients_list = load_recipients()
    
    with st.expander("Email this report", expanded=True):
        email_col1, email_col2 = st.columns([3, 1])
        with email_col1:
            if recipients_list:
                selected_recipient = st.selectbox("Select Recipient", options=recipients_list)
            else:
                st.warning("No recipients found in recipients.json")
                selected_recipient = None
                
        with email_col2:
            st.write("") # Spacer
            st.write("") # Spacer
            send_email_btn = st.button("Send Email", type="primary", use_container_width=True, disabled=not recipients_list)
            
        if send_email_btn and selected_recipient:
            with st.spinner(f"Sending email to {selected_recipient}..."):
                # Prepare data
                # Ensure date_str is only date, no time
                raw_date = str(result.get("date", "Unknown Date"))
                date_str = raw_date.split(" ")[0]
                subject = f"WGD Daily Digest: {result.get('cover_card', {}).get('ticker', keyword)} {date_str}"
                
                # Call backend
                success_result = send_report_email(
                    to_email=selected_recipient,
                    subject=subject,
                    summary_md=result["summary"],
                    cover_card=result.get("cover_card"),
                    ticker=keyword,
                    date_str=date_str
                )
                
                if success_result["success"]:
                    st.success(f"✅ Email sent successfully to {selected_recipient}!")
                else:
                    st.error(f"❌ {success_result['message']}")

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

    # 历史记录
    st.markdown("---")
    st.subheader("📚 历史记录")
    
    # 刷新历史列表按钮
    if st.button("🔄 刷新列表", use_container_width=True):
        st.rerun()
    
    # 获取历史记录列表
    try:
        from DailyDigest.models import get_digest_history_list
        history_list = get_digest_history_list(limit=20)
        
        if history_list:
            # 使用选择框显示历史
            history_options = [
                f"{h['created_at']} - {h['keyword']} ({h['sentiment_label']}, {h['post_count']}条)"
                for h in history_list
            ]
            
            selected_index = st.selectbox(
                "选择历史记录",
                range(len(history_options)),
                format_func=lambda i: history_options[i],
                key="history_selector"
            )
            
            if st.button("📖 查看此记录", use_container_width=True):
                st.session_state.view_history_id = history_list[selected_index]['id']
                st.rerun()
        else:
            st.info("暂无历史记录")
    except Exception as e:
        st.error(f"加载历史记录失败: {e}")



# 检查是否要查看历史记录
if 'view_history_id' in st.session_state and st.session_state.view_history_id:
    try:
        from DailyDigest.models import get_digest_by_id
        history_data = get_digest_by_id(st.session_state.view_history_id)
        
        if history_data:
            st.info(f"📖 正在查看历史记录 - {history_data['keyword']} ({history_data['created_at']})")
            
            # 添加"返回新建"按钮
            if st.button("🔙 返回新建"):
                del st.session_state.view_history_id
                st.rerun()
            
            # 转换为result格式并渲染
            result = {
                'success': True,
                'summary': history_data['summary'],
                'post_count': history_data['post_count'],
                'cover_card': history_data['cover_card'],
                'top_posts': history_data['top_posts'],
                'date': history_data['created_at'] # Pass history date
            }
            render_digest_result(result, history_data['keyword'])
        else:
            st.error("未找到该历史记录")
            del st.session_state.view_history_id
    except Exception as e:
        st.error(f"加载历史记录失败: {e}")
        del st.session_state.view_history_id
# Handle "Generate" Action (State Update)
if generate_btn or (auto_run and keyword):
    if not keyword:
        st.error("请输入关键词")
    else:
        if auto_crawl:
            # 分开调用爬取和生成，实现同步进度显示
            with st.status("🔄 正在处理...", expanded=True) as status:
                # 步骤1: 爬取数据 (Reddit + Stocktwits + Hacker News)
                st.write("📡 步骤 1/2: 正在爬取 Reddit, Stocktwits 和 Hacker News 数据...")
                st.info("💡 过程: Reddit Crawl -> Stocktwits Crawl -> Hacker News Crawl")
                
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
                            # Store in session state
                            st.session_state['current_result'] = digest_result
                            st.session_state['current_keyword'] = keyword
                        else:
                            status.update(label="⚠️ 摘要生成失败", state="error")
                            st.error(digest_result["message"])
                    else:
                        status.update(label="❌ 爬取失败", state="error")
                        st.error(crawl_message)
                        
                except Exception as e:
                    status.update(label="❌ 处理失败", state="error")
                    st.error(f"发生错误: {str(e)}")
            
        else:
            # 仅生成摘要（使用已有数据）
            with st.spinner(f"正在分析 '{keyword}' 的情绪..."):
                try:
                    result = run_digest_generation(keyword, hours)
                    
                    if result["success"]:
                        # Store in session state
                        st.session_state['current_result'] = result
                        st.session_state['current_keyword'] = keyword
                    else:
                        st.warning(result["message"])
                        if "No posts found" in result["message"]:
                            st.info("提示: 请先勾选'自动爬取数据'或手动运行爬虫获取数据")
                            
                except Exception as e:
                    st.error(f"发生错误: {str(e)}")

# Remove view_history logic here because it's handled above or we check state priority
# Render Logic: Decide what to show
# Priority: 1. Viewing History ID, 2. Current Generated Result, 3. Default Info

if 'view_history_id' in st.session_state and st.session_state.view_history_id:
    # Logic for history view is already handled in the previous block (lines 355-383)
    # But wait, looking at the code structure, the previous block was `if ... elif ... else`.
    # We need to ensure we don't double render.
    # The simplest way is to let the 'view_history_id' block handle itself (it halts execution or renders).
    # IF 'view_history_id' is NOT present, THEN we check for 'current_result'.
    pass 

elif 'current_result' in st.session_state:
    render_digest_result(st.session_state['current_result'], st.session_state['current_keyword'])

else:
    st.info("👈 在侧边栏输入关键词并点击'生成 Digest'开始")
