# -*- coding: utf-8 -*-
import json
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 飞书卡片消息 ─────────────────────────────────────────────────

def send_feishu_new_video(webhook: str, video: dict, analysis: dict = None):
    """发现新视频时推送飞书卡片"""
    if not webhook or "填入你的token" in webhook:
        return

    ts = datetime.fromtimestamp(video.get("create_time", 0)).strftime("%Y-%m-%d %H:%M")
    tags = "  ".join([f"#{t}" for t in video.get("tags", [])[:5]]) or "无"
    author = video.get("author_name", "")
    desc = video.get("desc", "")[:120]

    # 统计数字行
    stats = (f"👍 {video.get('digg_count',0):,}　"
             f"💬 {video.get('comment_count',0):,}　"
             f"↗ {video.get('share_count',0):,}　"
             f"▶ {video.get('play_count',0):,}")

    elements = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**发布者：** {author}　　**发布时间：** {ts}"}
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**文案内容**\n{desc}"}
        },
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**标签**　{tags}"}
        },
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**数据**　{stats}"}
        },
    ]

    if analysis:
        elements += [
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**🤖 DeepSeek 文案分析**\n\n"
                        f"🪝 **钩子话术**\n{analysis.get('hook','')}\n\n"
                        f"🏗 **文案结构**\n{analysis.get('structure','')}\n\n"
                        f"🔑 **核心关键词**\n{analysis.get('keywords','')}\n\n"
                        f"💡 **模仿建议**\n{analysis.get('suggestion','')}"
                    )
                }
            },
        ]

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"content": f"🎬 新视频 | {author}", "tag": "plain_text"},
            "template": "blue",
        },
        "elements": elements,
    }

    _send_feishu_card(webhook, card, f"抖音监控 | {author} 发布新视频")


