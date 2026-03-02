# 抖音监控 + AI文案分析工具

自动监控指定抖音博主的视频更新，用 DeepSeek AI 分析爆款文案规律，结果推送到飞书群。

## 功能

- 自动抓取博主最新视频（Playwright 反爬）
- DeepSeek AI 分析文案钩子、结构、关键词、模仿建议
- 飞书卡片推送（按博主分组，支持多群路由）
- SQLite 持久化存储，视频去重
- 定时监控 / 一次性抓取 / 手动批量分析 多种模式

---

## 快速开始

### 1. 配置

编辑 `config.yaml`：

```yaml
accounts:
  - name: "博主昵称"
    sec_uid: "MS4wLjABAAAA..."          # 抖音主页 URL 里的 sec_uid
    homepage: "https://www.douyin.com/user/MS4wLjABAAAA..."
    feishu_webhook: ""                   # 专属飞书群（留空用全局默认）

check_interval: 60                       # 检查间隔（分钟）

notify:
  feishu_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

ai_analyze:
  enabled: true
  openai_api_key: "sk-xxx"
  openai_base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
```

**如何获取 sec_uid：**
打开抖音网页版，进入博主主页，URL 里 `/user/` 后面那段 `MS4wLjAB...` 就是 sec_uid。

---

### 2. Docker 部署（推荐）

```bash
# 创建数据目录
mkdir data

# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

**目录结构：**
```
douyin_monitor/
├── config.yaml          # 配置文件（自行修改）
├── data/                # 数据目录（自动创建）
│   ├── monitor.db       # SQLite 数据库
│   └── monitor.log      # 运行日志
├── docker-compose.yml
└── Dockerfile
```

---

### 3. 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium

# 启动持续监控（默认每60分钟检查一次）
python monitor.py

# 只抓一次新视频
python monitor.py --once

# 分析所有未分析的视频（按点赞从高到低）
python monitor.py --analyze

# 只分析最高赞的 30 条
python monitor.py --analyze --top 30

# 强制重新分析所有视频（覆盖旧结果）
python monitor.py --reanalyze

# 查看数据库里的视频列表
python monitor.py --list
```

---

## 飞书多群路由

支持不同博主推到不同飞书群，在 `config.yaml` 的每个账号下填 `feishu_webhook`：

```yaml
accounts:
  - name: "博主A"
    sec_uid: "..."
    feishu_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/群A的token"

  - name: "博主B"
    sec_uid: "..."
    feishu_webhook: ""   # 留空 → 走全局 notify.feishu_webhook
```

- 有专属 webhook → 该博主的视频推到专属群
- 无专属 webhook → 推到全局默认群

---

## 推送效果

**新视频实时通知**（蓝色卡片）：
- 博主名 / 发布时间 / 文案内容 / 数据统计
- DeepSeek 自动分析：钩子话术 / 文案结构 / 关键词 / 模仿建议

**批量分析报告**（绿色卡片，按博主分组）：
- 每个博主一个区块，视频按点赞从高到低排列
- 尾部附爆款公式总结

---

## 技术栈

| 模块 | 技术 |
|------|------|
| 视频抓取 | Playwright + Chromium（绕过风控） |
| AI 分析 | LangChain + DeepSeek API |
| 数据存储 | SQLite |
| 通知推送 | 飞书 Webhook（交互卡片） |
| 定时任务 | schedule |
| 部署 | Docker + docker-compose |

---

## 常见问题

**Q: 抓取失败 / 返回空数据**
Playwright 会打开 Chromium 浏览器访问抖音，如果网络不稳定可能失败，重试即可。

**Q: DeepSeek 分析报错**
检查 `config.yaml` 里的 `openai_api_key` 是否正确，余额是否充足。

**Q: 飞书收不到消息**
确认 webhook URL 完整，飞书群机器人没有被禁用。

**Q: 如何增加监控账号**
在 `config.yaml` 的 `accounts` 列表里追加即可，修改后重启容器：
```bash
docker-compose restart
```
