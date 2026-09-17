# Run this once, from backend/, in a PowerShell that can reach psql.
# It generates two fresh random passwords, applies them directly to the
# bgp_owner/bgp_app roles via ALTER ROLE, and writes backend/.env itself --
# so there is no manual copy/paste step where the two can drift apart.
#
# You will be prompted for the postgres superuser password once by psql
# (or set $env:PGPASSWORD before running this, if you'd rather not be
# prompted).

$ErrorActionPreference = "Stop"

function New-Password {
    -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_})
}

$ownerPassword = New-Password
$appPassword = New-Password

$psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
if (-not $psql) {
    $candidates = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue
    if ($candidates) { $psql = $candidates[0].FullName }
}
if (-not $psql) {
    throw "psql.exe not found on PATH or under C:\Program Files\PostgreSQL\*\bin. Pass its full path in as `$psql = '...'` and re-run."
}
Write-Host "Using psql at: $psql"

& $psql -U postgres -h localhost -c "ALTER ROLE bgp_owner PASSWORD '$ownerPassword';"
if ($LASTEXITCODE -ne 0) { throw "ALTER ROLE bgp_owner failed (exit $LASTEXITCODE) -- .env was NOT touched. See the pgAdmin alternative if you don't know the postgres superuser password." }

& $psql -U postgres -h localhost -c "ALTER ROLE bgp_app PASSWORD '$appPassword';"
if ($LASTEXITCODE -ne 0) { throw "ALTER ROLE bgp_app failed (exit $LASTEXITCODE) -- bgp_owner's password WAS changed above but .env was NOT written. Fix auth, then re-run this whole script so both stay in sync." }

$envContent = @"
BGP_DATABASE_URL=postgresql+psycopg2://bgp_app:$appPassword@localhost:5432/bgp_dev
BGP_MIGRATION_DATABASE_URL=postgresql+psycopg2://bgp_owner:$ownerPassword@localhost:5432/bgp_dev
"@

Set-Content -Path ".env" -Value $envContent -NoNewline -Encoding utf8

Write-Host "Done. backend/.env rewritten with passwords that now match Postgres exactly."
