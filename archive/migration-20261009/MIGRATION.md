# 本机 XServer 核心迁移验收（2026-10-09）

## 结果
已把 `/opt/xserver/app/main.py` 换为 KR-Azure 成功目录的实际 `verified_single.py`，保留其真实登录、Turnstile、data URI 验证码请求、官网按钮点击、提交后重新进入详情流程；不是按摘要重写，也没有复制 KR 账号或代理 runner 到生产入口。
来源：KR-Azure `REDACTED_NODE_ID`，`/opt/extend-vps-exp/runs/account-example-account-20261009T065226Z/`。
先读取了该机 `DEPLOYMENT-VERIFIED.md` 和成功目录 `SUMMARY.md`。原始源码留在本目录 `source/`，仅作审计、不执行其中带代理的 runner。
原始 verified_single.py SHA256：`7d6fca164205729aa82cfd633290bdcba93c5abe361a14218936cb10739f1d7f`。

## 原状和范围
生产链：系统 Timer -> `/usr/bin/python3 /opt/xserver/app/run_xserver_random_window.py %i` -> `run_xserver_notify.py` -> app 专用 venv / main.py。
原来有两个每日窗口，而非一个：北京时间 14:00–16:00、20:00–22:00；均保留。随机计划逐账号错峰，未改动调度源码或任何 systemd unit。
开始时下午 scheduler 正在等待，已有一个历史任务在 14:30 执行完毕。为避免本次触发其他账号，于迁移时停止了仅此下午实例，取消其剩余两个计划；没有重启整批。Timer 保持 enabled/active，下次正常晚间批次继续。
本次仅选择本机 JSON 数组第一个账号（727****），没有导入 KR 凭据。另两个账号没有被本次 canary 启动。KR 操作均为读源码，无远端写入或执行续期。
root user 无 XServer Timer；root cron 无 XServer 项目入口。未更改其他服务。

## 生产适配
- `main.py`：去除代理选项与代理环境；Firefox `network.proxy.type=0`；aiohttp `trust_env=False`；GEOIP=false。指定验证码 API 不变。
- 本机 Camoufox 0.4.11 的 Screen 在 browserforge 而非 camoufox.fingerprints；首次 import 在登录前失败。验证导入失败/正确位置后修复，只调整导入，不替换浏览器流程。
- 移除无人值守失败后保留浏览器 15 分钟的调试等待；运行目录独立、私有。登录一轮一次，不做自动账号重试。
- `run_xserver_notify.py`：保留原标题、账号、运行状态、是否需要续期和截图版式，补业务分类与到期前后值。只在官网完成文字和重新读取期限严格增加同时成立时标为 RENEWED_VERIFIED。NOT_ELIGIBLE 要求登录证据与前后期限相同。
- 每次真实图片 sendPhoto，校验 Telegram JSON ok 和 message_id，写 notification-result.json。没有截图时生成失败结果图片，不悄悄退化为仅文字。HTTP 使用空 ProxyHandler。wrapper/core 失败或发图失败均非零退出。
- 取消旧 wrapper 失败后自动重新登录策略，防止重复提交与锁定。

## 真实 canary
初次因 Screen 导入错误在登录前退出 1；真实失败图 Telegram ok=true，message_id=11405，证据 `../runs/20261009T150812-8e132615/`。
修复后同一个账号执行一次登录，结果 NOT_ELIGIBLE；没有提交续期，不代表本次新增一天。
成功证据 `/opt/xserver/runs/20261009T150850-0d95aad7/`：
- 登录已到 dashboard；服务器 EXAMPLE_SERVER_ID。
- detail-before / detail-after：利用期限均 2026-10-10。
- 官网说明：利用期限の12時間前から更新手続きが可能です。利用を継続される場合は、2026年10月10日 12:00以降にお試しください。（官网未显示时区，不擅自转换。）
- core_exit_code=0；wrapper_process_exit=0；没有其它账号执行。
- 真实结果图 Telegram ok=true，message_id=11406。
- 图：`server-EXAMPLE_SERVER_ID/06_skip_renewal.png`。
验证码 API 本次未调用，因为未到窗口；源代码保留 KR 已验证接口，不把本次没有发生的验证码/续期提交描述为成功。

## 验证与证据
- `canary-exit.json`：真实外层进程退出状态、只选 index 0、账号文件完全不变。
- `verification.json`：3 个账号文件逐字节与备份一致；随机脚本、三个 units 逐字节未改；两个窗口各1000轮随机分配测试，3个独立时刻全在窗口内。
- `live-network.json`：实际运行浏览器及核心进程没有 proxy 环境变量；浏览器实际 prefs 为 network.proxy.type=0。
- `tdd-red*.txt` / `tdd-green.txt`：先失败后通过，覆盖未到窗口、日期未变不得成功、无官网确认不得成功、无登录不得成功、图片通知适配、失败单次执行及退出码。
- 最终 `xserver-checkin-afternoon.timer`、`xserver-checkin-evening.timer` 均 enabled/active；下一触发分别 2026-10-10 14:00 +08、2026-10-09 20:00 +08。

## 备份和回滚
完整 `/opt/xserver`（含专用 venv、原账号、隐藏文件）及三个系统 units：
`/var/backups/xserver/20261009-migration/prechange.tar.gz`，同目录 SHA256 sidecar；权限 0600，含秘密，不公开。
回滚生产入口（保留验收证据）：`sh /opt/xserver/migration-20261009/rollback.sh`。
该脚本已做 sh -n 检查，未执行实际回滚。仅恢复 main.py 和 notify wrapper，因为配置、定时器、随机脚本均未变。不要直接启动全部账号作回滚测试。
