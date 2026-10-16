# xserver-renew-onvps

一个用于 **XServer 免费 VPS 自动续期** 的公开仓库，包含主脚本、Telegram 通知包装脚本，以及一份尽量完整、可直接落地的单文件说明。

这个仓库已经做过公开发布所需的基础安全清理：**不包含真实账号、密码、Bot Token、Chat ID、日志、截图或本地环境文件**。

---

## 功能

- 自动登录 XServer 面板
- 检查当前账号是否进入可续期窗口
- 在允许续期时自动提交续期
- 保存运行输出与日志
- 通过 Telegram 推送执行结果
- 通过 cron 定时自动运行

---

## 仓库结构

```text
xserver-renew-onvps/
├── README.md
├── package.json
├── env.runtime.example
├── run_xserver_notify.py
└── xserver/
    ├── .env.example
    ├── main.py
    ├── requirements.txt
    ├── Dockerfile
    ├── entrypoint.sh
    └── run-docker.sh
```

---

## 仓库中不会包含的内容

出于安全原因，以下内容不会进入仓库：

- 真实 XServer 邮箱
- 真实 XServer 密码
- 真实 Telegram Bot Token
- 真实 Telegram Chat ID
- 本地 `.env`
- 运行日志
- 截图文件
- 虚拟环境目录
- 调试缓存

因此，仓库 clone 下来后，需要你自己补齐运行时变量。

---

## 这套项目怎么跑

这套项目主要分成两部分：

### 1. `xserver/main.py`
核心自动续期脚本。

负责：
- 打开 XServer 页面
- 登录账号
- 进入续期页面
- 检查是否到了可续期时间
- 能续期时提交操作

### 2. `run_xserver_notify.py`
包装脚本。

负责：
- 调用主脚本执行
- 记录日志
- 读取执行结果
- 可选发送 Telegram 通知

你平时真正定时跑的，通常是这个：

```bash
python3 run_xserver_notify.py
```

---

## 配置说明

### 1. 配置 XServer 主脚本

先复制环境变量模板：

```bash
cp xserver/.env.example xserver/.env
```

然后填写：

```env
EMAIL=account@example.invalid
PASSWORD=your-xserver-password
PROXY_SERVER=
DEBUG=false
```

说明：

- `EMAIL`：XServer 登录邮箱
- `PASSWORD`：XServer 登录密码
- `PROXY_SERVER`：可选代理
- `DEBUG`：是否启用调试模式

### 2. 配置 Telegram 通知脚本

如果你想收到执行通知，还需要这些变量：

```env
TG_BOT_TOKEN=your-telegram-bot-token
TG_CHAT_ID=your-telegram-chat-id
EMAIL=account@example.invalid
PASSWORD=your-xserver-password
ACCOUNT_LABEL=account-1
```

可选图床变量：

```env
XSERVER_IMAGE_UPLOAD_URL=https://example.com/api/upload
XSERVER_IMAGE_UPLOAD_REFERER=https://example.com
XSERVER_IMAGE_STRATEGY_ID=
```

如果不需要图床回退，可以先不填这些可选项。

---

## 部署教程

默认假设：

- 系统是 **Debian / Ubuntu**
- 你有 root 权限
- 你要部署的是这个仓库：
  `https://github.com/Yi-Zong/xserver-renew-onvps`

### 1. 更新系统并安装基础依赖

```bash
apt update && apt upgrade -y
apt install -y git python3 python3-venv python3-pip xvfb curl unzip
```

这些依赖分别用于：

- `git`：拉代码
- `python3`：运行 Python
- `python3-venv`：创建虚拟环境
- `python3-pip`：安装依赖
- `xvfb`：无头图形环境，适合 VPS 跑浏览器脚本
- `curl` / `unzip`：辅助工具

### 2. 克隆仓库

建议放到固定目录，例如 `/opt`：

```bash
cd /opt
git clone https://github.com/Yi-Zong/xserver-renew-onvps.git
cd xserver-renew-onvps
```

如果你不想放 `/opt`，也可以换成自己的目录，比如 `/root`。

### 3. 初始化 Python 环境

```bash
cd xserver
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install
cd ..
```

如果后续提示缺少浏览器系统库，再按报错补装。

### 4. 创建日志目录

```bash
mkdir -p logs
```

---

## 使用方法

### 方式一：先手动执行主脚本

建议先手动测试一次，确认环境没问题：

```bash
cd xserver
. .venv/bin/activate
python main.py
```

如果运行失败，优先检查：

1. `xserver/.env` 是否写对
2. 依赖是否装完整
3. 浏览器依赖是否缺失
4. XServer 页面结构是否发生变化

### 方式二：执行带 Telegram 通知的包装脚本

```bash
cd ..
EMAIL='your-email' \
PASSWORD='your-password' \
ACCOUNT_LABEL='account-1' \
TG_BOT_TOKEN='your-bot-token' \
TG_CHAT_ID='your-chat-id' \
python3 run_xserver_notify.py
```

如果你不需要 Telegram 通知，也可以只跑主脚本，不用这个包装脚本。

---

## cron 配置

### 最简单可用版

编辑 crontab：

```bash
crontab -e
```

加入示例：

```cron
0 8 * * * cd /opt/xserver-renew-onvps/xserver && TG_BOT_TOKEN='your-bot-token' TG_CHAT_ID='your-chat-id' EMAIL='your-email' PASSWORD='your-password' ACCOUNT_LABEL='account-1' /usr/bin/python3 /opt/xserver-renew-onvps/run_xserver_notify.py >> /opt/xserver-renew-onvps/logs/account1.log 2>&1
```

