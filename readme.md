# XServer 免费 VPS 多账号续期：生产代码备份与部署整改手册

本仓库替换为 2026-10-16 本机 `/opt/xserver` 的脱敏代码快照。它是**生产代码备份**，不是完整磁盘镜像；真实账号、Token、Cookie、截图、运行日志、数据库、虚拟环境和浏览器二进制均不上传。旧仓库提交历史保留，可以回滚。

> 自动续期不能保证平台永远允许续期。只对本人有权管理的账号操作，遵守平台规则。遇到人机验证使用官方人工或无障碍验证流程；本次备份不新增、优化或验证自动绕过机制。当前代码可能在验证策略变化后停止工作，不能以登录成功或进程退出 0 代替官网续期成功。

## 1. 目录与完整性

- `app/`：现用 Python 核心、通知 wrapper、多账号调度及现场保留的辅助源码。
- `systemd/`：生产服务和下午/晚间定时器快照。
- `archive/`：历史版本、旧入口和迁移源码，只作追溯，**不要一起部署或执行**。
- `docs/source-inventory.json`：源文件到仓库路径映射。
- `docs/`：系统依赖、浏览器版本等现场资料。
- `requirements-production.txt`：现场 Python 依赖版本及通知失败图片所需 Pillow。
- `tests/test_offline.py`：不登录、不续期、不发通知的离线回归。
- `NOTICE.md`：来源及许可边界；未发现明确 LICENSE，不擅自声明开源许可。

秘密的默认值已去除或占位替换。因此这是**完整可追溯的脱敏源码备份**，不是原机器逐字节含凭据克隆。历史代码不等同当前推荐部署入口。

## 2. 当前执行链路

```text
systemd timer（北京时间 14:00 / 20:00）
  → xserver-checkin@afternoon / @evening
  → run_xserver_random_window.py
  → 为每个账号选随机时间、排序、等待、串行执行
  → run_xserver_notify.py
  → xvfb-run + app/.venv/bin/python + main.py
  → 核对官网业务结果、生成截图、Telegram sendPhoto
```

窗口为北京时间 **14:00–16:00、20:00–22:00**。不要把所有账号同时批量启动。随机计划使用 `Asia/Shanghai`；晚于窗口开始启动时只在剩余时段抽样，晚于结束启动则拒绝。计划优先选不同的秒偏移，不是固定最小间隔保证；账号过多、网络慢时串行任务可能延迟到计划时间以后，不能保证所有任务在窗口结束前完成。

## 3. 新机器安装

以下为 **Debian/Ubuntu + systemd** 路线，生产快照为 Debian 13 ARM64。其他发行版包名可能不同。仅离线回归已在本次备份中验证；没有声称在另一台空白机器全流程安装并真实续期验收。

### 3.1 克隆及基础依赖

```bash
git clone https://github.com/Yi-Zong/xserver-free-vps-auto-renew.git
cd xserver-free-vps-auto-renew
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip xvfb xauth fonts-noto-cjk ca-certificates
```

浏览器还依赖 GTK、音频及图形运行库：Debian 13 对照 `docs/system-package-versions.txt` 安装 `libgtk-3-0t64`、`libasound2t64`；Debian 12 常对应 `libgtk-3-0`、`libasound2`。不要盲目复制其他系统包名，也不要为了此项目升级或删除其他生产程序的依赖。

```bash
sudo install -d -m 700 /opt/xserver/app /opt/xserver/logs /opt/xserver/runs
sudo cp -a app/. /opt/xserver/app/
sudo cp requirements-production.txt /opt/xserver/
sudo python3 -m venv /opt/xserver/app/.venv
sudo /opt/xserver/app/.venv/bin/python -m pip install -r /opt/xserver/requirements-production.txt
sudo /opt/xserver/app/.venv/bin/python -m camoufox fetch
```

依赖锁是现场快照，不代表所有系统都能安装这些版本。如果某个轮子或历史版本不可获取，应记录明确错误，在独立环境验证兼容版本，不修改正在工作的生产 venv。Camoufox 下载必须与运行服务使用同一用户的缓存；示例服务为 root。不要清理仍被其他程序使用的 Camoufox/Playwright 缓存。

### 3.2 多账号配置

```bash
sudo cp /opt/xserver/app/xserver_accounts.example.json /opt/xserver/app/xserver_accounts.json
sudo chmod 600 /opt/xserver/app/xserver_accounts.json
sudo nano /opt/xserver/app/xserver_accounts.json
```

结构必须是数组，示例：

```json
[
  {"email":"account1@example.invalid","password":"REPLACE_LOCALLY","label":"account1","log":"xserver_account1.log"},
  {"email":"account2@example.invalid","password":"REPLACE_LOCALLY","label":"account2","log":"xserver_account2.log"},
  {"email":"account3@example.invalid","password":"REPLACE_LOCALLY","label":"account3","log":"xserver_account3.log"}
]
```

