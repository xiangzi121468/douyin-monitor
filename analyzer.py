# -*- coding: utf-8 -*-
"""
用 LangChain 分析爆款文案结构
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ANALYZE_PROMPT = """你是一个抖音爆款文案分析专家，专注于【装修/家居/AI设计】赛道。

请分析以下抖音视频文案，提炼爆款规律：

文案内容：
{desc}

标签：{tags}
点赞数：{digg_count}
播放数：{play_count}

请从以下4个维度输出JSON格式分析结果：
1. hook（开头钩子话术，用户为什么停下来看）
2. structure（文案结构，如：痛点+解决方案+行动号召）
3. keywords（核心关键词，逗号分隔）
4. suggestion（给我的账号的模仿建议，一句话）

只输出JSON，不要其他内容：
{{"hook":"...","structure":"...","keywords":"...","suggestion":"..."}}
"""

def analyze_video(video: dict, cfg: dict) -> Optional[dict]:
    ai_cfg = cfg.get("ai_analyze", {})
    if not ai_cfg.get("enabled"):
        return None

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        llm = ChatOpenAI(
            model=ai_cfg.get("model", "gpt-4o-mini"),
            api_key=ai_cfg.get("openai_api_key"),
            base_url=ai_cfg.get("openai_base_url", "https://api.openai.com/v1"),
            temperature=0.3,
        )

        prompt = ANALYZE_PROMPT.format(
            desc=video.get("desc", ""),
            tags=", ".join(video.get("tags", [])),
            digg_count=video.get("digg_count", 0),
            play_count=video.get("play_count", 0),
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        result = json.loads(response.content.strip())
        logger.info(f"AI分析完成: {video.get('aweme_id')}")
        return result

    except Exception as e:
        logger.error(f"AI分析失败: {e}")
        return None


def batch_analyze_top_videos(cfg: dict, limit: int = None, skip_analyzed: bool = True):
    """
    批量分析数据库里的视频，按点赞数从高到低排序。

    limit         — 最多分析多少条；None = 全部
    skip_analyzed — True（默认）跳过已有分析记录的视频；False = 全部重新分析
    """
    import sqlite3
    import json
    from pathlib import Path
    from storage import save_analysis

    db_path = Path(__file__).parent / "monitor.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    if skip_analyzed:
        # 只取还没有 analysis 记录的视频
        sql = """
            SELECT v.aweme_id, v.author_name, v.desc, v.tags, v.digg_count, v.play_count
            FROM videos v
            LEFT JOIN analysis a ON v.aweme_id = a.aweme_id
            WHERE a.aweme_id IS NULL
            ORDER BY v.digg_count DESC
        """
    else:
        # 全部重新分析
        sql = """
            SELECT aweme_id, author_name, desc, tags, digg_count, play_count
            FROM videos
            ORDER BY digg_count DESC
        """

    if limit:
        sql += f" LIMIT {int(limit)}"

    c.execute(sql)
    rows = c.fetchall()

    # 统计各博主总视频数（用于进度显示）
    c.execute("SELECT author_name, COUNT(*) FROM videos GROUP BY author_name")
    author_total = {r[0]: r[1] for r in c.fetchall()}
    conn.close()

    if not rows:
        if skip_analyzed:
            print("所有视频已全部分析完毕，无需重复分析。")
            print("如需重新分析，运行: python monitor.py --analyze --reanalyze")
        else:
            print("数据库暂无数据，请先运行监控程序收集视频")
        return

    total = len(rows)
    label = f"全量（共 {total} 条）" if not limit else f"TOP {total} 条"
    print(f"\n{'='*65}")
    print(f"  抖音视频文案分析报告 — {label}，按点赞从高到低")
    print(f"  跳过已分析: {'是' if skip_analyzed else '否（全部重新分析）'}")
    print(f"{'='*65}\n")

    # 按博主分组显示进度
    from collections import defaultdict
    author_done: dict = defaultdict(int)

    report_rows = []

    for i, row in enumerate(rows, 1):
        aweme_id, author, desc, tags_json, digg, play = row
        tags = json.loads(tags_json) if tags_json else []
        total_for_author = author_total.get(author, "?")

        print(f"[{i}/{total}] [{author}]  👍{digg:,}  ▶{play:,}")
        print(f"  文案: {desc[:80]}")

        video = {
            "aweme_id": aweme_id,
            "author_name": author,
            "desc": desc,
            "tags": tags,
            "digg_count": digg,
            "play_count": play,
        }

        result = analyze_video(video, cfg)
        if result:
            save_analysis(aweme_id, result)
            author_done[author] += 1
            print(f"  钩子   : {result.get('hook','')}")
            print(f"  结构   : {result.get('structure','')}")
            print(f"  关键词 : {result.get('keywords','')}")
            print(f"  建议   : {result.get('suggestion','')}")
            report_rows.append((
                author, desc, digg,
                result.get("hook", ""),
                result.get("structure", ""),
                result.get("keywords", ""),
                result.get("suggestion", ""),
            ))
        else:
            print("  ⚠ AI分析失败，跳过")
        print()

    # ── 进度小结 ────────────────────────────────────────────────────
    print(f"{'='*65}")
    print(f"分析完成：成功 {len(report_rows)} / 共 {total} 条")
    for author, cnt in author_done.items():
        print(f"  {author}: {cnt} 条")
    print(f"{'='*65}\n")

    # ── 推飞书汇总报告 ────────────────────────────────────────────
    if report_rows:
        from notifier import send_feishu_analysis_report

        global_webhook = cfg.get("notify", {}).get("feishu_webhook", "")
        webhook_map = {
            acc["name"]: acc["feishu_webhook"]
            for acc in cfg.get("accounts", [])
            if acc.get("name") and acc.get("feishu_webhook")
        }

        send_feishu_analysis_report(global_webhook, report_rows, webhook_map=webhook_map)
        routed = list(webhook_map.keys())
        print(f"✅ 飞书报告已推送（共 {len(report_rows)} 条"
              f"{'，专属路由: ' + str(routed) if routed else '，全局 webhook'}）")
