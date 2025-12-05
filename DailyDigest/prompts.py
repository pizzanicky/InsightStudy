"""
Daily Digest Prompts
"""

DAILY_DIGEST_PROMPT = """
你是一位专业的社交媒体舆情分析师。你的任务是基于提供的关于关键词 "{keyword}" 的 Reddit 帖子生成"每日舆情摘要"。

这些帖子来自过去 {hours} 小时。

请分析以下帖子并以 Markdown 格式提供摘要。

**输入数据：**
{posts_text}

**输出要求：**

1.  **整体情绪**：（看涨/看跌/中性）并简要说明原因（1-2 句话）。
2.  **关键话题**：列出 3-5 个主要讨论的话题或主题。
3.  **总结**：简明扼要地总结整体讨论，突出任何重大新闻、传闻或社区反应。
4.  **热门帖子亮点**：简要提及 1-2 个最重要的帖子（如果有）。

**格式：**

## 📊 每日情绪：[情绪]

**关键话题：**
*   话题 1
*   话题 2
*   ...

**总结：**
[你的总结内容]

**亮点：**
*   [亮点 1]
*   [亮点 2]

**注意：请用中文回复所有内容。**

Finally, output a JSON object (and ONLY the JSON) at the very end of your response for the cover card, with these fields:

*   `ticker`: The stock symbol (e.g., IONQ).
*   `sentiment_score`: A number 0-10 (0 bearish, 10 bullish).
*   `sentiment_label`: A 2-character Chinese word (e.g., 极热, 看涨, 观望, 分歧, 恐慌).
*   `headline`: A professional, insight-driven headline (Max 15 chars, e.g., '量子算力变现能力的验证期').
*   `key_factors`: A list of 3 short phrases (Max 6 chars each) driving this sentiment (e.g., ["财报超预期", "空头回补", "AI叙事"]).

Ensure the JSON is valid and appears at the very end of the response.
"""
