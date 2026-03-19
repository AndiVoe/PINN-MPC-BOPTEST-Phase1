# Real-time campaign progress monitor
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/monitor_campaign.ps1

param(
    [int]$RefreshIntervalSeconds = 10
)

$root = Split-Path (Split-Path $MyInvocation.MyCommand.Path)
$statusPath = Join-Path $root "results/eu_rc_vs_pinn/runtime_discovery/campaign_live_status.json"
$logPath = Join-Path $root "logs/eu_campaign_stage1"

function Get-Status {
    if (-not (Test-Path $statusPath)) {
        return $null
    }
    try {
        return Get-Content $statusPath -Raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Format-Elapsed {
    param([int]$Seconds)
    $h = [int]($Seconds / 3600)
    $m = [int](($Seconds % 3600) / 60)
    $s = $Seconds % 60
    return "{0:D2}:{1:D2}:{2:D2}" -f $h, $m, $s
}

function Get-EstimatedRemaining {
    param($Status)
    
    if (-not $Status.completed_cases -or $Status.completed_cases -eq 0) {
        return "calculating..."
    }
    
    $total = $Status.total_cases
    $completed = $Status.completed_cases
    $elapsed = (Get-Date) - ([DateTime]$Status.started_utc)
    $avgPerCase = $elapsed.TotalSeconds / $completed
    $remaining = ($total - $completed) * $avgPerCase
    
    return Format-Elapsed ([int]$remaining)
}

Write-Host "`n╔════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   EU Phase 1 Campaign Progress Monitor    ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$lastState = $null

while ($true) {
    $status = Get-Status
    
    if ($status) {
        $elapsed = (Get-Date) - ([DateTime]$status.started_utc)
        $elapsedStr = Format-Elapsed ([int]$elapsed.TotalSeconds)
        $estimatedRemaining = Get-EstimatedRemaining $status
        
        Write-Host "`r[$(Get-Date -Format 'HH:mm:ss')] State: $($status.state) | Cases: $($status.completed_cases)/$($status.total_cases) | " -NoNewline -ForegroundColor White
        
        if ($status.state -eq "running" -and $status.current_case) {
            Write-Host "Current: $($status.current_case) [$($status.current_step)] | " -NoNewline -ForegroundColor Yellow
        }
        
        Write-Host "Elapsed: $elapsedStr | Est. Remaining: $estimatedRemaining" -ForegroundColor Green
        
        if ($status.state -eq "completed" -or $status.state -eq "stopped") {
            Write-Host "`n✓ Campaign $($status.state.ToUpper())" -ForegroundColor Green
            Write-Host "  Completed: $($status.completed_cases) cases" -ForegroundColor Green
            if ($status.failed_cases -gt 0) {
                Write-Host "  Failed: $($status.failed_cases) cases" -ForegroundColor Red
                Write-Host "  See: $($status.failure_summary)" -ForegroundColor Yellow
            }
            break
        }
        
        if ($status.last_error) {
            Write-Host "  ⚠ Last error: $($status.last_error)" -ForegroundColor Red
        }
        
        $lastState = $status.state
    } else {
        Write-Host "`r[$(Get-Date -Format 'HH:mm:ss')] Waiting for campaign to start..." -NoNewline -ForegroundColor Gray
    }
    
    Start-Sleep -Seconds $RefreshIntervalSeconds
}
