# XServer VPS Auto Renew

自动化处理 XServer 免费 VPS 续期的实验仓库。

## 功能概览

- 自动登录 XServer 面板
- 识别图片验证码
- 处理续期流程
- 支持 Tampermonkey 方案与脚本化运行

## 快速入口

- Colab：<https://colab.research.google.com/drive/1l1fAyDzNSSCVOF_JBpXRp2b3SHuI5bz6?usp=sharing>
- CAPTCHA 模型仓库：<https://github.com/GitHub30/captcha-cloudrun>
- 安装 Tampermonkey 脚本：<https://raw.githubusercontent.com/GitHub30/extend-vps-exp/refs/heads/main/renew.user.js>
- XServer 登录页：<https://secure.xserver.ne.jp/xapanel/login/xvps/>

## 使用方式

### 方式 1：Tampermonkey

1. 安装上面的用户脚本。
2. 打开 XServer 登录页。
3. 按页面提示执行续期。

### 方式 2：环境变量 + 脚本运行

如果自动化脚本不起作用，可以先检查环境变量是否已设置：

```env
EMAIL=account@example.invalid
PASSWORD=yourpassword
PROXY_SERVER=http://user:account@example.invalid:8888
```

## 代理服务器示例

```bash
apt update
apt install -y tinyproxy
echo Allow 0.0.0.0/0 >> /etc/tinyproxy/tinyproxy.conf
echo BasicAuth user password >> /etc/tinyproxy/tinyproxy.conf
systemctl restart tinyproxy
systemctl status tinyproxy
```

## 参考文档

- 日文说明：<https://motoki-design.co.jp/wordpress/xserver-vps-auto-renew/>
- 英文说明：<https://motoki-design.co.jp/wordpress/xserver-vps-auto-renew/>
- 中文说明：<https://motoki-design.co.jp/wordpress/xserver-vps-auto-renew/>

## 备注

- 当前仓库主要用于 XServer 免费 VPS 续期实验与通知联动。
- 如果你在 OpenClaw 工作区中使用它，建议结合 `run_xserver_notify.py` 与 cron 一起运行。
