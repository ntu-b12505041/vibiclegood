param(
    [string]$EnvironmentFile = '.env.deploy.local',
    [ValidatePattern('^[a-z0-9][a-z0-9_-]+$')]
    [string]$ProjectName = 'vibicle-production-like'
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location $root
try {
    function Compose {
        docker compose --env-file $EnvironmentFile -f compose.deploy.yaml -p $ProjectName @args
        if ($LASTEXITCODE -ne 0) { throw "Compose command failed: $($args[0])" }
    }
    $running = @(Compose ps --services --status running)
    if ('api' -in $running -or 'caddy' -in $running -or 'db' -notin $running) {
        throw 'Stop API and Caddy, stop the cleaner, and keep only DB running before backup.'
    }
    $backupId = [Guid]::NewGuid().ToString('N')
    $path = Join-Path $root "output/backup-$backupId"
    [IO.Directory]::CreateDirectory($path) | Out-Null
    $remote = "/tmp/vibicle-$backupId.dump"
    Compose exec -T db sh -ec 'pg_dump -Fc --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$1"' sh $remote
    Compose cp "db:$remote" (Join-Path $path 'db.dump')
    Compose exec -T db rm -- $remote
    Compose run --rm --no-deps --user 0:0 --volume "${path}:/backup" api python -m vibicle_api.bundle_images pack /backup/images.tar
    $hashes = [ordered]@{}
    foreach ($file in @('db.dump','images.tar')) {
        $hashes[$file] = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $path $file)).Hash
    }
    $hashes | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $path 'manifest.json')
    Write-Output "Backup completed at $path"
} finally { Pop-Location }
