# -*- coding: utf-8 -*-
import sys, io, sqlite3, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = Path(__file__).parent / "monitor.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("""
    SELECT v.author_name, v.desc, v.digg_count, v.play_count,
           a.hook, a.structure, a.keywords, a.suggestion
    FROM videos v
    JOIN analysis a ON v.aweme_id = a.aweme_id
    WHERE v.author_name != 'AI装修达人' AND v.author_name != '智能家居小哥'
    ORDER BY v.digg_count DESC
    LIMIT 20
""")
rows = c.fetchall()
conn.close()

print("=" * 65)
print("  DeepSeek 爆款文案分析报告")
print("=" * 65)

for i, row in enumerate(rows, 1):
    author, desc, digg, play, hook, structure, keywords, suggestion = row
    print(f"\n【{i}】👍 {digg:,}  ▶ {play:,}")
    print(f"  原文案: {desc[:60]}...")
    print(f"  🪝 钩子: {hook}")
    print(f"  🏗  结构: {structure}")
    print(f"  🔑 关键词: {keywords}")
    print(f"  💡 模仿建议: {suggestion}")
    print(f"  {'─'*60}")

print("\n\n📌 综合爆款公式总结:")
print("─" * 65)
print("  高赞视频共同特征:")
print("  1. 标题必有数字  →  '14个地方' / '2万增项'")
print("  2. 痛点前置     →  '最怕什么？怕增项，怕扯皮'")
print("  3. 承诺透明     →  '透明化' / '手把手教你'")
print("  4. 带具体平方   →  '65㎡' / '110㎡' / '124㎡'")
print()
print("  ✅ 你可以直接复用的文案套路:")
print("  → 'AI帮你扫装修报价单，这X个增项让你多花X万'")
print("  → 'XX㎡装修，AI出5套方案，设计费省X万'")
print("  → '装修公司不告诉你的X个坑，AI2秒帮你找出来'")