### 这条 cron 的含义

- `0 8 * * *`：每天早上 8 点执行
- `cd /opt/xserver-renew-onvps/xserver`：切换到项目目录
- `TG_BOT_TOKEN=...`：注入 Telegram bot token
- `TG_CHAT_ID=...`：注入 Telegram chat id
- `EMAIL=...`：XServer 账号邮箱
- `PASSWORD=...`：XServer 账号密码
- `ACCOUNT_LABEL=...`：账号备注名
- `/usr/bin/python3 /opt/xserver-renew-onvps/run_xserver_notify.py`：执行包装脚本
- `>> ...log 2>&1`：把标准输出和错误输出都写入日志

### 推荐版：使用 env 文件

不建议长期把密码直接写在 crontab 里。更推荐单独维护一个 env 文件。

创建运行时变量文件：

```bash
nano /opt/xserver-renew-onvps/.env.runtime
```

写入：

```env
TG_BOT_TOKEN=your-telegram-bot-token
TG_CHAT_ID=your-telegram-chat-id
EMAIL=account@example.invalid
PASSWORD=your-xserver-password
ACCOUNT_LABEL=account-1
```

然后把 cron 改成：

```cron
0 8 * * * . /opt/xserver-renew-onvps/.env.runtime && cd /opt/xserver-renew-onvps/xserver && /usr/bin/python3 /opt/xserver-renew-onvps/run_xserver_notify.py >> /opt/xserver-renew-onvps/logs/account1.log 2>&1
```

### 多账号示例

如果你有多个 XServer 账号，建议：

- 每个账号分开一条 cron
- 每个账号分开一个日志文件
- 每个账号使用不同的 `ACCOUNT_LABEL`
- 多账号错峰运行，不要同一秒一起跑

示例：

```cron
# account 1
0 8 * * * . /opt/xserver-renew-onvps/.env.runtime.account1 && cd /opt/xserver-renew-onvps/xserver && /usr/bin/python3 /opt/xserver-renew-onvps/run_xserver_notify.py >> /opt/xserver-renew-onvps/logs/account1.log 2>&1

# account 2
30 8 * * * . /opt/xserver-renew-onvps/.env.runtime.account2 && cd /opt/xserver-renew-onvps/xserver && /usr/bin/python3 /opt/xserver-renew-onvps/run_xserver_notify.py >> /opt/xserver-renew-onvps/logs/account3.log 2>&1
```

对应 env 文件内容大致如下：

```env
TG_BOT_TOKEN=your-telegram-bot-token
TG_CHAT_ID=your-telegram-chat-id
EMAIL=account@example.invalid
PASSWORD=account-password
ACCOUNT_LABEL=account-1
```

### 推荐执行时间

你可以按自己的节奏安排，比如：

- 每天 1 次
- 每天 2 次
- 多账号错峰执行

更稳妥的做法是错开 10~30 分钟，例如：

- 账号 1：08:00
- 账号 2：08:30
- 账号 3：09:00

### 如何检查 cron 是否生效

#### 查看当前 cron

```bash
crontab -l
```

#### 查看日志

```bash
tail -f /opt/xserver-renew-onvps/logs/account1.log
```

#### 看 Telegram 是否收到消息

如果启用了通知，cron 成功执行后通常会有推送。

### 一键追加 cron 的方式

如果你喜欢命令式写法，也可以：

```bash
( crontab -l 2>/dev/null; echo "0 8 * * * . /opt/xserver-renew-onvps/.env.runtime && cd /opt/xserver-renew-onvps/xserver && /usr/bin/python3 /opt/xserver-renew-onvps/run_xserver_notify.py >> /opt/xserver-renew-onvps/logs/account1.log 2>&1" ) | crontab -
```

---

## 常见问题

### 为什么手动运行正常，cron 却失败？

通常是因为 cron 环境更干净，容易缺：

- 完整路径
- 环境变量
- 虚拟环境激活
- 日志输出重定向

### 为什么 cron 里找不到命令？

因为 cron 环境很干净，建议：

- 使用完整路径，比如 `/usr/bin/python3`
- 使用完整项目路径
- 不要依赖当前 shell 配置

### 为什么日志里什么都没有？

先确认日志目录是否存在：

```bash
mkdir -p /opt/xserver-renew-onvps/logs
```

### 为什么脚本会突然失效？

因为这类自动化高度依赖网页结构。如果 XServer 修改了：

- 登录页结构
- 按钮文字
- CAPTCHA 流程
- Turnstile 验证逻辑

脚本就需要同步调整。

### 为什么不能把密码或 Token 直接放进仓库？

因为这是公开仓库。一旦提交到 GitHub，敏感信息就可能被索引、缓存或泄露。

---

## 安全建议

- 不要把真实密码提交到 GitHub
- 不要把 `.env.runtime` 提交到 GitHub
- 不要把 bot token 写死到源码里
- 如果变量曾经泄露，建议立刻更换

---

## 建议

推荐做法是：

1. **公开仓库只放代码和文档**
2. **所有 secrets 都放在运行环境中**
3. 使用 `.env`、`.env.runtime`、cron 变量或 CI secrets 管理敏感信息
4. 定期检查日志与截图，确认续期链路仍然可用
