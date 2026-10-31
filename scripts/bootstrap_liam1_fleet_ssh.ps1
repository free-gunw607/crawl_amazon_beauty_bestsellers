<#
Registers the existing WSL fleet public key for the Windows OpenSSH service.
Run elevated. This writes no private key and opens no public-network firewall rule.
#>
$ErrorActionPreference = "Stop"
# Public data only. Embedding it avoids elevation-specific WSL UNC access behavior.
$publicKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIUWisqWhzihGR0bVxS1Tl2KBclKvNbl5dY07BgRJYQ8 fleet-lenovo-bops"
if ($publicKey -notmatch '^ssh-ed25519\s+') {
    throw "Expected an ed25519 fleet public key"
}

$administratorKeys = "C:\ProgramData\ssh\administrators_authorized_keys"

function Add-FleetPublicKey([string]$Path) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    $existing = if (Test-Path -LiteralPath $Path) {
        Get-Content -LiteralPath $Path -Raw
    } else {
        ""
    }
    if ($existing -notmatch [regex]::Escape($publicKey)) {
        Add-Content -LiteralPath $Path -Value $publicKey
    }
}

# The fleet access account is an Administrator; Windows OpenSSH uses ProgramData for it.
Add-FleetPublicKey $administratorKeys
icacls $administratorKeys /inheritance:r | Out-Null
icacls $administratorKeys /grant "*S-1-5-18:F" /grant "*S-1-5-32-544:F" | Out-Null

Set-Service -Name sshd -StartupType Automatic
Restart-Service -Name sshd
Start-Sleep -Seconds 2

$listener = Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction Stop
[pscustomobject]@{
    Status = "fleet-key-installed"
    PublicKey = "fleet-lenovo-bops"
    AdministratorAuthorizedKeys = $administratorKeys
    ListenerCount = @($listener).Count
    TailscaleIPv4 = (& "C:\Program Files\Tailscale\tailscale.exe" ip -4)
} | Format-List
