param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot '.env'
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $pythonExe)) {
    throw "Missing project venv Python at $pythonExe"
}

if (-not (Test-Path $envFile)) {
    throw "Missing .env at $envFile"
}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) {
        return
    }

    if ($line -notmatch '^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
        Write-Warning "Ignoring malformed .env line: $line"
        return
    }

    $name = $Matches[1]
    $value = $Matches[2].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    elseif ($value.Contains('#')) {
        $value = ($value -split '\s+#', 2)[0].TrimEnd()
    }

    [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
}

$aiPort = if ($env:AI_SERVING_PORT) { $env:AI_SERVING_PORT } else { '8001' }
$gatewayPort = if ($env:API_GATEWAY_PORT) { $env:API_GATEWAY_PORT } else { '8000' }
$aiHost = if ($env:AI_SERVING_HOST) { $env:AI_SERVING_HOST } else { '127.0.0.1' }
$gatewayHost = if ($env:API_GATEWAY_HOST) { $env:API_GATEWAY_HOST } else { '127.0.0.1' }

$aiArgs = @(
    '-m', 'uvicorn',
    'backend.ai_serving.main:app',
    '--host', $aiHost,
    '--port', $aiPort
)

$gatewayArgs = @(
    '-m', 'uvicorn',
    'backend.api_gateway.main:app',
    '--host', $gatewayHost,
    '--port', $gatewayPort,
    '--reload'
)

Write-Host "Using Python: $pythonExe"
Write-Host "Loaded env: $envFile"
Write-Host "AI Serving: http://${aiHost}:${aiPort}"
Write-Host "API Gateway: http://${gatewayHost}:${gatewayPort}"

if ($DryRun) {
    Write-Host "Dry run only."
    Write-Host "$pythonExe $($aiArgs -join ' ')"
    Write-Host "$pythonExe $($gatewayArgs -join ' ')"
    exit 0
}

$aiProcess = Start-Process -FilePath $pythonExe -ArgumentList $aiArgs -WorkingDirectory $projectRoot -PassThru

try {
    $aiReady = $false
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        Start-Sleep -Seconds 1
        if ($aiProcess.HasExited) {
            throw "AI Serving exited early with code $($aiProcess.ExitCode)"
        }

        try {
            $response = Invoke-WebRequest -Uri "http://${aiHost}:${aiPort}/healthz" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $aiReady = $true
                break
            }
        }
        catch {
        }
    }

    if (-not $aiReady) {
        throw "AI Serving did not become ready at http://${aiHost}:${aiPort}/healthz"
    }

    & $pythonExe @gatewayArgs
}
finally {
    if ($aiProcess -and -not $aiProcess.HasExited) {
        Stop-Process -Id $aiProcess.Id -Force
        try {
            Wait-Process -Id $aiProcess.Id -ErrorAction Stop
        }
        catch {
        }
    }
}
