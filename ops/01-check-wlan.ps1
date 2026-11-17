# 对照 docs/01-连接车机热点.md
param(
    [string]$ConfigPath = ""
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $ConfigPath) {
    $local = Join-Path $PSScriptRoot "config.json"
    $ConfigPath = if (Test-Path $local) { $local } else { Join-Path $PSScriptRoot "config.example.json" }
}
$cfg = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($field in @("ssid", "bind_ip", "host")) {
    if ([string]::IsNullOrWhiteSpace([string]$cfg.$field)) {
        throw "请先在 ops/config.json 中填写 $field。"
    }
}
$wlan = netsh wlan show interfaces
$ssid = ([regex]::Match($wlan, "(?m)^\s*SSID\s*:\s*(.+)$")).Groups[1].Value.Trim()
$state = ([regex]::Match($wlan, "(?m)^\s*State\s*:\s*(.+)$")).Groups[1].Value.Trim()
$addr = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -eq $cfg.bind_ip }
$ok = ($state -eq "connected") -and ($ssid -eq $cfg.ssid) -and ($null -ne $addr)
$result = [ordered]@{
    ok = $ok
    expected_ssid = $cfg.ssid
    expected_bind_ip = $cfg.bind_ip
    ssid = $ssid
    state = $state
    bind_ip_present = ($null -ne $addr)
}
$result | ConvertTo-Json -Compress
if (-not $ok) { exit 1 }
