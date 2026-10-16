# 来源与授权边界

本次是用户现有部署的脱敏备份，不是重新授权。

- 目标仓库原提交：a47f1024cc1a1a23cbc92a879d2eecadd0ab1fcb，历史完整保留。
- 当前部署源：`/opt/xserver/app`；2026-10-09 迁移的 Python 核心与当前通知 wrapper 为部署入口。
- 本机历史副本分别源自 Yi-Zong/xserver-free-vps-auto-renew、Yi-Zong/xserver-renew-onvps；其 README 保存在 archive。
- 原说明引用 GitHub30/extend-vps-exp、GitHub30/captcha-cloudrun 与 motoki-design.co.jp 的相关文章，来源链接保留在历史 README。引用不代表已获得这些项目的额外授权。
- 现场源码树、目标仓库当前树未发现 LICENSE/COPYING；GitHub 仓库 API license 为 null。不能据此声称 MIT、Apache 或其他开源授权。原作者版权与原有声明仍归原权利人；对外再分发/商用前应确认许可。
- Python/浏览器依赖各自遵循上游许可，未将依赖或浏览器二进制打包入本仓库。
- 自动验证相关既有源码仅为原样备份（秘密占位替换除外），此次未新增、优化或实测任何绕过方法。遇到官方挑战应通过官方人工验证/无障碍支持渠道处理。