`email`、`password` 是必需字段，`label`、`log` 建议设置且彼此不同。日志名只用简单文件名，不含路径穿越。新增账号只需添加数组条目；删除账号先确认没有正在执行的窗口任务。真实邮箱可能出现在本地日志和通知中，必须保护文件权限。

### 3.3 Telegram 通知

```bash
sudo cp /opt/xserver/app/.env.runtime.example /opt/xserver/app/.env.runtime
sudo chmod 600 /opt/xserver/app/.env.runtime
sudo nano /opt/xserver/app/.env.runtime
```

```dotenv
TG_BOT_TOKEN=YOUR_BOT_TOKEN
TG_CHAT_ID=YOUR_CHAT_ID
```

先主动与自己的 Telegram Bot 建立对话。通知配置与账号密码不提交 Git。当前通知发送图片并显示完整邮箱，分别展示“脚本运行”和“账号续期”；不在通知文案展示到期日期、内部状态码或重复日期箭头。Telegram `ok=true` 和消息 ID 才是接口确认送达，不等于用户已阅读。

wrapper 默认走直连，清理子进程代理变量；不要在部署时擅自加入代理。生产业务与通知接收回执分开判断：业务成功但发图失败仍可使 wrapper 返回非零。

## 4. 部署前验证与单账号验收

先在仓库目录执行不产生业务副作用的测试：

```bash
python3 -m unittest discover -s tests -v
```

不要用运行 `main.py` 作为依赖测试，它会进入真实登录和续期流程。也不要运行 `run_xserver_all_now.py` 测试某一个账号，它会执行全部账号。

**以下单账号命令会实际登录、可能续期并发送通知，仅在明确授权时执行一次：**

```bash
sudo bash
cd /opt/xserver/app
set -a
. ./.env.runtime
set +a
read -r -p '账号邮箱: ' EMAIL
read -r -s -p '账号密码: ' PASSWORD; printf '\n'
export EMAIL PASSWORD
export ACCOUNT_LABEL=manual-one-account
umask 077
flock -n /run/lock/xserver-manual.lock /opt/xserver/app/.venv/bin/python run_xserver_notify.py
unset PASSWORD EMAIL
exit
```

先检查两个窗口 service 是否正在执行，不要在自动窗口期间手动运行。上面的手动锁只保护采用同一把锁的手动命令，**并不会自动锁住原版 systemd 调度**。不把密码作为命令行参数或写入 shell 历史。

### 三层结果判断

1. **脚本层**：浏览器正常运行、核心退出状态和结果文件存在。
2. **业务层**：官网明确续期成功，重新进入详情，前后期限确实变化；未到窗口只能算“暂无需续期”，不是新增续期。
3. **通知层**：Telegram 确认 `ok=true` 并返回消息 ID。通知失败不能反向认定官网续期失败，更不能立即重复续期。

## 5. 系统级定时器

先检查旧 cron 和旧 timer，避免一个账号被多套入口同时执行。不要同时启用 archive 内的工作流和当前 systemd。

```bash
sudo install -m 644 systemd/xserver-checkin@.service /etc/systemd/system/
sudo install -m 644 systemd/xserver-checkin-afternoon.timer /etc/systemd/system/
sudo install -m 644 systemd/xserver-checkin-evening.timer /etc/systemd/system/
```

模板服务使用 `/usr/bin/python3` 启动标准库调度器，核心由 wrapper 调用 `/opt/xserver/app/.venv/bin/python`。可在**新部署机**增加独立解释器 drop-in，使 wrapper 的 Pillow 等依赖也一致：

```bash
sudo install -d /etc/systemd/system/xserver-checkin@.service.d
sudo tee /etc/systemd/system/xserver-checkin@.service.d/python.conf >/dev/null <<'EOF'
[Service]
ExecStart=
ExecStart=/opt/xserver/app/.venv/bin/python /opt/xserver/app/run_xserver_random_window.py %i
EOF
sudo systemd-analyze verify /etc/systemd/system/xserver-checkin@.service /etc/systemd/system/xserver-checkin-afternoon.timer /etc/systemd/system/xserver-checkin-evening.timer
sudo systemctl daemon-reload
sudo systemctl enable --now xserver-checkin-afternoon.timer xserver-checkin-evening.timer
sudo systemctl list-timers --all 'xserver-checkin*'
```

这些命令仅作为部署说明，本次备份**没有在生产机执行**。`daemon-reload` 可能使其他带随机延迟的 timer 重算时间，变更后必须核验。启用带 Persistent 的定时器可能补触发，先读 unit 并检查当前时间，不能把“启用”当成纯静态操作。

