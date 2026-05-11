# XServer 免费 VPS 自动续期

这是一个用于 **自动检查并执行 XServer 免费 VPS 续期** 的项目，当前包含：

- 基于 Python + Playwright/Camoufox 的 XServer 免费 VPS 自动续期脚本
- 用于发送执行结果通知的包装脚本
- 一个支持 **多账号 / 多用户 / 代理 / 管理员控制** 的 Telegram Bot

适合希望把“检查是否到了可续期时间、到了就自动续期、并在 Telegram 中统一管理账号和查看结果”这件事自动化的人。

> **请仅用于你自己的 XServer 账号。**  
> 请不要把真实邮箱、密码、代理、Telegram Token、数据库、日志、截图等敏感信息提交到 GitHub。

---

## 项目功能

当前版本主要能力：

### 自动续期能力

- 自动打开 XServer 面板
- 自动登录 XServer
- 自动检查免费 VPS 是否进入可续期时间窗口
- 到了可续期时间时自动执行续期
- 未到时间时自动跳过，并返回明确结果
- 支持代理环境变量 `PROXY_SERVER`
- 支持保留截图与日志，便于排查失败原因

### Telegram Bot 能力

- 支持 Telegram Bot 管理多个 XServer 账号
- 支持用户添加、查看、删除、启用、禁用自己的账号
- 支持为单个账号设置签到时间
- 支持为单个账号设置代理
- 支持立即触发某个账号执行续期
- 支持多账号排队执行，避免同一用户并发打爆流程
- 支持管理员面板
- 支持管理员查看用户列表、账号数量、缺代理账号数量
- 支持管理员启用/禁用某个用户
- 支持敏感消息自动删除，降低邮箱/密码/代理泄露风险

### 通知能力

- 执行成功时发送简洁结果
- 执行失败时尽量附带失败原因
- 有截图时优先发送 Telegram 图片
- Telegram 发图失败时，可尝试图床回退

---

## 仓库结构

主要文件说明：

- `main.py`  
  核心浏览器自动化逻辑，负责登录 XServer、检查是否可续期、并执行续期。

- `run_xserver_notify.py`  
  续期执行包装器。会调用 `main.py`，整理结果、记录日志，并在配置了 Telegram 参数时发送通知。

- `tg_bot.py`  
  Telegram 机器人主程序，负责多账号管理、代理设置、任务排队、管理员功能等。

- `requirements.txt`  
  Python 依赖列表。

- `.env.example`  
  环境变量示例文件。

- `Dockerfile` / `entrypoint.sh` / `run-docker.sh`  
  Docker 运行相关文件。

---

## 运行环境要求

建议环境：

- Linux
- Python 3.10+
- 能稳定访问 XServer 面板
- 如需代理，准备可用的代理服务
- 无图形服务器上建议准备完整浏览器运行环境（例如 `xvfb` 等）

如果你是把它部署到 VPS 上长期运行，建议同时准备：

- systemd
- cron
- 可访问 Telegram API 的网络环境

---

## 安装部署

### 1）克隆仓库

```bash
git clone https://github.com/Yi-Zong/xserver-free-vps-auto-renew.git
cd xserver-free-vps-auto-renew
```

### 2）创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### 3）准备环境变量

```bash
cp .env.example .env
```

然后按需编辑 `.env`。

当前公开仓库中的 `.env.example` 只包含基础执行所需字段：

```env
# XServer 登录信息
EMAIL="your-email@example.com"
PASSWORD="your-password"

# Optional proxy for Playwright/Camoufox
PROXY_SERVER=""

# Optional Telegram notification for run_xserver_notify.py
TG_BOT_TOKEN=""
TG_CHAT_ID=""
ACCOUNT_LABEL=""
```

如果你要运行 Telegram Bot，通常还需要额外在运行环境中配置例如：

- `TG_BOT_TOKEN`
- `ADMIN_TG_ID`
- 以及你自己的其他部署参数

> 建议不要把真实 `.env` 提交到仓库。

---

## 运行方式

## 1. 直接运行核心续期脚本

```bash
python main.py
```

适合先手动验证浏览器自动化链路是否正常。

---

## 2. 运行通知包装脚本

```bash
python run_xserver_notify.py
```

这个脚本会：

- 调用 `main.py`
- 自动判断本次是否成功
- 自动判断今天是否需要续期
- 记录日志到 `logs/`
- 在配置了 Telegram 参数后发送结果通知
- 有截图时优先发送图片

