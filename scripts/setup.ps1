param([switch]$StartServices)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$apiDirectory = Join-Path $projectRoot "api"
$webDirectory = Join-Path $projectRoot "web"
$venvDirectory = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvDirectory "Scripts\python.exe"

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    $standardDocker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $standardDocker) { $docker = Get-Item -LiteralPath $standardDocker }
}
if (-not $docker) { throw "Docker CLI is unavailable. Start/reinstall Docker Desktop and reopen the terminal." }

if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv $venvDirectory
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install fastapi "uvicorn[standard]" sqlalchemy "psycopg[binary]" pydantic-settings agora-agents httpx "PyJWT[crypto]" prometheus-client pgvector alembic "redis[hiredis]" cryptography locust
if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed" }

Push-Location $webDirectory
try {
    npm install
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally {
    Pop-Location
}

Push-Location $apiDirectory
try {
    & $venvPython -m py_compile (Get-ChildItem app,tests,migrations -Recurse -Filter *.py | ForEach-Object FullName)
    if ($LASTEXITCODE -ne 0) { throw "Backend syntax validation failed" }
    & $venvPython -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
} finally {
    Pop-Location
}

Push-Location $projectRoot
try {
    & $docker.Source compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose validation failed" }
    & $docker.Source compose build
    if ($LASTEXITCODE -ne 0) { throw "Container build failed" }
    if ($StartServices) {
        & $docker.Source compose up -d
        if ($LASTEXITCODE -ne 0) { throw "Container startup failed" }
    }
} finally {
    Pop-Location
}

Write-Output "ORBIT dependency installation and verification completed successfully."
