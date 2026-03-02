# -*- coding: utf-8 -*-
"""
B站用户视频列表抓取
使用 B站公开 API（无需登录，免 Playwright）
"""
import time
import logging
import requests
from typing import List, Dict

logger = logging.getLogger(__name__)

# B站用户视频列表 API
BILI_API_URL = "https://api.bilibili.com/x/space/arc/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def get_user_videos(uid: str, max_count: int = 20) -> List[Dict]:
    """
    抓取 B站用户最新视频
    uid: B站用户 UID（纯数字，如 "123456789"）
    """
    videos = []
    page = 1
    page_size = min(max_count, 30)

    while len(videos) < max_count:
        try:
            params = {
                "mid": uid,
                "ps": page_size,
                "pn": page,
                "order": "pubdate",   # 按发布时间倒序
                "tid": 0,
                "keyword": "",
            }
            resp = requests.get(
                BILI_API_URL,
                params=params,
                headers=HEADERS,
                timeout=15,
            )
            data = resp.json()

            if data.get("code") != 0:
                logger.error(f"B站 API 错误: code={data.get('code')}, msg={data.get('message')}")
                break

            vlist = data.get("data", {}).get("list", {}).get("vlist", [])
            if not vlist:
                break

            for item in vlist:
                videos.append({
                    "aweme_id":      f"bili_{item.get('bvid', item.get('aid', ''))}",
                    "sec_uid":       uid,
                    "author_name":   item.get("author", ""),
                    "desc":          item.get("title", "") + ("  " + item.get("description", "") if item.get("description") else ""),
                    "tags":          [],   # B站视频详情接口才有标签，列表接口无
                    "create_time":   item.get("created", 0),
                    "digg_count":    item.get("play", 0),     # B站列表只有播放数，用播放代替点赞
                    "comment_count": item.get("comment", 0),
                    "share_count":   0,
                    "play_count":    item.get("play", 0),
                    "video_url":     f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                    "cover_url":     item.get("pic", ""),
                    "platform":      "bilibili",
                })
                if len(videos) >= max_count:
                    break

            # 是否还有下一页
            total = data.get("data", {}).get("page", {}).get("count", 0)
            if len(videos) >= total:
                break

            page += 1
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"B站抓取失败: {e}")
            break

    logger.info(f"B站共获取 {len(videos)} 条视频")
    return videos
