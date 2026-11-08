# Creates a uniquely named verification DB; never drops or resets existing data.
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$envFile = Join-Path $projectRoot '.env'
if (-not (Test-Path -LiteralPath $envFile)) { throw 'Run Initialize-Dev.ps1 first.' }
$userLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^POSTGRES_USER=' } | Select-Object -First 1
if (-not $userLine) { throw 'POSTGRES_USER missing from local .env.' }
$dbUser = $userLine.Split('=',2)[1].Trim()
$verificationDb = 'vibicle_3a_verify_' + [guid]::NewGuid().ToString('N').Substring(0,12)
$previousDb = $env:POSTGRES_DB
$previousTestDb = $env:VIBICLE_TEST_DB
Push-Location $projectRoot
try {
    docker compose exec -T db createdb -U $dbUser $verificationDb
    if ($LASTEXITCODE -ne 0) { throw 'Verification DB creation failed; no migration was run.' }
    $env:POSTGRES_DB = $verificationDb
    $env:VIBICLE_TEST_DB = $verificationDb
    Push-Location (Join-Path $projectRoot 'backend')
    try {
        uv run python -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
        uv run python -m alembic check
        if ($LASTEXITCODE -ne 0) { throw 'Model/migration drift detected.' }
        uv run python -m vibicle_api.check_db
        if ($LASTEXITCODE -ne 0) { throw 'Real DB connection failed.' }
        uv run python -m pytest -m integration -q
        if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL integration tests failed.' }
    } finally { Pop-Location }
    Write-Output ("Verification DB retained for inspection: " + $verificationDb)
} finally {
    $env:POSTGRES_DB = $previousDb
    $env:VIBICLE_TEST_DB = $previousTestDb
    Pop-Location
}
