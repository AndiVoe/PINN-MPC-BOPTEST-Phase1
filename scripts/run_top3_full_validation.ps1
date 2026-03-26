Param(
    [string]$PythonExe = ".venv/Scripts/python.exe",
    [string]$PlanFile = "configs/autotune_top3_full_validation.yaml",
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$py = Join-Path $root $PythonExe
$planPath = Join-Path $root $PlanFile

if (-not (Test-Path $py)) {
    throw "Python executable not found: $py"
}
if (-not (Test-Path $planPath)) {
    throw "Plan file not found: $planPath"
}

$yaml = Get-Content $planPath -Raw

# Very small, explicit parser assumptions for the known plan schema.
$candidateLines = ($yaml -split "`n") | Where-Object { $_ -match "^\s*- id: cand_\d+" }
$configLines = ($yaml -split "`n") | Where-Object { $_ -match "^\s*mpc_config:" }
$episodeLine = (($yaml -split "`n") | Where-Object { $_ -match "^\s*episodes:" })[0]
$outputRootLine = (($yaml -split "`n") | Where-Object { $_ -match "^\s*output_root:" })[0]

if (-not $episodeLine -or -not $outputRootLine) {
    throw "Could not parse episodes/output_root from plan file."
}

$episodesRaw = ($episodeLine -replace "^\s*episodes:\s*\[", "" -replace "\]\s*$", "")
$episodes = $episodesRaw.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }

$outputRoot = ($outputRootLine -replace "^\s*output_root:\s*", "").Trim()

if ($candidateLines.Count -ne $configLines.Count) {
    throw "Candidate list and config list length mismatch in plan file."
}

$commands = @()
for ($i = 0; $i -lt $candidateLines.Count; $i++) {
    $candId = ($candidateLines[$i] -replace "^\s*- id:\s*", "").Trim()
    $cfg = ($configLines[$i] -replace "^\s*mpc_config:\s*", "").Trim()

    foreach ($ep in $episodes) {
        $outDir = "$outputRoot/$candId"
        $cmd = "`"$py`" scripts/run_mpc_episode.py --predictor pinn --episode $ep --mpc-config $cfg --output-dir $outDir --no-live-snapshot --recover-from-queued --startup-timeout-s 1800"
        $commands += $cmd
    }
}

Write-Host "Prepared $($commands.Count) commands from $PlanFile"
Write-Host ""
$commands | ForEach-Object { Write-Host $_ }

if (-not $Execute) {
    Write-Host ""
    Write-Host "Dry-run mode active. No command executed."
    Write-Host "Run again with -Execute to launch the full validation batch."
    exit 0
}

Push-Location $root
try {
    foreach ($c in $commands) {
        Write-Host ""
        Write-Host "== Running =="
        Write-Host $c
        Invoke-Expression $c
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Full validation batch finished."
