# 0xe3 拉起 sshd

操作文件：

| 文件 | 作用 |
|---|---|
| [ops/03-send-e3.py](../ops/03-send-e3.py) | 组帧、绑 7878、发送、核对 ACK |
| [ops/testiface_frame.py](../ops/testiface_frame.py) | `0xe3` 帧格式与校验 |

车端：`testiface` 收到 `0xe3` 后 `posix_spawn("/bin/sh","-c",cmd)`。本步默认命令只建 `/var/run/sshd` 并按只读配置启动 sshd。sshd 在 tmpfs，下电即失。

```powershell
# 在仓库根目录执行
python ops\03-send-e3.py --json-output sessions\e3.json
```

协议通过：回包含 `82e30101`。本车完整回包为配置 `expected_ack_hex`。

ACK 不是 uid。身份下一步 SSH `id`。

帧自检（不连车）：

```powershell
python ops\testiface_frame.py --selftest
python tests\test_testiface_regression.py
```
