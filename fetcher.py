# -*- coding: utf-8 -*-
"""
多平台视频抓取调度器
根据账号配置的 platform 字段，分发到对应平台的抓取模块

支持平台：
  douyin   — 抖音（Playwright 浏览器）
  bilibili — B站（公开 API）
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def get_user_videos(account: dict, max_count: int = 20) -> List[Dict]:
    """
    统一入口：根据 account.platform 分发到对应抓取器

    account 字段：
      platform  — "douyin"（默认）| "bilibili"
      sec_uid   — 抖音 sec_uid
      uid       — B站用户 UID
      name      — 博主昵称（用于日志）
    """
    platform = account.get("platform", "douyin").lower()
    name = account.get("name", "")

    if platform == "bilibili":
        uid = account.get("uid", "")
        if not uid:
            logger.error(f"[{name}] B站账号缺少 uid 字段")
            return []
        sessdata = account.get("sessdata", "")
        logger.info(f"[{name}] 平台: B站，UID: {uid}，{'已配置 SESSDATA' if sessdata else '匿名模式'}")
        from fetcher_bili import get_user_videos as bili_fetch
        return bili_fetch(uid, max_count, sessdata=sessdata)

    else:  # 默认抖音
        sec_uid = account.get("sec_uid", "")
        if not sec_uid:
            logger.error(f"[{name}] 抖音账号缺少 sec_uid 字段")
            return []
        logger.info(f"[{name}] 平台: 抖音，sec_uid: {sec_uid[:30]}...")
        from fetcher_douyin import get_user_videos as dy_fetch
        return dy_fetch(sec_uid, max_count)
