# -*- coding: utf-8 -*-
"""
抖音用户视频列表抓取 - 使用 Playwright 真实浏览器，绕过风控
"""
import json
import time
import logging
import asyncio
from typing import List, Dict

logger = logging.getLogger(__name__)

SEC_UID_TO_HOMEPAGE = "https://www.douyin.com/user/{sec_uid}"


async def _fetch_user_videos_async(sec_uid: str, max_count: int = 20) -> List[Dict]:
    from playwright.async_api import async_playwright

    videos = []
    api_data = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        page = await context.new_page()

        # 拦截 API 响应
        captured = []

        async def handle_response(response):
            url = response.url
            if "aweme/v1/web/aweme/post" in url:
                try:
                    body = await response.json()
                    captured.append(body)
                    logger.info(f"拦截到 API 响应，视频数量: {len(body.get('aweme_list', []))}")
                except Exception:
                    pass

        page.on("response", handle_response)

        homepage = SEC_UID_TO_HOMEPAGE.format(sec_uid=sec_uid)
        logger.info(f"打开主页: {homepage}")

        try:
            await page.goto(homepage, wait_until="domcontentloaded", timeout=30000)
            # 等待页面加载并触发 API 请求
            await page.wait_for_timeout(5000)

            # 模拟向下滚动，触发更多视频加载
            await page.evaluate("window.scrollTo(0, 500)")
            await page.wait_for_timeout(3000)

        except Exception as e:
            logger.error(f"页面加载失败: {e}")
        finally:
            await browser.close()

        # 解析拦截到的数据
        for data in captured:
            for item in data.get("aweme_list", []):
                try:
                    tags = [t.get("title", "") for t in item.get("text_extra", [])
                            if t.get("type") == 1]

                    video_url, cover_url = "", ""
                    play_addr = item.get("video", {}).get("play_addr", {})
                    if play_addr.get("url_list"):
                        video_url = play_addr["url_list"][0]
                    cover = item.get("video", {}).get("cover", {})
                    if cover.get("url_list"):
                        cover_url = cover["url_list"][0]

                    stats  = item.get("statistics", {})
                    author = item.get("author", {})

                    videos.append({
                        "aweme_id":      item.get("aweme_id"),
                        "sec_uid":       sec_uid,
                        "author_name":   author.get("nickname", ""),
                        "desc":          item.get("desc", ""),
                        "tags":          tags,
                        "create_time":   item.get("create_time", 0),
                        "digg_count":    stats.get("digg_count", 0),
                        "comment_count": stats.get("comment_count", 0),
                        "share_count":   stats.get("share_count", 0),
                        "play_count":    stats.get("play_count", 0),
                        "video_url":     video_url,
                        "cover_url":     cover_url,
                    })

                    if len(videos) >= max_count:
                        break
                except Exception as e:
                    logger.warning(f"解析视频数据出错: {e}")
                    continue

    logger.info(f"共获取 {len(videos)} 条视频")
    return videos


def get_user_videos(sec_uid: str, max_count: int = 20) -> List[Dict]:
    """同步封装（供 monitor.py 调用）"""
    try:
        return asyncio.run(_fetch_user_videos_async(sec_uid, max_count))
    except Exception as e:
        logger.error(f"获取视频失败: {e}")
        return []
