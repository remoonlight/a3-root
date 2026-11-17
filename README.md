# A3 root

仓库地址：[vw-id-headunit-lab/a3-root](https://github.com/vw-id-headunit-lab/a3-root)

ICAS3GP（8704）经车机 SoftAP **A3** 通道拉起 Linux `sshd`，源端口 **7878** 公钥登录 `root`。文档与 `ops/` 文件一一对应。

仓库仅包含通用操作与模板；个人配置和 SSH 密钥不入库。

## 文档 ↔ 操作

| 步骤 | 文档 | 操作文件 |
|---|---|---|
| 配置 | [docs/00-配置.md](docs/00-配置.md) | [ops/config.example.json](ops/config.example.json)、[ops/config.py](ops/config.py) |
| 连热点 | [docs/01-连接车机热点.md](docs/01-连接车机热点.md) | [ops/01-check-wlan.ps1](ops/01-check-wlan.ps1) |
| 探测端口 | [docs/02-探测15500与22.md](docs/02-探测15500与22.md) | [ops/02-tcp-probe.py](ops/02-tcp-probe.py) |
| 发 0xe3 | [docs/03-0xe3-拉起sshd.md](docs/03-0xe3-拉起sshd.md) | [ops/03-send-e3.py](ops/03-send-e3.py)、[ops/testiface_frame.py](ops/testiface_frame.py) |
| 公钥登录 | [docs/04-公钥登录.md](docs/04-公钥登录.md) | [ops/04-ssh-login.py](ops/04-ssh-login.py)、[ops/04-bind7878-proxy.py](ops/04-bind7878-proxy.py)、[ssh/README.md](ssh/README.md) |
| 一键 | [docs/05-一键开启.md](docs/05-一键开启.md) | [ops/enable-root.ps1](ops/enable-root.ps1)、[ops/wait_7878.py](ops/wait_7878.py) |

## 一键

```powershell
# 在仓库根目录执行
Copy-Item ops\config.example.json ops\config.json
# 编辑 ops/config.json，填入本机网络参数和私钥路径
# 按 ssh/README.md 准备可信的 ssh/known_hosts
.\ops\enable-root.ps1
```

模板中的 `ssid`、`bind_ip`、`host` 为空，须先在本机配置中填写。真实配置、客户端密钥和主机身份文件均不入库。

验收：SSH 输出含 `uid=0(root)`。ACK `82 e3 01 01` 只证明协议，不证明身份。

## 自检（不连车）

```powershell
python ops\testiface_frame.py --selftest
python tests\test_testiface_regression.py
python tests\test_docs_ops.py
```

冷启动后 sshd 不会自起，每次下电需再跑一键或只发 `0xe3`。有线 A1、Android／QNX 不在本仓。
