# SSH 密钥与主机身份

操作文件：[ops/04-ssh-login.py](../ops/04-ssh-login.py)、[ops/04-bind7878-proxy.py](../ops/04-bind7878-proxy.py)。步骤：[docs/04-公钥登录.md](../docs/04-公钥登录.md)。

## 本机配置，不入库

- 将自己的私钥放到 `ops/config.json` 的 `identity_file` 路径，默认 `ssh/id_ed25519`。已有密钥不必重新生成。
- 对应的客户端公钥须事先由设备管理员授权；仓库不附带任何已授权密钥或设备指纹。
- 从设备控制台或其他独立可信渠道取得目标主机公钥，并核验其 SHA-256 指纹，再按 OpenSSH known_hosts 格式保存到 `ssh/known_hosts`。
- 每行使用 `主机地址 密钥类型 公钥内容`；非默认端口的主机地址格式为 `[主机地址]:端口`。内容必须对应本机配置中的 `host` 和 `ssh_port`。
- 仅运行 `ssh-keyscan` 取得的结果未经身份核验，不能直接视为可信。
- 检查本机文件指纹：`ssh-keygen.exe -lf ssh/known_hosts -E sha256`。
- 脚本使用 `StrictHostKeyChecking=yes`；缺少可信主机文件、未知主机或主机公钥变更时拒绝登录。
- `ssh/` 下除本说明外的文件全部忽略；不要强制提交私钥、公钥、known_hosts 或真实指纹。

## 需要新客户端密钥时

在本机执行 `ssh-keygen.exe -t ed25519 -f ssh/id_ed25519`，按提示设置口令，再由设备管理员授权对应公钥。不要在文档、日志或截图中分享设备关联信息。
