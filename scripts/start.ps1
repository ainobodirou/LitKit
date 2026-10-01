param(
    [switch]$Reload,
    [switch]$SkipMcpWarmup
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$requiredEnvKeys = @(
    "ANTHROPIC_API_KEY",
    "LITELLM_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OWNER_USER_ID",
    "GOOGLE_OAUTH_CREDENTIALS",
    "GOOGLE_CALENDAR_MCP_TOKEN_PATH"
)

function Test-CommandAvailable {
    param([Parameter(Mandatory)][string]$Name)

    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-TcpPort {
    param(
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][int]$Port
    )

    $client = [System.Net.Sockets.TcpClient]::new()

    try {
        $connection = $client.ConnectAsync($HostName, $Port)
        return $connection.Wait(1000) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Test-DockerEngine {
    $previousErrorPreference = $ErrorActionPreference

    try {
        # Docker writes connection failures to stderr. Suppress them here so
        # strict script error handling does not abort before we inspect its
        # process exit code.
        $ErrorActionPreference = "SilentlyContinue"
        docker info *> $null
        return $LASTEXITCODE -eq 0
    }
    finally {
        $ErrorActionPreference = $previousErrorPreference
    }
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Virtual environment not found at $pythonPath. Create it and install requirements.txt first."
}

if (-not (Test-Path -LiteralPath ".env" -PathType Leaf)) {
    throw ".env was not found in $projectRoot."
}

$envContents = Get-Content -LiteralPath ".env"

foreach ($key in $requiredEnvKeys) {
    $pattern = "^\s*" + [regex]::Escape($key) + "\s*=\s*.+$"

    if (-not ($envContents | Select-String -Pattern $pattern -Quiet)) {
        throw "Required .env setting is missing or empty: $key"
    }
}

if (-not (Test-CommandAvailable -Name "docker")) {
    throw "Docker CLI was not found. Install Docker Desktop first."
}

if (-not (Test-CommandAvailable -Name "npx.cmd")) {
    throw "npx.cmd was not found. Install Node.js first."
}

Write-Host "Checking Python dependencies..."
& $pythonPath -c "import fastapi, duckdb, telegram, langchain, langchain_mcp_adapters, sentence_transformers"

if ($LASTEXITCODE -ne 0) {
    throw "Python dependency check failed. Install requirements.txt into .venv."
}

Write-Host "Checking Google Calendar credentials..."
& $pythonPath -m scripts.preflight

if ($LASTEXITCODE -ne 0) {
    throw "Google Calendar credential preflight failed."
}

if (-not (Test-DockerEngine)) {
    $dockerDesktopCandidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\Docker Desktop.exe")
    )
    $dockerDesktopPath = $dockerDesktopCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1

    if (-not $dockerDesktopPath) {
        throw "Docker Desktop is not running and its executable was not found."
    }

    Write-Host "Starting Docker Desktop..."
    Start-Process -FilePath $dockerDesktopPath -WindowStyle Hidden

    $dockerReady = $false

    foreach ($attempt in 1..120) {
        if (Test-DockerEngine) {
            $dockerReady = $true
            break
        }

        Start-Sleep -Seconds 1
    }

    if (-not $dockerReady) {
        throw "Docker Desktop started, but its Linux engine was not ready after 120 seconds."
    }
}

Write-Host "Starting LiteLLM..."
docker compose up -d litellm

if ($LASTEXITCODE -ne 0) {
    throw "LiteLLM failed to start."
}

Write-Host "Waiting for LiteLLM on port 4000..."
$litellmReady = $false

foreach ($attempt in 1..30) {
    if (Test-TcpPort -HostName "127.0.0.1" -Port 4000) {
        $litellmReady = $true
        break
    }

    Start-Sleep -Seconds 1
}

if (-not $litellmReady) {
    docker compose logs --tail 50 litellm
    throw "LiteLLM did not become available on port 4000."
}

if (-not $SkipMcpWarmup) {
    Write-Host "Preparing Google Calendar MCP..."
    npx.cmd --yes @cocal/google-calendar-mcp@2.6.3 --version

    if ($LASTEXITCODE -ne 0) {
        throw "Google Calendar MCP package could not be prepared."
    }
}

$uvicornArguments = @(
    "-m", "uvicorn",
    "app.main:app",
    "--host", "127.0.0.1",
    "--port", "8000"
)

if ($Reload) {
    $uvicornArguments += "--reload"
}

Write-Host "Starting LitKit..."
& $pythonPath @uvicornArguments