---

## 3. 运行 Telegram Bot

```bash
python tg_bot.py
```

运行后，用户可以在 Telegram 中完成：

- 添加账号
- 设置代理
- 设置时间
- 立即签到
- 查看账号状态
- 删除账号
- 管理账号启用/禁用状态

管理员还可以进入管理面板执行用户管理。

---

## 代理说明

项目支持通过环境变量或 Bot 面板配置代理。

示例：

```env
PROXY_SERVER="socks5://user:pass@1.2.3.4:1080"
```

当前 Bot 侧约束为：

- 仅允许 `socks5://`
- 非管理员用户必须添加代理才可以签到

如果代理失效，常见现象包括：

- 页面打不开
- 登录超时
- 执行中断
- 返回代理失效 / 网络超时等错误

---

## Telegram Bot 使用说明

### 添加账号

按机器人提示发送：

```text
邮箱 密码 socks5代理
```

示例：

```text
xxxxxxx@gmail.com your_password socks5://user:pass@1.2.3.4:1080
```

### 账号能力

每个账号都支持：

- 立即签到
- 修改时间
- 设置代理
- 启用 / 禁用
- 删除账号

### 管理员能力

管理员可以：

- 查看用户总数
- 查看可用/禁用用户数量
- 查看总账号数
- 查看缺代理账号数
- 管理单个用户的启用状态

---

## 定时运行示例

可以使用 cron：

```cron
0 8 * * * cd /path/to/xserver-free-vps-auto-renew && . .venv/bin/activate && python run_xserver_notify.py >> logs/xserver.log 2>&1
```

如果你使用 Telegram Bot 方式长期运行，更常见的是使用 systemd 保持 `tg_bot.py` 常驻。

---

## Docker 说明

仓库里提供了：

- `Dockerfile`
- `entrypoint.sh`
- `run-docker.sh`

如果你希望容器化运行，可以基于这些文件自行构建。

不过对于需要频繁调试浏览器自动化、代理、Telegram、截图和日志问题的场景，**直接在 VPS 上用 Python 虚拟环境部署通常更容易排查问题**。

---

## 常见问题

### 1）脚本显示“今天无需续期”

这是正常情况。XServer 免费 VPS 不是每天都可以续期，只有进入它允许的时间窗口，脚本才会真正提交续期。

### 2）登录失败 / 超时 / 卡住

建议优先检查：

- 邮箱密码是否正确
- 是否开启了 XServer 两步验证（2FA）
- 代理是否可用
- VPS 网络是否能稳定访问 XServer
- 无头运行环境是否完整（如 `xvfb-run`）

### 3）Telegram 没收到通知

请检查：

- `TG_BOT_TOKEN` 是否正确
- `TG_CHAT_ID` 是否正确
- 机器人是否已经和目标用户发起过对话
- 服务器是否能访问 `https://api.telegram.org`

### 4）Bot 很慢、卡住、没反应

建议重点排查：

- 服务器网络
- IPv4 / IPv6 路由
- 代理质量
- XServer 页面可达性
- `xvfb-run` 是否安装完整
- 机器人日志中是否出现超时或子进程报错

### 5）截图 / 日志有敏感信息怎么办

不要公开上传。尤其不要把以下内容暴露到公开仓库：

- `.env`
- `bot_users.db`
- `logs/`
- 浏览器截图
- cookie / session / 代理信息
- 用户邮箱和密码

---

## 安全建议

请务必不要提交以下内容：

- `.env`
- 真实邮箱和密码
- Telegram Bot Token / Chat ID / Admin ID
- 代理账号信息
- `bot_users.db`
- 截图和日志
- 浏览器缓存、cookie、数据库等运行痕迹

如果你打算继续公开维护这个项目，建议优先检查：

- `.gitignore` 是否完整
- 示例配置是否脱敏
- 管理员 ID、图床地址等是否已通过环境变量注入

---

## 使用声明

本项目仅用于自动化处理你自己的 XServer 免费 VPS 续期流程。

请自行承担以下风险：

- 账号安全风险
- 代理可用性风险
- 自动化脚本失效风险
- 上游页面改版带来的兼容性风险

如果 XServer 页面结构发生变化，脚本可能需要同步调整。

---

## 仓库地址

GitHub：

<https://github.com/Yi-Zong/xserver-free-vps-auto-renew>

如果这个项目对你有帮助，欢迎 fork、修改和继续完善。 
