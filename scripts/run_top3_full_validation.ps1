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

$yamlRaw = Get-Content $planPath -Raw

# Try structured YAML parsing if ConvertFrom-Yaml is available (PowerShell 7+).
$episodes = @()
$outputRoot = $null
$candidates = @()
$predictors = @()

if (Get-Command -Name ConvertFrom-Yaml -ErrorAction SilentlyContinue) {
    try {
        $plan = $yamlRaw | ConvertFrom-Yaml
        if ($plan -and $plan.validation) {
            $episodes = $plan.validation.episodes
            $outputRoot = $plan.validation.output_root
            if ($plan.validation.predictors) {
                $predictors = $plan.validation.predictors
            }
        }
        if ($plan -and $plan.candidates) {
            $candidates = $plan.candidates
        }
    } catch {
        Write-Host "WARNING: ConvertFrom-Yaml failed: $($_.Exception.Message)"
    }
}

# Fallback: tolerant line-based parsing to handle older PowerShell or minor formatting differences.
if (-not $episodes -or -not $outputRoot -or -not $candidates -or $candidates.Count -eq 0) {
    $lines = $yamlRaw -split "`r?`n"
    $episodeLine = $lines | Where-Object { $_ -match "^\s*episodes\s*:" } | Select-Object -First 1
    $outputRootLine = $lines | Where-Object { $_ -match "^\s*output_root\s*:" } | Select-Object -First 1

    if ($episodeLine) {
        $epRaw = $episodeLine -replace ".*episodes\s*:\s*\[", "" -replace "\].*$", ""
        $episodes = $epRaw.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
    }
    # Parse predictors if present
    $predictorsLine = $lines | Where-Object { $_ -match "^\s*predictors\s*:" } | Select-Object -First 1
    if ($predictorsLine) {
        $predRaw = $predictorsLine -replace ".*predictors\s*:\s*\[", "" -replace "\].*$", ""
        $predictors = $predRaw.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
    }
    if ($outputRootLine) {
        $outputRoot = ($outputRootLine -replace "^\s*output_root\s*:\s*", "").Trim()
    }

    # Parse candidates: prefer pairing '- id' blocks with subsequent 'mpc_config' lines.
    $candidateLines = $lines | Where-Object { $_ -match "^\s*-\s*id\s*:\s*cand_\d+" }
    $configLines = $lines | Where-Object { $_ -match "^\s*mpc_config\s*:\s*" }

    if ($candidateLines.Count -ne $configLines.Count) {
        $candidates = @()
        for ($idx = 0; $idx -lt $lines.Count; $idx++) {
            $line = $lines[$idx]
            if ($line -match "^\s*-\s*id\s*:\s*(cand_\d+)") {
                $id = $Matches[1]
                $cfg = $null
                for ($j = $idx + 1; $j -lt [Math]::Min($idx + 10, $lines.Count); $j++) {
                    if ($lines[$j] -match "^\s*mpc_config\s*:\s*(.+)") {
                        $cfg = $Matches[1].Trim()
                        break
                    }
                }
                $candidateObj = [PSCustomObject]@{ id = $id; mpc_config = $cfg }
                $candidates += $candidateObj
            }
        }
    } else {
        $candidates = @()
        for ($i = 0; $i -lt $candidateLines.Count; $i++) {
            $id = ($candidateLines[$i] -replace "^\s*-\s*id\s*:\s*", "").Trim()
            $cfg = ($configLines[$i] -replace "^\s*mpc_config\s*:\s*", "").Trim()
            $candidateObj = [PSCustomObject]@{ id = $id; mpc_config = $cfg }
            $candidates += $candidateObj
        }
    }
}

if (-not $episodes -or -not $outputRoot -or -not $candidates -or $candidates.Count -eq 0) {
    throw "Could not parse plan file into episodes/output_root/candidates. Parsed counts: episodes=$($episodes.Count); candidates=$($candidates.Count)"
}

# Ensure we have at least one predictor (default to pinn)
if (-not $predictors -or $predictors.Count -eq 0) {
    $predictors = @("pinn")
}

Write-Host "DEBUG: parsed episodes=$($episodes.Count) output_root='$outputRoot' candidates=$($candidates.Count)"

$commands = @()
foreach ($cand in $candidates) {
    $candId = $cand.id
    $cfg = $cand.mpc_config
    if (-not $cfg) {
        Write-Host "WARNING: candidate $candId has no mpc_config; skipping"
        continue
    }
    foreach ($ep in $episodes) {
        $outDir = "$outputRoot/$candId"
        foreach ($pred in $predictors) {
            $cmd = "`"$py`" scripts/run_mpc_episode.py --predictor $pred --episode $ep --mpc-config `"$cfg`" --output-dir `"$outDir`" --no-live-snapshot --recover-from-queued --resume-existing --startup-timeout-s 1800"
            $commands += $cmd
        }
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
    foreach ($cand in $candidates) {
        $candId = $cand.id
        $cfg = $cand.mpc_config
        if (-not $cfg) {
            Write-Host "WARNING: candidate $candId has no mpc_config; skipping"
            continue
        }
        foreach ($ep in $episodes) {
            $outDir = "$outputRoot/$candId"
            foreach ($pred in $predictors) {
                Write-Host ""
                Write-Host "== Running =="
                $args = @(
                    "scripts/run_mpc_episode.py",
                    "--predictor", $pred,
                    "--episode", $ep,
                    "--mpc-config", $cfg,
                    "--output-dir", $outDir,
                    "--no-live-snapshot",
                    "--recover-from-queued",
                    "--resume-existing",
                    "--startup-timeout-s", "1800"
                )
                Write-Host "& $py $($args -join ' ')"
                & $py @args
                if ($LASTEXITCODE -ne 0) {
                    throw "Command failed with exit code $LASTEXITCODE"
                }
            }
        }
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Full validation batch finished."
