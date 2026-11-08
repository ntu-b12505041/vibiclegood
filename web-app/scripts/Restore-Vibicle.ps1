param(
    [Parameter(Mandatory)]
    [string]$BackupPath,
    [Parameter(Mandatory)]
    [string]$EnvironmentFile,
    [Parameter(Mandatory)]
    [ValidatePattern('^vibicle-restore-[a-z0-9-]+$')]
    [string]$ProjectName
)
$ErrorActionPreference = 'Stop'
$path = (Resolve-Path -LiteralPath $BackupPath).Path
$envPath = (Resolve-Path -LiteralPath $EnvironmentFile).Path
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$manifest = Get-Content -Raw -LiteralPath (Join-Path $path 'manifest.json') | ConvertFrom-Json
foreach ($file in @('db.dump','images.tar')) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $path $file)).Hash -ne $manifest.$file) {
        throw "Invalid backup checksum for $file."
    }
}
Push-Location $root
try {
    function Compose {
        docker compose --env-file $envPath -f compose.deploy.yaml -p $ProjectName @args
        if ($LASTEXITCODE -ne 0) { throw "Compose command failed: $($args[0])" }
    }
    $existing = @(docker ps -aq --filter "label=com.docker.compose.project=$ProjectName")
    if ($LASTEXITCODE -ne 0) { throw 'Docker is unavailable.' }
    $volumes = @(docker volume ls -q --filter "label=com.docker.compose.project=$ProjectName")
    if ($LASTEXITCODE -ne 0) { throw 'Docker is unavailable.' }
    if ($existing.Count -or $volumes.Count) { throw 'Restore requires a brand new project and volumes.' }
    Compose up -d --wait --wait-timeout 90 db
    Compose cp (Join-Path $path 'db.dump') 'db:/tmp/vibicle-restore.dump'
    Compose exec -T db sh -ec 'pg_restore --exit-on-error --single-transaction --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB" /tmp/vibicle-restore.dump'
    Compose exec -T db sh -ec 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"' sh 'UPDATE auth_sessions SET revoked_at = greatest(created_at, clock_timestamp()) WHERE revoked_at IS NULL'
    Compose exec -T db rm -- /tmp/vibicle-restore.dump
    Compose run --rm migrate
    Compose run --rm --no-deps --volume "${path}:/backup:ro" api python -m vibicle_api.bundle_images unpack /backup/images.tar
    Compose run --rm --no-deps api python -m vibicle_api.bundle_images verify
    Write-Output 'Restore and session invalidation complete. API and Caddy are still stopped.'
} finally { Pop-Location }
