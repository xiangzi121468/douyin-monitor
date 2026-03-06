# 精选联盟热销商品抓取配置指南

> 本文档说明如何配置抖音 Cookie，实现自动抓取精选联盟热销商品榜并推送飞书。

---

## 功能说明

抓取**抖音精选联盟**平台的热销商品数据，包括：

| 数据字段 | 说明 |
|---------|------|
| 商品名称 | 完整标题 |
| 售价 | 单位：元 |
| 月销量 | 近30天销售量 |
| 佣金比例 | 推广佣金百分比 |
| 商品链接 | 可直接跳转 |

支持按类目筛选：

| 类目名称 | 类目 ID |
|---------|--------|
| 家居家装（默认） | 50 |
| 全部 | 0 |
| 家电 | 161 |
| 建材 | 1437 |
| 服饰 | 20 |
| 美妆 | 18 |

---

## 前置条件

> ⚠️ 精选联盟需要**创作者账号**才能访问，个人账号可能无权限。
> 如未开通创作者，可先申请：[抖音创作者中心](https://creator.douyin.com)

---

## 第一步：获取抖音登录 Cookie

### Chrome / Edge 浏览器操作步骤

1. 打开 [https://www.douyin.com](https://www.douyin.com) 并**登录**你的抖音账号

2. 按 `F12` 打开开发者工具

3. 点击顶部 **Application（应用）** 选项卡

4. 左侧展开 **Cookies** → 点击 `https://www.douyin.com`

5. 在右侧表格中找到以下字段并逐一复制 Value 值：

   | Cookie 名 | 说明 | 是否必须 |
   |-----------|------|---------|
   | `sessionid` | 登录会话 ID | ✅ 必须 |
   | `ttwid` | 设备标识 | ✅ 必须 |
   | `passport_csrf_token` | 防跨站令牌 | ✅ 必须 |
   | `sid_guard` | 会话守护 | 建议填写 |

   **示例格式（仅作参考，非真实值）：**
   ```
   sessionid     = abc123def456...（很长的字符串）
   ttwid         = 1%7Cxxxxxxxx%7C...
   passport_csrf_token = abcdef123456
   ```

6. 如果找不到 Application 选项卡，点击工具栏末尾的 `>>` 箭头展开

---

## 第二步：填入 config.yaml

打开项目目录下的 `config.yaml`，找到 `douyin_cookies` 字段填入：

```yaml
douyin_cookies:
  sessionid: "abc123def456..."
  ttwid: "1%7Cxxxxxxxx%7C..."
  passport_csrf_token: "abcdef123456"
  sid_guard: "abc123%7C..."     # 可选
```

---

## 第三步：运行抓取

```bash
# 抓取家居家装类目热销榜（默认）
python monitor.py --products

# 指定其他类目
python monitor.py --products --category 全部
python monitor.py --products --category 家电
python monitor.py --products --category 建材

# Docker 环境
docker-compose exec douyin-monitor python monitor.py --products
```

---

## 飞书推送效果

运行成功后，飞书群收到**紫色卡片**，格式如下：

```
🛒 精选联盟热销榜 · 家居家装
─────────────────────────
类目：家居家装   共 20 个商品   更新时间：2026-03-02 18:30

1. 免打孔浴室置物架卫生间壁挂...
   💰 ¥29.9   🔥 月销 5万+   佣金 20.0%
   🔗 查看商品

2. 懒人沙发榻榻米折叠床单人...
   💰 ¥199.0   📈 月销 8,234   佣金 15.5%
   🔗 查看商品
...
```

---

## 定时自动抓取

在 `config.yaml` 中开启自动商品监控：

```yaml
# 每天早上9点自动抓取热销榜（需配合定时任务）
product_monitor:
  enabled: true
  category: "家居家装"
  cron: "0 9 * * *"   # 每天09:00执行（服务器 crontab 配置）
```

或者用 Linux crontab 定时执行：

```bash
# 编辑 crontab
crontab -e

# 每天早9点抓一次热销榜
0 9 * * * cd /opt/douyin_monitor && docker-compose exec -T douyin-monitor python monitor.py --products
```

---

## 常见问题

### Q: 运行后显示"未获取到商品数据"

可能原因：
1. Cookie 过期（重新登录获取）
2. 账号没有精选联盟权限（需申请创作者权限）
3. 网络问题（服务器无法访问 jinritemai.com）

排查方式：
```bash
# 查看详细日志
python monitor.py --products 2>&1 | head -50
```

---

### Q: Cookie 多久过期？

- `sessionid` 通常 **7-30 天**有效
- 过期后重新登录抖音网页版，重新获取 Cookie

---

### Q: 如何知道我有精选联盟权限？

打开 [https://haohuo.jinritemai.com](https://haohuo.jinritemai.com)，如果可以正常访问商品列表页面，说明有权限。

如果跳转到开通页面，需要先完成创作者认证。

---

## 安全提醒

- ⚠️ Cookie 等同于账号登录凭证，**不要分享给他人**
- ⚠️ 不要将含 Cookie 的 `config.yaml` 提交到公开 Git 仓库
- ✅ 项目 `.gitignore` 已默认排除 `config.yaml`
