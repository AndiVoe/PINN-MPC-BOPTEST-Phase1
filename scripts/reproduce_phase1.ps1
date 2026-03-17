Param(
	[string]$PythonExe = ".venv/Scripts/python.exe",
	[string]$TrainConfig = "configs/pinn_phase1.yaml",
	[string]$MpcConfig = "configs/mpc_phase1.yaml",
	[string]$Checkpoint = "artifacts/pinn_phase1/best_model.pt",
	[switch]$SkipTrain,
	[switch]$SkipMpc,
	[switch]$SkipParity,
	[switch]$SkipBundle,
	[switch]$SkipDiscovery
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
	Param(
		[Parameter(Mandatory = $true)][string]$Name,
		[Parameter(Mandatory = $true)][scriptblock]$Action
	)
	Write-Host ""
	Write-Host "=== $Name ==="
	& $Action
}

function Assert-Ok {
	Param([string]$Context)
	if ($LASTEXITCODE -ne 0) {
		throw "$Context failed with exit code $LASTEXITCODE"
	}
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$py = Join-Path $root $PythonExe

if (-not (Test-Path $py)) {
	throw "Python executable not found: $py"
}

Push-Location $root
try {
	if (-not $SkipDiscovery) {
		Invoke-Step -Name "Discover BOPTEST testcase IDs" -Action {
			& $py scripts/discover_boptest_testcases.py
			if ($LASTEXITCODE -ne 0) {
				Write-Host "Discovery did not fully resolve testcase IDs (exit code $LASTEXITCODE)."
				Write-Host "Continuing pipeline; inspect runtime_discovery artifacts before launching benchmark runs."
			}
		}
	}

	if (-not $SkipTrain) {
		Invoke-Step -Name "Train PINN" -Action {
			& $py scripts/train_pinn.py --config $TrainConfig
			Assert-Ok -Context "Training"
		}
	}

	if (-not $SkipMpc) {
		Invoke-Step -Name "Run MPC with RC predictor" -Action {
			& $py scripts/run_mpc_episode.py --predictor rc --episode all-test --config $MpcConfig
			Assert-Ok -Context "RC test episodes"

			& $py scripts/run_mpc_episode.py --predictor rc --episode all-future-test --config $MpcConfig
			Assert-Ok -Context "RC future-test episodes"
		}

		Invoke-Step -Name "Run MPC with PINN predictor" -Action {
			& $py scripts/run_mpc_episode.py --predictor pinn --episode all-test --config $MpcConfig --checkpoint $Checkpoint
			Assert-Ok -Context "PINN test episodes"

			& $py scripts/run_mpc_episode.py --predictor pinn --episode all-future-test --config $MpcConfig --checkpoint $Checkpoint
			Assert-Ok -Context "PINN future-test episodes"
		}
	}

	if (-not $SkipParity) {
		Invoke-Step -Name "Validate discomfort parity report" -Action {
			& $py scripts/validate_discomfort_parity.py
			Assert-Ok -Context "Discomfort parity validation"
		}
	}

	if (-not $SkipBundle) {
		Invoke-Step -Name "Build publication artifact bundle" -Action {
			& $py scripts/prepare_publication_artifacts.py
			Assert-Ok -Context "Publication artifact bundling"
		}
	}

	Write-Host ""
	Write-Host "Reproduction pipeline completed."
	Write-Host "Parity report: results/mpc_phase1/discomfort_parity_report.csv"
	Write-Host "Bundle index: results/eu_rc_vs_pinn/publication_bundle/file_index.csv"
	Write-Host "Discovery map: results/eu_rc_vs_pinn/runtime_discovery/eu_testcases_resolved_mapping.json"
}
finally {
	Pop-Location
}