不要额外启用 `xserver-checkin-now.service`；它是全账号立即执行入口快照，不是必须的每日定时器。

## 6. 日志与排查

```bash
systemctl status xserver-checkin@afternoon.service xserver-checkin@evening.service --no-pager
journalctl -u xserver-checkin@afternoon.service -u xserver-checkin@evening.service --since today --no-pager
systemctl list-timers --all 'xserver-checkin*'
```

任务长期 `activating` 可能正在等待随机时间，不应直接判故障。调度日志位于 `/opt/xserver/app/logs/` 和 `/opt/xserver/logs/`，运行证据在 `/opt/xserver/runs/`，包含截图、官网前后详情、核心输出和 `notification-result.json`。

- `NOT_ELIGIBLE`：官网尚未开放续期，不要为了“成功”重复提交。
- 登录失败或官方安全验证未完成：保留现场，使用官方人工/无障碍流程；不要空 token 重试。
- 图片 API 返回异常：检查真实请求契约与网络；不要把 HTTP 200 当成有效识别结果。
- Telegram 失败：检查 Bot、Chat ID、权限及回执；不要因此重复业务提交。
- Camoufox `Screen` 导入失败：核对 `browserforge.fingerprints.Screen` 与依赖版本，不能盲目升级整个生产环境。
- 窗口结束拒绝执行：等待下一窗口或明确授权单账号执行，不把错误解释为账号被封。
- venv 路径迁移：检查 shebang 和硬编码 `/opt/xserver/app`，不能只移动文件夹。

## 7. 图片接口契约与隐私

现用核心的 `CAPTCHA_API` 请求发送的是**完整 `data:image/...;base64,...` 字符串原始文本**，不是 JSON 对象，也不是只传 base64 部分。当前 wrapper 在子进程环境中显式指定现场使用的 API 地址，单纯外层 export 不一定生效；需要更换时在独立副本审阅对应赋值并验证，再获授权部署。

既有接口代码仅作为备份；此文档不提供自动突破安全验证的增强方案。截图和账户页面可能含个人信息，第三方接口可用性和隐私需自行评估。当前 Telegram 图片发送路径直接调用 `sendPhoto`，历史上传函数保留不代表每次都会调用历史图床。

## 8. 多账号部署整改建议与边界

以下属于待验证的整改清单，不冒称原版已实现：

1. **统一互斥**：原调度没有跨入口全局锁。若要避免手动/定时/两个窗口交叉，应在所有入口采用同一锁，并设计非阻塞失败和告警；只给其中一个入口加锁不完整。
2. **业务幂等**：当前依赖官网可续期状态及单次运行判断，并非本地事务式去重；恢复失败前先检查官网实际结果。
3. **账号数量与耗时预算**：随机开始时间不保证截止前完成。大量账号需预留每次约定超时预算，不能无限堆进两小时窗口。
4. **资源限制**：监测浏览器内存和子进程生命周期；新增 MemoryMax/RuntimeMax 等限制前，在副本验证它们不会在真实提交阶段中断任务。
5. **配置校验**：部署前检测空数组、缺少字段、重复邮箱及重复日志名；不把所有账号批量跑一遍代替静态验证。
6. **告警真实性**：官网成功、wrapper 退出、图片回执必须分别展示。失败时不要发送“全部成功”。
7. **保留当前通知格式**：完整邮箱、脚本/续期分栏，不恢复旧版到期日期箭头。

仓库备份不在生产落地以上建议，任何后续整改应先备份、离线回归、授权单账号验证，再检查定时器与通知。

## 9. 更新与回滚

在部署机先记录当前提交、依赖版本和定时配置，私密备份账号配置、通知凭据及必要运行证据，备份权限设为 600。不要把这些备份放公开 Web 目录或 GitHub。

更新在单独目录克隆固定提交，执行离线测试和秘密扫描；只在没有执行中任务的维护窗口切换。保留原 venv/配置回滚副本，不把新模板覆盖真实账号文件。

仓库历史回滚建议创建正常 revert 提交，不 force push。原仓库已另存本地 Git bundle（未上传，含旧历史，需私密保护）。本机生产 `/opt/xserver`、账号配置和 timer 在本次发布中不修改。

## 10. 本次验证范围

已执行的实际测试见 `docs/verification.json`：离线结果分类、图片通知请求、随机窗口、多账号 schema、语法、秘密扫描和源文件哈希核对。测试不会访问账号、申请续期或发送消息。

**没有执行**：空白机器完整安装、真实账号再次续期、官方接口未来兼容性承诺。历史源码可能存在旧路径和未安装依赖，仅推荐部署当前 app 核心链路，不执行 archive。部署完必须自行按上述分层验收，不能以本文或 CI 通过替代真实业务结果。