def _build_author_card_elements(author: str, rows: list, icon: str = "🔵") -> list:
    """生成单个博主的卡片 elements（供复用）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"共 **{len(rows)}** 条视频　　生成时间：{now}"
            }
        },
        {"tag": "hr"},
    ]
    for j, row in enumerate(rows):
        _, desc, digg, hook, structure, keywords, suggestion = row
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**第{j+1}条　👍 {digg:,}**\n"
                    f"原文案：{desc[:60]}{'...' if len(desc) > 60 else ''}\n\n"
                    f"🪝 **钩子**：{hook}\n"
                    f"🏗 **结构**：{structure}\n"
                    f"🔑 **关键词**：{keywords}\n"
                    f"💡 **建议**：{suggestion}"
                )
            }
        })
        if j < len(rows) - 1:
            elements.append({"tag": "hr"})

    elements += [
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    "**📌 爆款公式总结**\n"
                    "1️⃣ **数字+痛点** → `装修增项，最多的【X】个地方`\n"
                    "2️⃣ **AI+省钱** → `AI秒出【X】套方案，省【X万】设计费`\n"
                    "3️⃣ **强反差+免费** → `花【XX】装出【万元】效果，工具免费用`\n"
                    "4️⃣ **悬念设问** → `手把手教你拆解报价单，猜猜增项了多少万？`"
                )
            }
        }
    ]
    return elements


def send_feishu_author_report(webhook: str, author: str, rows: list, icon: str = "🔵"):
    """
    推送单个博主的分析报告卡片（专属 webhook 路由）
    rows: list of (author, desc, digg, hook, structure, keywords, suggestion)
    """
    if not webhook or "填入你的token" in webhook:
        return
    if not rows:
        return

    elements = _build_author_card_elements(author, rows, icon)
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"content": f"{icon} {author} | 爆款文案分析", "tag": "plain_text"},
            "template": "green",
        },
        "elements": elements,
    }
    _send_feishu_card(webhook, card, f"{author} 爆款文案分析报告")


def send_feishu_analysis_report(webhook: str, report_rows: list,
                                 webhook_map: dict = None):
    """
    批量分析完成后推送飞书报告。

    webhook      — 全局默认 webhook（账号无专属时使用）
    report_rows  — list of (author, desc, digg, hook, structure, keywords, suggestion)
    webhook_map  — {author_name: feishu_webhook_url}，有值则按博主路由到各自飞书群；
                   路由后剩余无专属 webhook 的博主，合并发到全局 webhook。
    """
    if not report_rows:
        return

    from collections import OrderedDict
    author_icons = ["🔵", "🟠", "🟢", "🟣", "🔴", "🟡"]

    # ── 按博主分组 ────────────────────────────────────
    grouped: dict = OrderedDict()
    for row in report_rows:
        grouped.setdefault(row[0], []).append(row)

    routed_authors = set()  # 已路由到专属 webhook 的博主

    # ── 1. 有专属 webhook 的博主 → 各自发送 ──────────
    if webhook_map:
        for idx, (author, rows) in enumerate(grouped.items()):
            author_webhook = webhook_map.get(author, "")
            if author_webhook and "填入你的token" not in author_webhook:
                icon = author_icons[idx % len(author_icons)]
                send_feishu_author_report(author_webhook, author, rows, icon)
                logger.info(f"[路由] {author} → 专属 webhook")
                routed_authors.add(author)

    # ── 2. 剩余博主 → 合并发到全局 webhook ───────────
    remaining = [(a, rows) for a, rows in grouped.items() if a not in routed_authors]
    if not remaining:
        return
    if not webhook or "填入你的token" in webhook:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    video_count = sum(len(r) for _, r in remaining)
    author_count = len(remaining)

    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"共分析 **{video_count}** 条视频　共 **{author_count}** 个博主　　生成时间：{now}"
            }
        },
        {"tag": "hr"},
    ]

    for idx, (author, rows) in enumerate(remaining):
        icon = author_icons[idx % len(author_icons)]
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"{icon} **{author}**　共 {len(rows)} 条视频"
            }
        })
        for j, row in enumerate(rows):
            _, desc, digg, hook, structure, keywords, suggestion = row
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**第{j+1}条　👍 {digg:,}**\n"
                        f"原文案：{desc[:60]}{'...' if len(desc) > 60 else ''}\n\n"
                        f"🪝 **钩子**：{hook}\n"
                        f"🏗 **结构**：{structure}\n"
                        f"🔑 **关键词**：{keywords}\n"
                        f"💡 **建议**：{suggestion}"
                    )
                }
            })
            if j < len(rows) - 1:
                elements.append({"tag": "hr"})
        if idx < author_count - 1:
            elements.append({"tag": "hr"})

    elements += [
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    "**📌 爆款公式总结**\n"
                    "1️⃣ **数字+痛点** → `装修增项，最多的【X】个地方`\n"
                    "2️⃣ **AI+省钱** → `AI秒出【X】套方案，省【X万】设计费`\n"
                    "3️⃣ **强反差+免费** → `花【XX】装出【万元】效果，工具免费用`\n"
                    "4️⃣ **悬念设问** → `手把手教你拆解报价单，猜猜增项了多少万？`"
                )
            }
        }
    ]

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"content": "📊 抖音爆款文案分析报告", "tag": "plain_text"},
            "template": "green",
        },
        "elements": elements,
    }
    _send_feishu_card(webhook, card, "抖音爆款文案分析报告已生成")


def _send_feishu_card(webhook: str, card: dict, fallback_text: str = ""):
    payload = {
        "msg_type": "interactive",
        "card": card,
    }
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        data = resp.json()
        if data.get("code") == 0 or data.get("StatusCode") == 0:
            logger.info("飞书卡片发送成功")
        else:
            logger.error(f"飞书返回错误: {data}")
    except Exception as e:
        logger.error(f"飞书通知失败: {e}")


# ── 钉钉 ─────────────────────────────────────────────────────────

def _format_text_msg(video: dict, analysis: dict = None) -> str:
    ts = datetime.fromtimestamp(video.get("create_time", 0)).strftime("%Y-%m-%d %H:%M")
    tags = " ".join([f"#{t}" for t in video.get("tags", [])[:5]])
    msg = (
        f"【新视频】{video.get('author_name', '')}\n"
        f"文案：{video.get('desc', '')[:100]}\n"
        f"标签：{tags or '无'}\n"
        f"点赞:{video.get('digg_count',0):,}  评论:{video.get('comment_count',0):,}  "
        f"分享:{video.get('share_count',0):,}\n"
        f"发布时间：{ts}\n"
    )
    if analysis:
        msg += (
            f"\n── AI文案分析 ──\n"
            f"钩子：{analysis.get('hook','')}\n"
            f"结构：{analysis.get('structure','')}\n"
            f"关键词：{analysis.get('keywords','')}\n"
            f"建议：{analysis.get('suggestion','')}\n"
        )
    return msg


def send_dingtalk(webhook: str, video: dict, analysis: dict = None):
    if not webhook:
        return
    payload = {"msgtype": "text", "text": {"content": _format_text_msg(video, analysis)}}
    try:
        requests.post(webhook, json=payload, timeout=10).raise_for_status()
        logger.info("钉钉通知发送成功")
    except Exception as e:
        logger.error(f"钉钉通知失败: {e}")


def send_wecom(webhook: str, video: dict, analysis: dict = None):
    if not webhook:
        return
    payload = {"msgtype": "text", "text": {"content": _format_text_msg(video, analysis)}}
    try:
        requests.post(webhook, json=payload, timeout=10).raise_for_status()
        logger.info("企业微信通知发送成功")
    except Exception as e:
        logger.error(f"企业微信通知失败: {e}")


def send_email(cfg: dict, video: dict, analysis: dict = None):
    if not cfg.get("enabled"):
        return
    text = _format_text_msg(video, analysis)
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = f"[抖音监控] {video.get('author_name','')} 发布新视频"
    msg["From"]    = cfg["sender"]
    msg["To"]      = cfg["receiver"]
    try:
        with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"]) as s:
            s.login(cfg["sender"], cfg["password"])
            s.sendmail(cfg["sender"], cfg["receiver"], msg.as_string())
        logger.info("邮件通知发送成功")
    except Exception as e:
        logger.error(f"邮件通知失败: {e}")


def notify_all(cfg: dict, video: dict, analysis: dict = None):
    """
    发现新视频时调用。
    飞书通知优先使用账号专属 webhook，无则回落到全局 notify.feishu_webhook。
    """
    n = cfg.get("notify", {})
    global_feishu = n.get("feishu_webhook", "")

    # 查找该视频作者的专属 webhook
    author = video.get("author_name", "")
    account_feishu = ""
    for account in cfg.get("accounts", []):
        if account.get("name") == author:
            account_feishu = account.get("feishu_webhook", "")
            break

    feishu_hook = account_feishu if account_feishu else global_feishu
    send_feishu_new_video(feishu_hook, video, analysis)
    send_dingtalk(n.get("dingtalk_webhook", ""), video, analysis)
    send_wecom(n.get("wecom_webhook", ""), video, analysis)
    send_email(n.get("email", {}), video, analysis)
