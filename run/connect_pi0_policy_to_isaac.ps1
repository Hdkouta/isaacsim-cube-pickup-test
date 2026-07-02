param(
    [Parameter(Mandatory = $true)]
    [string]$PolicyUrl,

    [string]$RepoRoot = "C:\VScode\Yoshida_script",
    [string]$HostPython = "python",
    [string]$IsaacPython = "C:\isaacsim\python.bat",
    [string]$Instruction = "control the ShadowHand to approach, contact, and hold the cube",
    [string]$ContextJson = "configs\policy_request_context.example.json",

    [ValidateSet("data-url", "base64-object", "path")]
    [string]$ImageMode = "data-url",

    [switch]$CaptureObservation,
    [switch]$InstructionOnly,
    [switch]$ApplyInIsaac
)

$ErrorActionPreference = "Stop"

function Invoke-LoggedCommand {
    param(
        [string]$Display,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "COMMAND: $Display"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "command failed with exit code $LASTEXITCODE`: $Display"
    }
}

function Write-CaptureConfig {
    param([string]$Path)

    $json = @"
{
  "reset_from_initial": true,
  "open_hand_on_setup": true,
  "lock_wrist_on_setup": true,
  "apply_action_if_file_exists": false,
  "save_images": true
}
"@
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

Set-Location -LiteralPath $RepoRoot

Write-Host "IsaacSim/pi0 policy connection start"
Write-Host "RepoRoot: $RepoRoot"
Write-Host "PolicyUrl: $PolicyUrl"

if ($CaptureObservation) {
    $configPath = Join-Path $RepoRoot "configs\action_env_config.json"
    $backupPath = "$configPath.connect_backup"
    $hadConfig = Test-Path -LiteralPath $configPath

    if ($hadConfig) {
        Copy-Item -LiteralPath $configPath -Destination $backupPath -Force
    }

    try {
        Write-CaptureConfig -Path $configPath
        Invoke-LoggedCommand `
            "$IsaacPython run\send_script_to_isaac.py eval\apply_action_env.py  # capture observation only" `
            { & $IsaacPython "run\send_script_to_isaac.py" "eval\apply_action_env.py" }
    }
    finally {
        if ($hadConfig) {
            Move-Item -LiteralPath $backupPath -Destination $configPath -Force
        }
        elseif (Test-Path -LiteralPath $configPath) {
            Remove-Item -LiteralPath $configPath -Force
        }
    }
}

$requestArgs = @(
    "run\request_pi0_policy_action.py",
    "--policy-url", $PolicyUrl,
    "--instruction", $Instruction,
    "--image-mode", $ImageMode,
    "--output-action", "configs\action_input.json",
    "--validate-images"
)

if (-not $InstructionOnly) {
    $requestArgs += @("--latest-eval-images")
}

if ($ContextJson -and (Test-Path -LiteralPath (Join-Path $RepoRoot $ContextJson))) {
    $requestArgs += @("--context-json", $ContextJson)
}

Invoke-LoggedCommand `
    "$HostPython $($requestArgs -join ' ')" `
    { & $HostPython @requestArgs }

if ($ApplyInIsaac) {
    Invoke-LoggedCommand `
        "$IsaacPython run\send_script_to_isaac.py eval\apply_action_env.py" `
        { & $IsaacPython "run\send_script_to_isaac.py" "eval\apply_action_env.py" }
}

Write-Host ""
Write-Host "DONE: pi0 policy response was converted to configs\action_input.json"
if (-not $ApplyInIsaac) {
    Write-Host "Next apply command:"
    Write-Host "& $IsaacPython $RepoRoot\run\send_script_to_isaac.py $RepoRoot\eval\apply_action_env.py"
}
