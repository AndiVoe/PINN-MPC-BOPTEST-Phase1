#!/usr/bin/env powershell
<#
.SYNOPSIS
Clean old results, temporary artifacts, and outdated data to prevent accidental reuse.

.DESCRIPTION
This script removes:
1. Old campaign results (eu_rc_vs_pinn/raw - before stage2)
2. Temporary smoke test artifacts (weighting_smoke)
3. Old log files (older than current batch)
4. BUT PRESERVES:
   - Newly trained PINN models (artifacts/eu/*/best_model.pt)
   - Stage2 results (eu_rc_vs_pinn_stage2/)
   - Current configs and manifests
   - Datasets used for new training

.EXAMPLE
.\.venv\Scripts\python.exe .\scripts\cleanup_old_data.ps1
#>

param(
    [switch]$DryRun = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Continue"
$timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

function Write-Log {
    param($Message)
    Write-Output "[$timestamp] $Message"
}

function Remove-ItemSafe {
    param(
        [string]$Path,
        [string]$Description
    )
    
    if (Test-Path $Path) {
        $size = 0
        if ((Get-Item $Path).PSIsContainer) {
            $size = (Get-ChildItem $Path -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
        } else {
            $size = (Get-Item $Path).Length / 1MB
        }
        
        if ($DryRun) {
            Write-Log "[DRY RUN] Would delete $Description : $Path (~$([math]::Round($size,1)) MB)"
        } else {
            try {
                Remove-Item -Path $Path -Recurse -Force -ErrorAction Stop
                Write-Log "[OK] Deleted $Description : $Path (~$([math]::Round($size,1)) MB)"
            } catch {
                Write-Log "[ERROR] Failed to delete $Description : $_"
            }
        }
    } else {
        if ($Verbose) {
            Write-Log "[SKIP] $Description not found: $Path"
        }
    }
}

Write-Log "=========================================="
Write-Log "CLEANUP: Old Results & Temporary Data"
Write-Log "=========================================="
if ($DryRun) { Write-Log "[MODE] DRY RUN (no files deleted)" }
Write-Log ""

# Stage 1: Old campaign results (before stage2)
Write-Log "Stage 1: Removing old campaign results..."
Remove-ItemSafe "results/eu_rc_vs_pinn/raw" "Old stage1 MPC results (raw)"
Remove-ItemSafe "results/eu_rc_vs_pinn/runtime_discovery" "Old runtime discovery logs"

# Stage 2: Temporary smoke test artifacts
Write-Log "Stage 2: Removing temporary smoke test artifacts..."
Remove-ItemSafe "artifacts/weighting_smoke" "Smoke test weighting artifacts"

# Stage 3: Old batch training summaries
Write-Log "Stage 3: Removing old training summaries..."
Remove-ItemSafe "artifacts/eu/retrain_manual_summary.json" "Batch training summary (archive)"

# Stage 4: Outdated probe/diagnostic datasets
Write-Log "Stage 4: Removing diagnostic probe datasets..."
Remove-ItemSafe "datasets/eu_probe_bestest_hydronic" "Diagnostic probe dataset (bestest)"
Remove-ItemSafe "datasets/eu_probe_timing" "Diagnostic probe dataset (timing - before clean)"
Remove-ItemSafe "datasets/eu_probe_timing_clean" "Diagnostic probe dataset (timing - clean)"

# Stage 5: Old log directories (keep recent ones)
Write-Log "Stage 5: Checking old logs..."
if (Test-Path "logs/eu_campaign_stage1") {
    $logFiles = Get-ChildItem "logs/eu_campaign_stage1" -File
    $yesterday = (Get-Date).AddDays(-1)
    
    foreach ($file in $logFiles) {
        if ($file.LastWriteTime -lt $yesterday) {
            $description = "Old log file ($($file.LastWriteTime.ToString('yyyy-MM-dd')))"
            Remove-ItemSafe $file.FullName $description
        }
    }
}

# Stage 6: Verify preservation
Write-Log ""
Write-Log "Stage 6: Verifying newly trained models are preserved..."
$trainedModels = @(
    "artifacts/eu/singlezone_commercial_hydronic/best_model.pt",
    "artifacts/eu/bestest_hydronic/best_model.pt",
    "artifacts/eu/bestest_hydronic_heat_pump/best_model.pt",
    "artifacts/eu/multizone_residential_hydronic/best_model.pt",
    "artifacts/eu/twozone_apartment_hydronic/best_model.pt"
)

$allPreserved = $true
foreach ($model in $trainedModels) {
    if (Test-Path $model) {
        $size = (Get-Item $model).Length / 1MB
        Write-Log "[OK] Preserved: $model ($([math]::Round($size,1)) MB)"
    } else {
        Write-Log "[ERROR] MISSING: $model"
        $allPreserved = $false
    }
}

Write-Log ""
Write-Log "=========================================="
if ($allPreserved) {
    Write-Log "✓ Cleanup verification PASSED"
} else {
    Write-Log "✗ Cleanup verification FAILED - some models missing!"
}
Write-Log "=========================================="

if ($DryRun) {
    Write-Log ""
    Write-Log "To execute cleanup (WARNING - irreversible):"
    Write-Log "  .\scripts\cleanup_old_data.ps1 -DryRun:`$false"
    Write-Log ""
}
