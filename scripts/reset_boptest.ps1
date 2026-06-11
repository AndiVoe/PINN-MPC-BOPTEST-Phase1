param(
    [string]$Url = "http://127.0.0.1:8000",
    [string]$RedisName = "project1-boptest-redis-1",
    [string]$ComposeFile = "",
    [switch]$Hard
)

$ErrorActionPreference = "Stop"

function Invoke-StopActiveTests {
    param([string]$BaseUrl, [string]$Redis)

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "Docker CLI not available; skipping test stop cleanup."
        return
    }

    try {
        $active = docker exec $Redis redis-cli --raw EVAL "local out={}; for _,k in ipairs(redis.call('keys','tests:*')) do local s=redis.call('hget',k,'status'); if s=='Queued' or s=='Running' then table.insert(out,k..'='..s) end end; return out" 0
    } catch {
        Write-Host "Could not query active tests in Redis: $($_.Exception.Message)"
        return
    }

    foreach ($line in $active) {
        if ($line -match '^tests:([^=]+)=') {
            $testId = $Matches[1]
            try {
                Invoke-RestMethod -Method Put -Uri ("{0}/stop/{1}" -f $BaseUrl.TrimEnd('/'), $testId) -TimeoutSec 30 | Out-Null
                Write-Host "Stopped active test: $testId"
            } catch {
                Write-Host "Warning: failed to stop test $testId : $($_.Exception.Message)"
            }
        }
    }
}

function Invoke-SoftRestart {
    param([string]$Redis)

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI not available."
    }

    Write-Host "Restarting BOPTEST web, worker, and redis containers ..."
    docker restart project1-boptest-web-1 | Out-Null
    docker restart project1-boptest-worker-1 | Out-Null
    docker restart $Redis | Out-Null
}

function Invoke-HardReset {
    param([string]$Compose)

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI not available."
    }
    if ([string]::IsNullOrWhiteSpace($Compose)) {
        throw "-ComposeFile is required for -Hard reset."
    }

    Write-Host "Performing full compose reset with $Compose ..."
    docker compose -f $Compose down
    docker compose -f $Compose up -d web worker provision
}

Write-Host "Stopping any active BOPTEST tests first ..."
Invoke-StopActiveTests -BaseUrl $Url -Redis $RedisName

if ($Hard) {
    Invoke-HardReset -Compose $ComposeFile
} else {
    Invoke-SoftRestart -Redis $RedisName
}

Write-Host "Reset complete. Check /version and queue depth before resuming campaigns."
