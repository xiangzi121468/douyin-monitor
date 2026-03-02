# -*- coding: utf-8 -*-
"""
多平台视频监控 + AI文案分析主程序
支持平台：抖音 / B站

用法：
  python monitor.py                        # 启动持续监控（定时检查）
  python monitor.py --once                 # 只抓取一次新视频
  python monitor.py --analyze              # 分析所有未分析的视频（按点赞排序）
  python monitor.py --analyze --top 20     # 只分析点赞最高的 20 条
  python monitor.py --reanalyze            # 重新分析所有视频
  python monitor.py --generate             # AI 生成 5 条新文案并推飞书
  python monitor.py --generate --count 10  # 生成 10 条
  python monitor.py --list                 # 查看最近收集的视频
"""
import os
import sys
import time
import logging
import argparse
import yaml
import schedule
from pathlib import Path

_DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
_DATA_DIR.mkdir(parents=True, exist_ok=True)

from storage import init_db, is_new_video, save_video, save_analysis, get_recent_videos
from fetcher import get_user_videos
from notifier import notify_all
from analyzer import analyze_video, batch_analyze_top_videos
from generator import batch_generate_and_push

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_DATA_DIR / "monitor.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"

def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

def check_account(account: dict, cfg: dict):
    name = account.get("name", "")
    platform = account.get("platform", "douyin")
    logger.info(f"检查账号: {name} [{platform}]")

    videos = get_user_videos(account, max_count=20)
    if not videos:
        logger.warning(f"  {name} 未获取到视频，可能被风控或 sec_uid 有误")
        return

    new_count = 0
    for video in videos:
        aweme_id = video.get("aweme_id")
        if not aweme_id:
            continue

        if is_new_video(aweme_id):
            new_count += 1
            logger.info(f"  🆕 新视频: {video.get('desc','')[:50]} | 👍{video.get('digg_count',0):,}")

            # 存库
            save_video(video)

            # AI分析
            analysis = analyze_video(video, cfg)
            if analysis:
                save_analysis(aweme_id, analysis)

            # 发通知
            notify_all(cfg, video, analysis)

            time.sleep(0.5)

    if new_count == 0:
        logger.info(f"  {name} 无新视频")
    else:
        logger.info(f"  {name} 发现 {new_count} 条新视频")

def check_all(cfg: dict):
    accounts = cfg.get("accounts", [])
    logger.info(f"开始检查 {len(accounts)} 个账号...")
    for account in accounts:
        try:
            check_account(account, cfg)
        except Exception as e:
            logger.error(f"检查账号 {account.get('name')} 时出错: {e}")
        time.sleep(2)  # 账号之间间隔，避免风控
    logger.info("本轮检查完毕")

def main():
    parser = argparse.ArgumentParser(description="多平台视频监控 + AI文案分析工具")
    parser.add_argument("--once",      action="store_true", help="只抓取一次新视频后退出")
    parser.add_argument("--analyze",   action="store_true", help="分析所有未分析的视频（按点赞排序）")
    parser.add_argument("--reanalyze", action="store_true", help="重新分析所有视频（包括已分析的）")
    parser.add_argument("--top",       type=int, default=None, metavar="N", help="只处理点赞最高的 N 条")
    parser.add_argument("--generate",  action="store_true", help="AI 生成新文案并推飞书")
    parser.add_argument("--count",     type=int, default=5, metavar="N", help="生成文案条数（默认5）")
    parser.add_argument("--list",      action="store_true", help="列出最近收集的视频")
    args = parser.parse_args()

    # 初始化数据库
    init_db()
    cfg = load_config()

    if args.list:
        rows = get_recent_videos(20)
        print(f"\n最近收集的 {len(rows)} 条视频：")
        print(f"{'='*70}")
        for aweme_id, author, desc, digg, play, fetched_at in rows:
            print(f"[{fetched_at}] {author} | 👍{digg:,} ▶{play:,}")
            print(f"  {desc[:60]}...")
        return

    if args.analyze or args.reanalyze:
        batch_analyze_top_videos(
            cfg,
            limit=args.top,
            skip_analyzed=(not args.reanalyze),
        )
        return

    if args.generate:
        batch_generate_and_push(cfg, count=args.count)
        return

    if args.once:
        check_all(cfg)
        return

    # 持续监控模式
    interval = cfg.get("check_interval", 60)
    logger.info(f"启动持续监控，检查间隔 {interval} 分钟")

    # 启动时先检查一次
    check_all(cfg)

    schedule.every(interval).minutes.do(check_all, cfg=cfg)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
