param(
    [ValidateSet('.env.deploy.local', '.env.deploy.production')]
    [string]$FileName = '.env.deploy.local'
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$destination = Join-Path $root $FileName
if (Test-Path -LiteralPath $destination) {
    Write-Output "$FileName already exists and was preserved."
    exit 0
}
$content = [IO.File]::ReadAllText((Join-Path $root '.env.deploy.example'))
foreach ($placeholder in @(
    'replace_with_a_local_random_password',
    'replace_with_an_independent_runtime_password',
    'replace_with_an_independent_local_secret'
)) {
    $data = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($data) } finally { $rng.Dispose() }
    $content = $content.Replace($placeholder, ([BitConverter]::ToString($data)).Replace('-', '').ToLowerInvariant())
}
[IO.File]::WriteAllText($destination, $content, [Text.UTF8Encoding]::new($false))
Write-Output "Created ignored $FileName. Secrets were not printed."
