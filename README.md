# 吃药提醒系统

## 目录结构

```
pill_reminder/code/
├── config.yaml          # 配置文件
├── db.py                # SQLite 数据库模块
├── feishu.py            # 飞书 Bot API 模块
├── scheduler.py         # 无状态调度器（cron 调用）
├── webhook.py           # Python Webhook 服务（内部确认接口）
├── requirements.txt     # Python 依赖
├── state.db             # SQLite 数据库
├── logs/                # 日志目录
├── node/
│   ├── receiver.js      # Node.js 长连接服务（接收飞书事件）
│   ├── package.json     # Node.js 依赖
│   └── node_modules/    # Node.js 包
└── systemd/
    ├── pill-reminder.service        # systemd 服务（Python Webhook）
    └── pill-reminder-node.service  # systemd 服务（Node.js 长连接）
```

## 架构

```
cron (每分钟)
    ↓
scheduler.py  ← 检查是否到达 10:00/15:00/20:00
    ↓
SQLite (state.db)
    ↓
飞书 Bot API → 发送提醒

用户回复 "吃过药了"
    ↓
Node.js 长连接 (receiver.js) ← 接收飞书事件
    ↓
Python /internal/confirm 接口 ← 确认 session
    ↓
飞书 Bot API → 发送 "✅ 已确认吃药"
```

## 配置项说明 (config.yaml)

```yaml
feishu:
  app_id: "cli_xxx"              # 飞书应用 ID
  app_secret: "xxx"              # 飞书应用密钥
  user_id: "ou_xxx"              # 消息接收用户的 open_id

reminder:
  slots:                          # 提醒时间点
    - "10:00"
    - "15:00"
    - "20:00"
  interval_minutes: 5             # 循环提醒间隔
  max_duration_hours: 12         # session 最大持续时间

confirmation:
  valid_text: "吃过药了"          # 确认文本（必须精确匹配）
```

## 服务管理（systemd）

### 启动服务
```bash
sudo systemctl start pill-reminder
sudo systemctl start pill-reminder-node
```

### 查看状态
```bash
sudo systemctl status pill-reminder
sudo systemctl status pill-reminder-node
```

### 停止服务
```bash
sudo systemctl stop pill-reminder
sudo systemctl stop pill-reminder-node
```

### 重启服务
```bash
sudo systemctl restart pill-reminder
sudo systemctl restart pill-reminder-node
```

### 开机启动（已配置）
```bash
sudo systemctl enable pill-reminder
sudo systemctl enable pill-reminder-node
```

## 手动启动服务（不使用 systemd）

```bash
# Python Webhook 服务
python3 /home/snail/pill_reminder/code/webhook.py &

# Node.js 长连接服务
cd /home/snail/pill_reminder/code/node
node receiver.js &
```

## cron（已配置）

```
* * * * * flock -n /tmp/pill-reminder.lock python3 /home/snail/pill_reminder/code/scheduler.py
```

## 日志位置

- `logs/reminder.log` - scheduler 日志
- `logs/webhook.log` - Python 服务日志
- `logs/receiver.log` - Node.js 长连接日志
- `logs/cron.log` - cron 执行日志

## 设计原则

- **无 while True 循环**：所有状态保存在 SQLite
- **单 active session**：同一时刻只允许一个活跃 session
- **精准匹配**：只有精确回复「吃过药了」才算确认
- **flock 防并发**：cron 使用 flock 防止多实例
- **长连接接收**：使用 Node.js WSClient 接收飞书事件，无需公网地址

## 飞书开放平台配置

1. 应用 → 事件与回调 → 订阅方式选择「**长连接**」
2. 添加事件：`im.message.receive_v1`
3. 不需要配置公网回调地址

## 查看进程 ID
```bash
ps aux | grep -E "webhook|receiver" | grep -v grep
```