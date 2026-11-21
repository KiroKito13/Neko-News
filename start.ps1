$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path config.json)) {
    Copy-Item config.example.json config.json
    Start-Process notepad.exe -ArgumentList config.json -Wait
}
foreach ($provider in 'DISCORD', 'FLUXER') {
    $key = "${provider}_BOT_TOKEN"
    if (![Environment]::GetEnvironmentVariable($key)) {
        $token = Read-Host "$provider bot token" -AsSecureString
        [Environment]::SetEnvironmentVariable($key, [Net.NetworkCredential]::new('', $token).Password)
    }
}
py -3 relay.py
