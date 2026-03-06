# -*- coding: utf-8 -*-
"""
蝉妈妈热销商品抓取器
- 不需要登录，免费获取 TOP10 热销商品
- 支持按大类筛选（家居家纺 id=10, 家具建材 id=7 等）
- 数据来源: 蝉妈妈抖音商品销量榜
"""

import logging
import re
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 蝉妈妈类目 ID 映射（来自 API 实际返回）
CATEGORY_MAP = {
    "all": -1,
    "全部": -1,
    "服饰内衣": 22,
    "鞋靴箱包": 18,
    "食品饮料": 17,
    "美妆护肤": 8,
    "运动户外": 13,
    "日用百货": 19,
    "家居家纺": 10,
    "母婴用品": 1,
    "医药保健": 25,
    "3C数码": 9,
    "厨卫家电": 20,
    "家具建材": 7,
    "珠宝饰品": 24,
    "玩具乐器": 15,
    "图书教育": 14,
    "礼品文创": 11,
    "生鲜蔬果": 3,
    "宠物用品": 21,
    "汽配摩托": 5,
    "本地生活": 2,
}

# 装修相关类目（可同时抓多个）
HOME_DECO_CATEGORIES = [
    {"name": "家居家纺", "id": 10},
    {"name": "家具建材", "id": 7},
]


def _parse_row_text(row_text: str) -> Optional[dict]:
    """从表格行文本解析商品信息"""
    lines = [l.strip() for l in re.split(r'[\t\n]', row_text) if l.strip()]
    if not lines or len(lines) < 3:
        return None

    # 移除首部可能的排名数字
    start = 0
    if lines[0].isdigit():
        start = 1

    if start >= len(lines):
        return None

    title = lines[start]
    if not title or len(title) < 5:
        return None

    # 提取佣金、日销量、销售额、转化率
    commission = ""
    daily_sales = ""
    total_sales = ""
    conversion = ""

    remaining = lines[start + 1:]
    for part in remaining:
        part = part.strip()
        if not part:
            continue
        # 佣金：含 % 且较短
        if "%" in part and not commission and len(part) < 20:
            # 蝉选字样处理
            if "蝉选" in part or "公开" in part or "相似" in part:
                commission = part.replace("\n", " ")
            else:
                commission = part
        # 日销量：含 w 或 万
        elif ("w" in part.lower() or "万" in part) and not daily_sales and "~" in part:
            daily_sales = part
        # 销售额：比日销量更大的数（第二次遇到 w~w 格式）
        elif ("w" in part.lower() or "万" in part) and "~" in part and not total_sales and daily_sales:
            total_sales = part
        # 转化率：带 %+ 或 %~% 格式
        elif "%" in part and ("+" in part or "~" in part) and not conversion:
            conversion = part

    return {
        "title": title,
        "commission": commission or "0%",
        "daily_sales": daily_sales or "未知",
        "total_sales": total_sales or "未知",
        "conversion": conversion or "未知",
        "source": "蝉妈妈",
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


async def fetch_hot_products(category_id: int = -1, category_name: str = "全部") -> list[dict]:
    """
    用 Playwright 抓取蝉妈妈商品销量榜 TOP10（免登录）

    Args:
        category_id: 类目 ID，-1 表示全部
        category_name: 类目名称（用于日志）

    Returns:
        商品列表，每项包含 title, commission, daily_sales, total_sales, conversion
    """
    from playwright.async_api import async_playwright

    url = f"https://www.chanmama.com/promotionRank/tikGoodsSale/?category_id={category_id}"
    logger.info(f"抓取蝉妈妈商品销量榜: {category_name} ({url})")

    products = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
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

            # 如果分类需要登录则会跳转到注册页，捕获一下
            await page.goto(url, wait_until="networkidle", timeout=50000)
            await page.wait_for_timeout(4000)

            current_url = page.url
            if "register" in current_url or "login" in current_url:
                logger.warning(f"类目筛选需要登录，降级为全部类目")
                await page.goto(
                    "https://www.chanmama.com/promotionRank/tikGoodsSale/?category_id=-1",
                    wait_until="networkidle", timeout=50000
                )
                await page.wait_for_timeout(4000)
                category_name = "全部（免登录）"

            # 提取商品行
            rows = await page.evaluate("""
                () => {
                    const results = [];
                    const trs = document.querySelectorAll('tr');
                    for (const tr of trs) {
                        const text = tr.innerText ? tr.innerText.trim() : '';
                        if (text && text.length > 10
                            && (text.includes('w') || text.includes('万') || text.includes('%'))
                            && !text.includes('排行') && !text.includes('商品信息')) {
                            results.push(text);
                            if (results.length >= 15) break;
                        }
                    }
                    return results;
                }
            """)

            logger.info(f"解析到 {len(rows)} 个候选行")

            for idx, row_text in enumerate(rows, 1):
                parsed = _parse_row_text(row_text)
                if parsed:
                    parsed["rank"] = idx
                    parsed["category"] = category_name
                    products.append(parsed)
                    logger.debug(f"  #{idx} {parsed['title'][:30]} | 日销:{parsed['daily_sales']}")

            await browser.close()

    except Exception as e:
        logger.error(f"抓取蝉妈妈失败: {e}", exc_info=True)

    logger.info(f"共获取 {len(products)} 个商品")
    return products


async def fetch_home_deco_products() -> list[dict]:
    """
    抓取家居装修相关热销商品
    - 先尝试家居家纺类目（需登录则自动降级全部）
    - 若类目 API 可用则再抓家具建材
    - 最终结果去重
    """
    seen_titles = set()
    all_products = []

    for cat in HOME_DECO_CATEGORIES:
        products = await fetch_hot_products(cat["id"], cat["name"])
        added = 0
        for p in products:
            key = p["title"][:30]
            if key not in seen_titles:
                seen_titles.add(key)
                all_products.append(p)
                added += 1
        # 如果该类目 fallback 了（商品 category 变成"全部"），不再重复抓
        if products and products[0].get("category", "").startswith("全部"):
            logger.info("检测到类目筛选需要登录，跳过后续类目，仅取全部榜 TOP10")
            break

    return all_products


# CLI 测试入口
if __name__ == "__main__":
    import asyncio
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    async def main():
        products = await fetch_home_deco_products()
        print(f"\n=== 热销商品 TOP {len(products)} ===")
        for p in products:
            print(f"\n#{p['rank']} 【{p['category']}】{p['title']}")
            print(f"   佣金: {p['commission']} | 日销: {p['daily_sales']} | 销售额: {p['total_sales']} | 转化率: {p['conversion']}")

    asyncio.run(main())
