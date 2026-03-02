# -*- coding: utf-8 -*-
"""
B站用户视频列表抓取
使用 WBI 签名接口（B站 2023 年后的标准认证方式）
"""
import time
import hashlib
import logging
import requests
from functools import reduce
from typing import List, Dict

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://space.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://space.bilibili.com",
}

# WBI mixin key 混淆表
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


def _get_mixin_key(orig: str) -> str:
    return reduce(lambda s, i: s + orig[i], MIXIN_KEY_ENC_TAB, "")[:32]


def _get_wbi_keys(session: requests.Session) -> tuple:
    """从 B站 nav 接口获取 wbi img/sub key"""
    resp = session.get(
        "https://api.bilibili.com/x/web-interface/nav",
        headers=HEADERS,
        timeout=10,
    )
    data = resp.json()
    wbi_img = data["data"]["wbi_img"]
    img_key = wbi_img["img_url"].rsplit("/", 1)[-1].split(".")[0]
    sub_key = wbi_img["sub_url"].rsplit("/", 1)[-1].split(".")[0]
    return img_key, sub_key


def _sign_params(params: dict, mixin_key: str) -> dict:
    """对请求参数进行 WBI 签名"""
    import urllib.parse
    params["wts"] = int(time.time())
    # 按 key 排序，过滤特殊字符
    query = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(params.items())
        if k not in ("Referer", "User-Agent")
    )
    w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params["w_rid"] = w_rid
    return params


def get_user_videos(uid: str, max_count: int = 20, sessdata: str = "") -> List[Dict]:
    """
    抓取 B站用户最新视频（WBI 签名接口）
    uid      : B站用户 UID（纯数字）
    sessdata : B站登录 Cookie（SESSDATA）
    """
    videos = []
    page = 1
    page_size = min(max_count, 30)

    session = requests.Session()
    session.headers.update(HEADERS)
    if sessdata:
        session.cookies.set("SESSDATA", sessdata, domain=".bilibili.com")

    try:
        img_key, sub_key = _get_wbi_keys(session)
        mixin_key = _get_mixin_key(img_key + sub_key)
        logger.info(f"B站 WBI 签名获取成功")
    except Exception as e:
        logger.error(f"获取 WBI key 失败: {e}，尝试无签名模式")
        mixin_key = None

    while len(videos) < max_count:
        try:
            params = {
                "mid": uid,
                "ps": page_size,
                "pn": page,
                "order": "pubdate",
                "tid": 0,
                "keyword": "",
            }

            if mixin_key:
                params = _sign_params(params, mixin_key)
                url = "https://api.bilibili.com/x/space/wbi/arc/search"
            else:
                url = "https://api.bilibili.com/x/space/arc/search"

            resp = session.get(url, params=params, timeout=15)
            data = resp.json()
            code = data.get("code", -1)

            if code == -799:
                logger.warning("B站触发频率限制，等待 8 秒后重试...")
                time.sleep(8)
                continue

            if code != 0:
                logger.error(f"B站 API 错误: code={code}, msg={data.get('message')}")
                if not sessdata:
                    logger.warning("建议在 config.yaml 配置 sessdata（浏览器登录B站后从 Cookie 获取）")
                break

            vlist = data.get("data", {}).get("list", {}).get("vlist", [])
            if not vlist:
                logger.info(f"B站第 {page} 页无数据，结束")
                break

            author_name = vlist[0].get("author", "") if vlist else ""

            for item in vlist:
                videos.append({
                    "aweme_id":      f"bili_{item.get('bvid', item.get('aid', ''))}",
                    "sec_uid":       uid,
                    "author_name":   item.get("author", author_name),
                    "desc":          item.get("title", "") + (
                        "  " + item.get("description", "") if item.get("description") else ""
                    ),
                    "tags":          [],
                    "create_time":   item.get("created", 0),
                    "digg_count":    item.get("play", 0),
                    "comment_count": item.get("comment", 0),
                    "share_count":   0,
                    "play_count":    item.get("play", 0),
                    "video_url":     f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                    "cover_url":     item.get("pic", ""),
                    "platform":      "bilibili",
                })
                if len(videos) >= max_count:
                    break

            total = data.get("data", {}).get("page", {}).get("count", 0)
            if len(videos) >= total:
                break

            page += 1
            time.sleep(1)

        except Exception as e:
            logger.error(f"B站抓取异常: {e}")
            break

    logger.info(f"B站共获取 {len(videos)} 条视频")
    return videos
