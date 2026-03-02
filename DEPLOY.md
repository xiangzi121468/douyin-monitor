# 部署文档

> 抖音监控 + AI文案分析工具 — 生产环境部署指南

---

## 目录

1. [环境要求](#1-环境要求)
2. [服务器初始化](#2-服务器初始化)
3. [获取代码](#3-获取代码)
4. [配置文件](#4-配置文件)
5. [构建与启动](#5-构建与启动)
6. [验证部署](#6-验证部署)
7. [日常运维](#7-日常运维)
8. [更新升级](#8-更新升级)
9. [常见问题](#9-常见问题)

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Ubuntu 20.04+ / CentOS 7+ / Debian 11+ |
| CPU | 1 核以上 |
| 内存 | **1G 以上**（Playwright Chromium 需要） |
| 磁盘 | 10G 以上 |
| 网络 | 可访问抖音、DeepSeek API、飞书 |
| Docker | 20.10+ |
| Docker Compose | 1.29+ |

> 推荐：阿里云 / 腾讯云轻量应用服务器，2核2G，约 50-80元/月。

---

## 2. 服务器初始化

### 安装 Docker

```bash
# Ubuntu / Debian
curl -fsSL https://get.docker.com | sh

# 启动并设置开机自启
systemctl start docker
systemctl enable docker

# 验证安装
docker -v
```

### 安装 Docker Compose

```bash
# Ubuntu / Debian
apt install docker-compose -y

# 或手动安装最新版
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 验证
docker-compose -v
```

---

## 3. 获取代码

### 方式 A：Git 克隆（推荐）

```bash
# 克隆到服务器
git clone https://github.com/你的用户名/douyin-monitor.git /opt/douyin_monitor
cd /opt/douyin_monitor
```

### 方式 B：SCP 上传

```bash
# 在本地 Windows 执行
scp -r C:\Temp\douyin_monitor root@服务器IP:/opt/douyin_monitor
```

---

## 4. 配置文件

```bash
cd /opt/douyin_monitor

# 创建数据持久化目录
mkdir -p data
```

编辑 `config.yaml`，填入真实配置：

```bash
vim config.yaml
```

```yaml
accounts:
  # 要监控的抖音博主，可配置多个
  - name: "砖哥讲装修"
    sec_uid: "MS4wLjABAAAAiQrswXqDFBF..."   # 从抖音主页 URL 获取
    homepage: "https://www.douyin.com/user/MS4wLjABAAAA..."
    feishu_webhook: ""                        # 专属飞书群，留空用全局默认

  - name: "娟姐四合院"
    sec_uid: "MS4wLjABAAAA..."
    homepage: "https://www.douyin.com/user/MS4wLjABAAAA..."
    feishu_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/专属群token"

# 检查间隔（分钟），建议 30-60
check_interval: 60

notify:
  # 全局默认飞书群
  feishu_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/你的token"
  dingtalk_webhook: ""
  wecom_webhook: ""
  email:
    enabled: false

ai_analyze:
  enabled: true
  openai_api_key: "sk-你的DeepSeek密钥"
  openai_base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
```

> ⚠️ **注意**：`config.yaml` 包含 API 密钥，不要提交到公开 Git 仓库。

**获取 sec_uid 方法：**
1. 打开 [抖音网页版](https://www.douyin.com)
2. 进入要监控的博主主页
3. 复制地址栏 URL 中 `/user/` 后面的字符串（`MS4wLjAB...` 那段）

---

## 5. 构建与启动

```bash
cd /opt/douyin_monitor

# 首次构建镜像（需要 5-10 分钟，会下载 Python + Playwright）
docker-compose up -d --build

# 查看启动状态
docker-compose ps
```

期望输出：
```
      Name              Command        State    Ports
------------------------------------------------------
douyin-monitor   python monitor.py    Up
```

---

## 6. 验证部署

### 查看实时日志

```bash
docker-compose logs -f
```

正常日志示例：
```
2026-03-02 10:00:00 [INFO] 开始检查 2 个账号...
2026-03-02 10:00:00 [INFO] 检查账号: 砖哥讲装修
2026-03-02 10:00:05 [INFO] 打开主页: https://www.douyin.com/user/...
2026-03-02 10:00:12 [INFO] 拦截到 API 响应，视频数量: 20
2026-03-02 10:00:12 [INFO] 🆕 新视频: 装修避坑... | 👍12,345
2026-03-02 10:00:18 [INFO] AI分析完成: 7602970553095880635
2026-03-02 10:00:18 [INFO] 飞书卡片发送成功
```

### 手动触发一次抓取测试

```bash
docker-compose exec douyin-monitor python monitor.py --once
```

### 查看数据库数据

```bash
docker-compose exec douyin-monitor python monitor.py --list
```

---

## 7. 日常运维

### 常用命令

```bash
# 查看运行状态
docker-compose ps

# 实时查看日志（Ctrl+C 退出）
docker-compose logs -f

# 查看最近 100 行日志
docker-compose logs --tail=100

# 重启服务（修改 config.yaml 后执行）
docker-compose restart

# 停止服务
docker-compose down

# 停止并删除数据卷（慎用，会清空数据库）
docker-compose down -v
```

### 手动执行任务

```bash
# 立即抓取一次新视频
docker-compose exec douyin-monitor python monitor.py --once

# 分析所有未分析的视频并推飞书
docker-compose exec douyin-monitor python monitor.py --analyze

# 重新分析所有视频（包括已分析过的）
docker-compose exec douyin-monitor python monitor.py --reanalyze

# 只分析点赞最高的 30 条
docker-compose exec douyin-monitor python monitor.py --analyze --top 30

# 查看数据库视频列表
docker-compose exec douyin-monitor python monitor.py --list
```

### 查看数据文件

```bash
# 数据目录（宿主机）
ls -lh /opt/douyin_monitor/data/

# 数据库大小
du -sh /opt/douyin_monitor/data/monitor.db

# 查看日志文件
tail -f /opt/douyin_monitor/data/monitor.log
```

### 添加新监控账号

1. 编辑 `config.yaml`，在 `accounts` 下追加新账号
2. 重启容器：

```bash
docker-compose restart
```

---

## 8. 更新升级

```bash
cd /opt/douyin_monitor

# 拉取最新代码
git pull

# 重新构建并启动（--build 重新构建镜像）
docker-compose up -d --build

# 确认更新成功
docker-compose ps
docker-compose logs --tail=20
```

> 数据库文件在 `./data/` 目录，更新代码不会影响历史数据。

---

## 9. 常见问题

### Q: 构建时下载很慢

配置 Docker 国内镜像源：

```bash
# 编辑 daemon 配置
vim /etc/docker/daemon.json
```

```json
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://registry.docker-cn.com"
  ]
}
```

```bash
systemctl daemon-reload
systemctl restart docker
```

---

### Q: 抓取失败，日志报 "未获取到视频"

可能原因：
- 网络不通（服务器无法访问抖音）
- sec_uid 填错了

排查：
```bash
# 进入容器内手动测试
docker-compose exec douyin-monitor bash
python -c "from fetcher import get_user_videos; print(get_user_videos('你的sec_uid', 5))"
```

---

### Q: 飞书收不到消息

```bash
# 容器内手动测试 webhook
docker-compose exec douyin-monitor python -c "
import requests
r = requests.post('你的飞书webhook地址', json={'msg_type':'text','content':{'text':'测试'}})
print(r.json())
"
```

---

### Q: 内存不够，容器被 OOM 杀掉

编辑 `docker-compose.yml`，限制内存并防止 OOM：

```yaml
services:
  douyin-monitor:
    deploy:
      resources:
        limits:
          memory: 800m
    mem_swappiness: 0
```

或者升级服务器内存到 2G。

---

### Q: 修改了 config.yaml 不生效

```bash
# config.yaml 挂载为只读，修改后重启即可
docker-compose restart
```

---

## 目录结构说明

```
/opt/douyin_monitor/
├── config.yaml          # 配置文件（需手动维护）
├── docker-compose.yml   # 编排文件
├── Dockerfile           # 镜像构建文件
├── requirements.txt     # Python 依赖
├── monitor.py           # 主程序
├── fetcher.py           # 视频抓取（Playwright）
├── analyzer.py          # AI 文案分析（DeepSeek）
├── notifier.py          # 飞书推送
├── storage.py           # SQLite 数据存储
└── data/                # 运行时数据（持久化）
    ├── monitor.db       # 视频 + 分析结果数据库
    └── monitor.log      # 运行日志
```
