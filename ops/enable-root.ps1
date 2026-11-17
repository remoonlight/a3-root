# 对照 docs/05-一键开启.md
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$Ops = Join-Path $Root "ops"
$Example = Join-Path $Ops "config.example.json"
$Config = Join-Path $Ops "config.json"
if (-not (Test-Path $Config)) {
    Copy-Item -LiteralPath $Example -Destination $Config
    throw "已创建 ops/config.json；请先填写 ssid、bind_ip、host，并按 ssh/README.md 准备密钥和可信主机文件，然后重试。"
}
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "需要 python" }
$Python = $py.Source
if ($py.Name -eq "py.exe") { $PythonArgs = @("-3") } else { $PythonArgs = @() }
$env:PYTHONPATH = $Ops
$Session = Join-Path $Root ("sessions\" + [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ"))
New-Item -ItemType Directory -Path $Session | Out-Null

function Invoke-Py([string]$script, [string[]]$scriptArgs) {
    & $Python @PythonArgs $script @scriptArgs
    return $LASTEXITCODE
}

Write-Host "1 检查热点  docs/01-连接车机热点.md"
$code = 0
& (Join-Path $Ops "01-check-wlan.ps1")
$code = $LASTEXITCODE
if ($code -ne 0) { throw "未连到配置中的车机热点" }

Write-Host "2 尝试已有 SSH  docs/04-公钥登录.md"
$code = Invoke-Py (Join-Path $Ops "04-ssh-login.py") @("--json-output", (Join-Path $Session "ssh-first.json"))
if ($code -eq 0) {
    Write-Host "sshd 已在，uid=0 已核对。会话 $Session"
    exit 0
}

Write-Host "3 发 0xe3 拉 sshd  docs/03-0xe3-拉起sshd.md"
$code = Invoke-Py (Join-Path $Ops "03-send-e3.py") @("--json-output", (Join-Path $Session "e3.json"))
if ($code -ne 0) { throw "0xe3 未拿到 82 e3 01 01" }

Write-Host "4 再登录  docs/04-公钥登录.md"
$code = Invoke-Py (Join-Path $Ops "04-ssh-login.py") @("--json-output", (Join-Path $Session "ssh-after.json"))
if ($code -ne 0) { throw "SSH 未得到 uid=0。看 $Session" }
Write-Host "完成 uid=0。会话 $Session"
exit 0
