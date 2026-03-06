# -*- coding: utf-8 -*-
"""
抖音精选联盟热销商品抓取
使用 Playwright 登录精选联盟，拦截商品列表 API，获取热销榜数据

支持按类目筛选：
  0   — 全部
  50  — 家居/家装/厨具
  161 — 家电
  20  — 服饰
  ...（更多类目见 CATEGORY_MAP）
"""
import json
import asyncio
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

HAOHUO_URL = "https://haohuo.jinritemai.com/views/product/list"

# 常用类目 ID（精选联盟一级类目）
CATEGORY_MAP = {
    "全部":      "0",
    "家居家装":  "50",
    "厨具":      "50",
    "家电":      "161",
    "建材":      "1437",
    "服饰":      "20",
    "美妆":      "18",
    "食品":      "21",
    "母婴":      "24",
    "数码":      "161",
}


async def _fetch_products_async(
    cookies: dict,
    category_id: str = "50",
    max_count: int = 30,
) -> List[Dict]:
    """
    Playwright 浏览器抓取精选联盟商品列表
    cookies    — 抖音登录 Cookie dict（从 config.yaml 读取）
    category_id — 类目 ID，默认 50（家居家装）
    """
    from playwright.async_api import async_playwright

    products = []
    captured = []

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

        # 注入抖音登录 Cookies
        for name, value in cookies.items():
            await context.add_cookies([{
                "name":   name,
                "value":  value,
                "domain": ".jinritemai.com",
                "path":   "/",
            }])
            await context.add_cookies([{
                "name":   name,
                "value":  value,
                "domain": ".douyin.com",
                "path":   "/",
            }])

        page = await context.new_page()

        # 拦截商品列表 API
        async def handle_response(response):
            url = response.url
            if any(kw in url for kw in [
                "product/search", "product/list",
                "alliance/product", "haohuo/product",
                "ecommerce/product",
            ]):
                try:
                    body = await response.json()
                    captured.append({"url": url, "body": body})
                    logger.info(f"拦截到商品 API: {url[:80]}")
                except Exception:
                    pass

        page.on("response", handle_response)

        # 打开精选联盟商品列表，带类目参数
        target_url = f"{HAOHUO_URL}?product_type=0&category_id={category_id}&sort_type=2"
        logger.info(f"打开精选联盟: {target_url}")

        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
            await page.wait_for_timeout(5000)

            # 滚动触发更多数据
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

        except Exception as e:
            logger.error(f"页面加载失败: {e}")
        finally:
            await browser.close()

    # 解析拦截到的商品数据
    for item in captured:
        body = item["body"]
        # 尝试不同的数据路径
        raw_list = (
            body.get("data", {}).get("products", [])
            or body.get("data", {}).get("list", [])
            or body.get("data", {}).get("product_list", [])
            or body.get("products", [])
            or []
        )

        for p in raw_list:
            try:
                # 兼容不同字段名
                product_id  = str(p.get("product_id") or p.get("id") or "")
                title       = p.get("title") or p.get("product_name") or p.get("name") or ""
                price_raw   = p.get("price") or p.get("min_price") or 0
                price       = float(price_raw) / 100 if price_raw > 100 else float(price_raw)
                monthly_sales = (
                    p.get("sales_volume") or p.get("month_sales")
                    or p.get("monthly_sales") or p.get("sold_count") or 0
                )
                commission_rate = (
                    p.get("cos_ratio") or p.get("commission_rate")
                    or p.get("ratio") or 0
                )
                commission_rate_pct = (
                    commission_rate / 100
                    if commission_rate > 1 else commission_rate * 100
                )
                cover_url = (
                    p.get("cover") or p.get("img") or p.get("product_img") or ""
                )
                product_url = (
                    p.get("schema") or p.get("url")
                    or f"https://haohuo.jinritemai.com/views/product/item2?id={product_id}"
                )

                if not title or not product_id:
                    continue

                products.append({
                    "product_id":       product_id,
                    "title":            title,
                    "price":            price,
                    "monthly_sales":    int(monthly_sales),
                    "commission_rate":  round(commission_rate_pct, 1),
                    "cover_url":        cover_url,
                    "product_url":      product_url,
                    "category_id":      category_id,
                })

                if len(products) >= max_count:
                    break
            except Exception as e:
                logger.warning(f"解析商品数据出错: {e}")
                continue

        if len(products) >= max_count:
            break

    # 按月销量排序
    products.sort(key=lambda x: x["monthly_sales"], reverse=True)
    logger.info(f"共获取 {len(products)} 个商品")
    return products


def fetch_hot_products(
    cfg: dict,
    category: str = "家居家装",
    max_count: int = 30,
) -> List[Dict]:
    """同步封装，供 monitor.py 调用"""
    douyin_cookies = cfg.get("douyin_cookies", {})
    if not douyin_cookies:
        logger.error("未配置 douyin_cookies，请在 config.yaml 中填写抖音登录 Cookie")
        return []

    category_id = CATEGORY_MAP.get(category, "50")
    logger.info(f"抓取精选联盟热销商品，类目：{category}（ID={category_id}）")

    try:
        return asyncio.run(
            _fetch_products_async(douyin_cookies, category_id, max_count)
        )
    except Exception as e:
        logger.error(f"商品抓取失败: {e}")
        return []
