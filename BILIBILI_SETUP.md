# B站监控配置指南

> 本文档说明如何将 B站 UP 主加入监控，实现视频自动抓取 + AI 分析 + 飞书推送。

---

## 目录

1. [获取 UP 主 UID](#1-获取-up-主-uid)
2. [获取 SESSDATA（登录凭证）](#2-获取-sessdata登录凭证)
3. [配置 config.yaml](#3-配置-configyaml)
4. [验证配置](#4-验证配置)
5. [注意事项](#5-注意事项)

---

## 1. 获取 UP 主 UID

UID 是 B站每个用户的唯一数字 ID，在 UP 主主页 URL 里可以直接找到。

**步骤：**

1. 打开浏览器，进入要监控的 UP 主主页
2. 查看地址栏，格式为：

   ```
   https://space.bilibili.com/3546876158675230
                              ↑
                         这串数字就是 UID
   ```

3. 复制 `/` 后面的纯数字部分（如 `3546876158675230`）

> 💡 如果 URL 后面有参数（如 `?spm_id_from=...`），只取 `?` 前面的数字部分。

---

## 2. 获取 SESSDATA（登录凭证）

B站接口需要登录态才能稳定访问，SESSDATA 是浏览器登录后保存的 Cookie 凭证。

**步骤：**

### Chrome / Edge 浏览器

1. 打开 [https://www.bilibili.com](https://www.bilibili.com) 并**登录**你的 B站账号

2. 按 `F12` 打开开发者工具

3. 点击顶部菜单 **Application**（应用）选项卡

   > 如果看不到 Application，点击 `>>` 展开更多选项

4. 在左侧找到 **Cookies** → 展开 → 点击 `https://www.bilibili.com`

5. 在右侧列表中找到名称为 **SESSDATA** 的行

6. 双击 **Value** 列的值，全选并复制

   ```
   示例格式：
   68c5dedb%2C1788000141%2Ce8aec%2A31CjD0g40yD...（很长的一串）
   ```

### Firefox 浏览器

1. 登录 bilibili.com
2. 按 `F12` → **Storage（存储）** → **Cookies** → `https://www.bilibili.com`
3. 找到 **SESSDATA**，复制其 Value 值

---

## 3. 配置 config.yaml

打开项目根目录下的 `config.yaml`，在 `accounts` 列表中添加 B站账号：

```yaml
accounts:
  # ── 已有的抖音账号（保持不变）──
  - name: "砖哥讲装修"
    platform: "douyin"
    sec_uid: "MS4wLjABAAAA..."
    feishu_webhook: ""

  # ── 新增 B站账号 ──────────────────────────────
  - name: "即梦AI生成视频"          # 自定义备注名，用于飞书推送显示
    platform: "bilibili"            # 固定填 bilibili
    uid: "3546876158675230"         # 第1步获取的 UP 主 UID
    homepage: "https://space.bilibili.com/3546876158675230"
    sessdata: "你的SESSDATA值"      # 第2步获取的登录凭证
    feishu_webhook: ""              # 专属飞书群（留空则用全局默认）
```

**字段说明：**

| 字段 | 是否必填 | 说明 |
|------|---------|------|
| `name` | ✅ 必填 | 任意备注名，显示在飞书通知中 |
| `platform` | ✅ 必填 | 固定填 `bilibili` |
| `uid` | ✅ 必填 | UP 主的 B站 UID（纯数字） |
| `homepage` | 选填 | UP 主主页链接（仅作备注） |
| `sessdata` | ⚠️ 强烈建议 | 不填则匿名访问，容易触发频率限制 |
| `feishu_webhook` | 选填 | 该 UP 主专属飞书群，留空用全局默认 |

---

## 4. 验证配置

### 方式一：快速测试（推荐）

```bash
# 立即抓取一次，验证 B站账号是否能正常获取数据
python monitor.py --once
```

**正常日志示例：**
```
[INFO] 检查账号: 即梦AI生成视频 [bilibili]
[INFO] B站 WBI 签名获取成功
[INFO] B站共获取 20 条视频
[INFO] 🆕 新视频: 【全50集】AI短剧制作教程... | 👍7,036
[INFO] AI分析完成: bili_BV1hrAbzZEHg
[INFO] 飞书卡片发送成功
```

### 方式二：Docker 环境

```bash
# 修改 config.yaml 后重启容器
docker-compose restart

# 查看日志验证
docker-compose logs -f
```

---

## 5. 注意事项

### ⚠️ SESSDATA 有效期

- SESSDATA 通常有效期为 **6 个月**，过期后需要重新登录获取
- 过期后日志会出现 `code=-101` 或 `code=-400` 错误
- 更新方式：重新登录 B站 → 按上述步骤获取新的 SESSDATA → 更新 `config.yaml` → 重启

### ⚠️ 请勿频繁请求

- 程序已内置请求间隔，正常使用不会触发风控
- 不要将 `check_interval` 设置过小（建议 **≥ 30 分钟**）

### ⚠️ SESSDATA 安全

- SESSDATA 相当于你的 B站登录凭证，**不要分享给他人**
- 不要将含有 SESSDATA 的 `config.yaml` 提交到公开 Git 仓库
- 项目的 `.gitignore` 已默认排除 `config.yaml`

### B站 vs 抖音 数据差异

| 字段 | 抖音 | B站 |
|------|------|-----|
| 点赞数 | `digg_count` | 暂无（用播放数代替）|
| 播放数 | `play_count` | `play_count` |
| 视频 ID | `aweme_id` | `bili_BV1xxx`（加 `bili_` 前缀）|
| 抓取方式 | Playwright 浏览器 | HTTP API（更快更稳定）|

---

## 常见报错

| 错误 | 原因 | 解决方法 |
|------|------|---------|
| `code=-799 请求过于频繁` | 匿名访问被限速 | 配置 `sessdata` |
| `code=-101` | SESSDATA 失效 | 重新登录获取新的 SESSDATA |
| `code=-400` | 请求参数异常 | 检查 UID 是否正确（纯数字） |
| `抓取到 0 条视频` | UP 主未发布视频 / UID 错误 | 确认 UID 和主页是否一致 |
| `获取 WBI key 失败` | 网络不通 | 检查服务器能否访问 bilibili.com |

---

## 完整 config.yaml 示例

```yaml
accounts:
  # 抖音账号
  - name: "砖哥讲装修"
    platform: "douyin"
    sec_uid: "MS4wLjABAAAAiQrswXqDFBF..."
    homepage: "https://www.douyin.com/user/MS4wLjABAAAA..."
    feishu_webhook: ""

  # B站账号
  - name: "即梦AI生成视频"
    platform: "bilibili"
    uid: "3546876158675230"
    homepage: "https://space.bilibili.com/3546876158675230"
    sessdata: "68c5dedb%2C1788000141%2Ce8aec..."
    feishu_webhook: ""

check_interval: 60

notify:
  feishu_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/你的token"

ai_analyze:
  enabled: true
  openai_api_key: "sk-你的DeepSeek密钥"
  openai_base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
```
