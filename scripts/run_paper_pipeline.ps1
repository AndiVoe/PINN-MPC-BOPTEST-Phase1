
# Run this first!!!!!!!!!!!!!!!!!!!!
# First run ".\scripts\reset_boptest.ps1"


Param(
	[string]$PythonExe       = ".venv/Scripts/python.exe",
	[string]$MpcEpisode       = "te_exc_aut_rw",
	# Phase skips
	[switch]$SkipDataGen,       # Phase 1  - standard 30-day dataset
	[switch]$SkipDataGenEx,     # Phase 1b - excited/diverse dataset
	[switch]$SkipTrain,         # Phase 2  - PINN training
	[switch]$SkipValidate,      # Phase 3  - PINN validation metrics
	[switch]$SkipCalibrate,     # Phase 4  - RC baseline calibration
	[switch]$SkipMpcRc,         # Phase 5a - MPC closed-loop (RC predictor)
	[switch]$SkipMpcPinn,       # Phase 5b - MPC closed-loop (PINN predictor)
	[switch]$SkipCompare,       # Phase 6  - Result aggregation
	[switch]$SkipPlots,         # Phase 7  - Publication plots
	[switch]$SkipCsvExport,     # Phase 8  - CSV dataset & audit export
	# Dataset options
	[string]$DataGenManifest  = "manifests/episode_split_phase1_30day.yaml",
	[string]$DataGenOutput    = "datasets/phase1_singlezone",
	[string]$ExcitedManifest  = "manifests/episode_split_phase1_excited.yaml",
	[string]$ExcitedOutput    = "datasets/phase1_excited",
	# Training options
	[string]$TrainDataset     = "datasets/phase1_excited",      # default to the excited dataset, for standard dataset: /phase1_singlezone
	# MPC options
	[string]$MpcManifest      = "manifests/episode_split_phase1_excited.yaml"
)

$ErrorActionPreference = "Stop"

