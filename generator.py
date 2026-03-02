# -*- coding: utf-8 -*-
"""
AI 视频文案生成器
根据数据库中爆款视频的分析结果，生成可直接发布的新文案
"""
import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

GENERATE_PROMPT = """你是一个抖音爆款文案创作专家，专注于【装修/家居/AI设计】赛道。

我分析了最近一批爆款视频，总结出以下规律：

【高频钩子话术】
{top_hooks}

【爆款文案结构】
{top_structures}

【核心高频关键词】
{top_keywords}

【参考爆款原文案（点赞最高的3条）】
{top_descs}

---
请根据以上爆款规律，为我的账号创作 {count} 条全新的视频文案。

要求：
1. 每条文案包含：【标题】（15字以内，即视频封面文字）、【正文】（80-120字，视频字幕/配音文案）、【标签】（5个话题标签）
2. 开头必须有强钩子，让用户停下来看
3. 结合装修/AI设计热点，口语化，适合短视频节奏
4. 每条风格略有不同（揭秘型、对比型、干货型、情感型等）
5. 不能直接抄袭参考文案，要有创新

只输出 JSON 数组，格式如下，不要有其他内容：
[
  {{"title":"...","content":"...","tags":["tag1","tag2","tag3","tag4","tag5"]}},
  ...
]
"""


def _load_analysis_patterns(db_path: Path, limit: int = 20) -> dict:
    """从数据库加载爆款分析结果，提取规律"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        SELECT v.desc, v.digg_count, a.hook, a.structure, a.keywords, a.suggestion
        FROM videos v
        JOIN analysis a ON v.aweme_id = a.aweme_id
        WHERE v.digg_count > 0
        ORDER BY v.digg_count DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return {}

    hooks, structures, keywords_list, descs = [], [], [], []
    for desc, digg, hook, structure, keywords, suggestion in rows:
        if hook:
            hooks.append(hook)
        if structure:
            structures.append(structure)
        if keywords:
            keywords_list.extend([k.strip() for k in keywords.split(",")])
        descs.append((digg, desc))

    # 关键词词频统计
    from collections import Counter
    kw_freq = Counter(keywords_list).most_common(15)
    top_kw = "、".join([f"{k}({v}次)" for k, v in kw_freq])

    # TOP3 原文案
    top3_descs = "\n".join([f"({digg:,}赞) {desc[:80]}" for digg, desc in descs[:3]])

    return {
        "top_hooks": "\n".join([f"• {h}" for h in hooks[:8]]),
        "top_structures": "\n".join([f"• {s}" for s in structures[:6]]),
        "top_keywords": top_kw,
        "top_descs": top3_descs,
    }


def generate_copy(cfg: dict, count: int = 5) -> List[Dict]:
    """
    生成视频文案
    返回 list of {title, content, tags}
    """
    import os
    ai_cfg = cfg.get("ai_analyze", {})
    if not ai_cfg.get("enabled"):
        logger.warning("AI 分析未启用，请在 config.yaml 中开启 ai_analyze.enabled")
        return []

    data_dir = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
    db_path = data_dir / "monitor.db"

    if not db_path.exists():
        logger.error("数据库不存在，请先运行 --once 抓取视频后再生成文案")
        return []

    patterns = _load_analysis_patterns(db_path)
    if not patterns:
        logger.error("数据库中暂无分析数据，请先运行 --analyze 分析视频")
        return []

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        llm = ChatOpenAI(
            model=ai_cfg.get("model", "deepseek-chat"),
            api_key=ai_cfg.get("openai_api_key"),
            base_url=ai_cfg.get("openai_base_url", "https://api.deepseek.com/v1"),
            temperature=0.8,   # 生成创意文案用更高的温度
        )

        prompt = GENERATE_PROMPT.format(
            top_hooks=patterns["top_hooks"],
            top_structures=patterns["top_structures"],
            top_keywords=patterns["top_keywords"],
            top_descs=patterns["top_descs"],
            count=count,
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        # 提取 JSON（防止 DeepSeek 在前后加了说明文字）
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            logger.error(f"AI 返回格式异常: {raw[:200]}")
            return []

        results = json.loads(raw[start:end])
        logger.info(f"成功生成 {len(results)} 条文案")
        return results

    except Exception as e:
        logger.error(f"文案生成失败: {e}")
        return []


def batch_generate_and_push(cfg: dict, count: int = 5):
    """生成文案 + 推飞书 + 控制台输出"""
    print(f"\n{'='*65}")
    print(f"  AI 文案生成器 — 基于爆款规律生成 {count} 条新文案")
    print(f"{'='*65}\n")

    results = generate_copy(cfg, count)
    if not results:
        print("❌ 文案生成失败，请检查日志")
        return

    for i, item in enumerate(results, 1):
        print(f"【第{i}条】")
        print(f"  标题 : {item.get('title','')}")
        print(f"  正文 : {item.get('content','')}")
        print(f"  标签 : {'  '.join(['#'+t for t in item.get('tags',[])])}")
        print()

    # 推飞书
    feishu_webhook = cfg.get("notify", {}).get("feishu_webhook", "")
    if feishu_webhook:
        from notifier import send_feishu_generated_copy
        send_feishu_generated_copy(feishu_webhook, results)
        print(f"✅ 已推送飞书（共 {len(results)} 条文案）")
    else:
        print("⚠ 未配置飞书 webhook，跳过推送")
