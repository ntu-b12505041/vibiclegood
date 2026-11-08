# Run from any working directory. Never replaces an existing .env.
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$envPath = Join-Path $projectRoot '.env'
function New-LocalSecret {
    $secretBytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($secretBytes) } finally { $rng.Dispose() }
    ([BitConverter]::ToString($secretBytes)).Replace('-', '').ToLowerInvariant()
}
if (Test-Path -LiteralPath $envPath) {
    if (-not (Select-String -LiteralPath $envPath -Pattern '^RATE_LIMIT_SECRET=' -Quiet)) {
        [IO.File]::AppendAllText($envPath, "`nRATE_LIMIT_SECRET=$(New-LocalSecret)`n")
        Write-Output 'Added independent rate limit secret; existing settings preserved.'
    } else {
        Write-Output '.env already configured; preserved.'
    }
    exit 0
}
$template = [IO.File]::ReadAllText((Join-Path $projectRoot '.env.example'))
$content = $template.Replace('replace_with_a_local_random_password', (New-LocalSecret))
$content = $content.Replace('replace_with_an_independent_local_secret', (New-LocalSecret))
[IO.File]::WriteAllText($envPath, $content, (New-Object Text.UTF8Encoding($false)))
Write-Output 'Created ignored local .env; password was not printed.'