function Invoke-Phase {
	Param(
		[Parameter(Mandatory = $true)][string]$PhaseName,
		[Parameter(Mandatory = $true)][string]$ScriptName,
		[Parameter(Mandatory = $true)][scriptblock]$Action
	)
	Write-Host ""
	Write-Host "================================================================================"
	Write-Host " $PhaseName"
	Write-Host " Script: $ScriptName"
	Write-Host "================================================================================"
	& $Action
	if ($LASTEXITCODE -ne 0) {
		throw "$ScriptName failed with exit code $LASTEXITCODE"
	}
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$py = Join-Path $root $PythonExe

if (-not (Test-Path $py)) {
	throw "Python executable not found: $py"
}

Push-Location $root
try {
	# --------------------------------------------------------------------------
	# BOPTEST Readiness Gate (conditional on execution of BOPTEST-interactive phases)
	# --------------------------------------------------------------------------
	$needsBoptest = (-not $SkipDataGen) -or (-not $SkipDataGenEx) -or (-not $SkipMpcRc) -or (-not $SkipMpcPinn)
	if ($needsBoptest) {
		$BoptestUrl = "http://127.0.0.1:8000"
		$maxAttempts = 60

		Write-Host ""
		Write-Host "Waiting for BOPTEST web container at $BoptestUrl/version ..."
		$attempt = 0
		while ($attempt -lt $maxAttempts) {
			try {
				$resp = Invoke-WebRequest -Uri "$BoptestUrl/version" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
				if ($resp.StatusCode -eq 200) {
					Write-Host "[OK] Web container is up (attempt $($attempt + 1))."
					break
				}
			}
			catch { }
			$attempt++
			if ($attempt -ge $maxAttempts) {
				throw "BOPTEST web did not respond after $maxAttempts attempts. Start Docker first."
			}
			Start-Sleep -Seconds 2
		}

		Write-Host "Waiting for MinIO-backed /testcases endpoint ..."
		$attempt = 0
		while ($attempt -lt $maxAttempts) {
			try {
				$resp = Invoke-WebRequest -Uri "$BoptestUrl/testcases" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
				if ($resp.StatusCode -eq 200) {
					Write-Host "[OK] BOPTEST stack is fully ready (attempt $($attempt + 1))."
					break
				}
			}
			catch { }
			$attempt++
			if ($attempt -ge $maxAttempts) {
				throw "BOPTEST /testcases endpoint did not respond after $maxAttempts attempts (~$(2*$maxAttempts)s). MinIO may be stuck."
			}
			Start-Sleep -Seconds 2
		}
	} else {
		Write-Host ""
		Write-Host "[Info] Skipping BOPTEST readiness gate (offline phases only)."
	}


	# --------------------------------------------------------------------------
	# Phase 1: Data Generation (standard 30-day episodes)
	# Generates: datasets/phase1_singlezone  (tr_long_*, val_long_*, te_long_*)
	# --------------------------------------------------------------------------
	if (-not $SkipDataGen) {
		Invoke-Phase -PhaseName "Phase 1: Data Generation (standard)" -ScriptName "scripts/generate_boptest_datasets.py" -Action {
			& $py scripts/generate_boptest_datasets.py `
				--manifest $DataGenManifest `
				--output   $DataGenOutput `
				--resume
		}
	} else {
		Write-Host "`n[Skip] Phase 1: Data Generation (standard)"
	}

	# --------------------------------------------------------------------------
	# Phase 1b: Excited Data Generation (diverse setpoints + all 4 seasons)
	# Generates: datasets/phase1_excited  (tr_exc_*, val_exc_*, te_exc_*)
	#
	# Purpose: Provides persistent excitation training data with:
	#   - random_walk  : slow persistent setpoint drifts (hold 1-2 h)
	#   - step_sweep   : hard step changes 19<->24 degC every 4-6 h
	#   - sinusoidal   : smooth modulation across full setpoint range
	# This cures the PINN rollout RMSE issue caused by constant setpoints
	# in the standard dataset (delta_u std ~ 0 previously).
	# --------------------------------------------------------------------------
	if (-not $SkipDataGenEx) {
		Invoke-Phase -PhaseName "Phase 1b: Excited Data Generation (diverse setpoints + 4 seasons)" -ScriptName "scripts/generate_boptest_datasets.py" -Action {
			& $py scripts/generate_boptest_datasets.py `
				--manifest $ExcitedManifest `
				--output   $ExcitedOutput `
				--resume
		}
	} else {
		Write-Host "`n[Skip] Phase 1b: Excited Data Generation"
	}

	# --------------------------------------------------------------------------
	# Phase 2: PINN Training
	# Trains on: $TrainDataset (default: datasets/phase1_singlezone)
	# To train on excited data pass: -TrainDataset datasets/phase1_excited
	# The excited dataset uses configs/pinn_phase1_excited.yaml (wider model,
	# 48-step rollout, L-BFGS finetune) and writes to artifacts/pinn_phase1_excited/
	# --------------------------------------------------------------------------
	if (-not $SkipTrain) {
		if ($TrainDataset -like "*excited*") {
			$trainConfig = "configs/pinn_phase1_excited.yaml"
			$artifactDir = "artifacts/pinn_phase1_excited"
		} else {
			$trainConfig = "configs/pinn_phase1.yaml"
			$artifactDir = "artifacts/pinn_phase1"
		}
		Invoke-Phase -PhaseName "Phase 2: PINN Training (dataset: $TrainDataset)" -ScriptName "scripts/train_pinn.py" -Action {
			& $py scripts/train_pinn.py `
				--config       $trainConfig `
				--artifact-dir $artifactDir `
				--dataset-root $TrainDataset
		}
	} else {
		Write-Host "`n[Skip] Phase 2: PINN Training"
	}

	# --------------------------------------------------------------------------
	# Phase 3: Validation (Table 1 Metrics)
	# --------------------------------------------------------------------------
	if (-not $SkipValidate) {
		if ($TrainDataset -like "*excited*") {
			$ckptVal    = "artifacts/pinn_phase1_excited/best_model.pt"
			$metricsVal = "artifacts/pinn_phase1_excited/metrics.json"
			$configVal  = "configs/pinn_phase1_excited.yaml"
		} else {
			$ckptVal    = "artifacts/pinn_phase1/best_model.pt"
			$metricsVal = "artifacts/pinn_phase1/metrics.json"
			$configVal  = "configs/pinn_phase1.yaml"
		}
		Invoke-Phase -PhaseName "Phase 3: Validation (Table 1 Metrics)" -ScriptName "scripts/validate_pinn_training.py" -Action {
			& $py scripts/validate_pinn_training.py `
				--checkpoint $ckptVal `
				--metrics    $metricsVal `
				--config     $configVal
		}
	} else {
		Write-Host "`n[Skip] Phase 3: Validation"
	}

	# --------------------------------------------------------------------------
	# Phase 4: RC Baseline Setup
	# --------------------------------------------------------------------------
	if (-not $SkipCalibrate) {
		if ($TrainDataset -like "*excited*") {
			$trainConfig = "configs/pinn_phase1_excited.yaml"
		} else {
			$trainConfig = "configs/pinn_phase1_improved.yaml"
		}
		Invoke-Phase -PhaseName "Phase 4: RC Baseline Setup" -ScriptName "scripts/calibrate_rc_baseline.py" -Action {
			& $py scripts/calibrate_rc_baseline.py --config $trainConfig
		}
	} else {
		Write-Host "`n[Skip] Phase 4: RC Baseline Setup"
	}

	# --------------------------------------------------------------------------
	# Phase 5: MPC Closed-Loop (Table 2 & 3 Rollouts)
	# --------------------------------------------------------------------------
	$rcCheckpoint   = "artifacts/rc_baseline_calibrated/rc_calibrated_checkpoint.pt"
	$mpcConfig      = "configs/mpc_phase1.yaml"
	
	if ($TrainDataset -like "*excited*") {
		$pinnCheckpoint = "artifacts/pinn_phase1_excited/best_model.pt"
	} else {
		$pinnCheckpoint = "artifacts/pinn_phase1/best_model.pt"
	}

	if (-not $SkipMpcRc) {
		Invoke-Phase -PhaseName "Phase 5a: MPC Closed-Loop (RC Predictor)" -ScriptName "scripts/run_mpc_episode.py" -Action {
			& $py scripts/run_mpc_episode.py `
				--predictor rc `
				--episode   $MpcEpisode `
				--mpc-config $mpcConfig `
				--checkpoint $rcCheckpoint `
				--manifest   $MpcManifest
		}
	} else {
		Write-Host "`n[Skip] Phase 5a: MPC Closed-Loop (RC Predictor)"
	}

	if (-not $SkipMpcPinn) {
		Invoke-Phase -PhaseName "Phase 5b: MPC Closed-Loop (PINN Predictor)" -ScriptName "scripts/run_mpc_episode.py" -Action {
			& $py scripts/run_mpc_episode.py `
				--predictor pinn `
				--episode   $MpcEpisode `
				--mpc-config $mpcConfig `
				--checkpoint $pinnCheckpoint `
				--manifest   $MpcManifest
		}
	} else {
		Write-Host "`n[Skip] Phase 5b: MPC Closed-Loop (PINN Predictor)"
	}

	# --------------------------------------------------------------------------
	# Phase 6: Result Aggregation
	# --------------------------------------------------------------------------
	if (-not $SkipCompare) {
		Invoke-Phase -PhaseName "Phase 6: Result Aggregation" -ScriptName "scripts/compare_rc_vs_pinn_results.py" -Action {
			& $py scripts/compare_rc_vs_pinn_results.py `
				--episode-stem $MpcEpisode
		}
	} else {
		Write-Host "`n[Skip] Phase 6: Result Aggregation"
	}

	# --------------------------------------------------------------------------
	# Phase 7: Publication Plots
	# --------------------------------------------------------------------------
	if (-not $SkipPlots) {
		Invoke-Phase -PhaseName "Phase 7: Publication Plots" -ScriptName "scripts/generate_conference_plots_v2.py" -Action {
			& $py scripts/generate_conference_plots_v2.py `
				--episode-stem $MpcEpisode
		}
	} else {
		Write-Host "`n[Skip] Phase 7: Publication Plots"
	}

	# --------------------------------------------------------------------------
	# Phase 8: CSV Dataset & Audit Export
	# --------------------------------------------------------------------------
	if (-not $SkipCsvExport) {
		Invoke-Phase -PhaseName "Phase 8: CSV Dataset & Audit Export" -ScriptName "scripts/export_datasets_to_csv.py" -Action {
			& $py scripts/export_datasets_to_csv.py
			& $py scripts/export_closed_loop_to_csv.py --episode $MpcEpisode
			
			if ($TrainDataset -like "*excited*") {
				$datasetJsonDir = "datasets/phase1_excited/json"
				$pinnCkptPath   = "artifacts/pinn_phase1_excited/best_model.pt"
			} else {
				$datasetJsonDir = "datasets/phase1_singlezone/json"
				$pinnCkptPath   = "artifacts/pinn_phase1_building_scale/best_model.pt"
			}
			
			& $py scripts/evaluate_surrogates_open_loop.py --episode $MpcEpisode --dataset-dir $datasetJsonDir --pinn-ckpt $pinnCkptPath
			& $py scripts/plot_open_loop_validation.py --episode $MpcEpisode
		}
	} else {
		Write-Host "`n[Skip] Phase 8: CSV Dataset & Audit Export"
	}

	Write-Host "`n[OK] Full pipeline completed successfully!"
}
finally {
	Pop-Location
}
