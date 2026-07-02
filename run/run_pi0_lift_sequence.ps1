param(
    [Parameter(Mandatory = $true)]
    [string]$PolicyUrl,

    [string]$RepoRoot = "C:\VScode\Yoshida_script",
    [string]$HostPython = "python",
    [string]$IsaacPython = "C:\isaacsim\python.bat",
    [int]$Steps = 6,
    [string]$Instruction = "Use the ShadowHand to approach, grasp, hold, and lift the cube upward. Keep the cube stable and avoid pushing it sideways.",

    [ValidateSet("data-url", "base64-object", "path")]
    [string]$ImageMode = "data-url",

    [switch]$NoInitialReset,
    [switch]$SkipMergeLogs
)

$ErrorActionPreference = "Stop"

$ActionSchemaName = "shadowhand_joint17_handdelta3_v1"
$AxisNames = @(
    "FFJ3", "FFJ2", "FFJ1",
    "MFJ3", "MFJ2", "MFJ1",
    "RFJ3", "RFJ2", "RFJ1",
    "LFJ4", "LFJ3", "LFJ2", "LFJ1",
    "THJ4", "THJ3", "THJ2", "THJ1",
    "hand_dx", "hand_dy", "hand_dz"
)

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

function Write-ActionEnvConfig {
    param(
        [string]$Path,
        [bool]$ResetFromInitial,
        [bool]$OpenHandOnSetup,
        [bool]$ApplyAction
    )

    $config = [ordered]@{
        reset_from_initial = $ResetFromInitial
        open_hand_on_setup = $OpenHandOnSetup
        lock_wrist_on_setup = $true
        apply_action_if_file_exists = $ApplyAction
        action_file = "C:\VScode\Yoshida_script\configs\action_input.json"
        action_template_file = "C:\VScode\Yoshida_script\configs\action_input_template.json"
        save_images = $true
        save_stage_after_setup = $false
        wait_after_setup_steps = 20
        wait_after_hand_delta_steps = 24
        wait_after_joint_steps = 80
        max_abs_hand_delta_m = 0.04
    }

    $json = $config | ConvertTo-Json -Depth 20
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Write-LiftStepContext {
    param(
        [string]$Path,
        [int]$StepIndex,
        [int]$StepCount,
        [string]$SequenceId,
        [string]$InstructionText
    )

    $context = [ordered]@{
        task = "shadowhand_cube_lift_with_pi0_policy"
        action_schema = $ActionSchemaName
        expected_axis_names = $AxisNames
        units = [ordered]@{
            joint_targets = "degrees"
            hand_delta = "meters"
        }
        stage_goal = "approach_contact_hold_lift"
        lift_policy_note = "Use positive hand_dz only after contact or hold is stable. Keep hand_dx and hand_dy small to avoid sideways cube push."
        sequence_id = $SequenceId
        step_index = $StepIndex
        step_count = $StepCount
        instruction = $InstructionText
        success_criteria = [ordered]@{
            action_schema = $ActionSchemaName
            vector_length = 20
            joint_targets = 17
            hand_delta = 3
            prefer_cube_z_increase = $true
            prefer_cube_xy_motion_m_max = 0.001
        }
    }

    $json = $context | ConvertTo-Json -Depth 20
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

if ($Steps -lt 1) {
    throw "Steps must be >= 1"
}

Set-Location -LiteralPath $RepoRoot

$SequenceId = Get-Date -Format "yyyyMMdd_HHmmss"
$SequenceDir = Join-Path $RepoRoot "results\pi0_lift_sequence\$SequenceId"
New-Item -ItemType Directory -Force -Path $SequenceDir | Out-Null

$ConfigPath = Join-Path $RepoRoot "configs\action_env_config.json"
$ConfigBackupPath = Join-Path $SequenceDir "action_env_config.backup.json"
$HadConfig = Test-Path -LiteralPath $ConfigPath
if ($HadConfig) {
    Copy-Item -LiteralPath $ConfigPath -Destination $ConfigBackupPath -Force
}

$ContextPath = Join-Path $SequenceDir "pi0_lift_request_context.json"
$ActionPath = Join-Path $RepoRoot "configs\action_input.json"

Write-Host "pi0 lift sequence start"
Write-Host "RepoRoot: $RepoRoot"
Write-Host "PolicyUrl: $PolicyUrl"
Write-Host "Steps: $Steps"
Write-Host "SequenceDir: $SequenceDir"
Write-Host "Instruction: $Instruction"

try {
    for ($Step = 1; $Step -le $Steps; $Step++) {
        $ShouldReset = ($Step -eq 1) -and (-not $NoInitialReset)
        $StepInstruction = "$Instruction Current step: $Step of $Steps. Return one safe 20D ShadowHand action."

        Write-Host ""
        Write-Host "===== pi0 lift step $Step / ${Steps}: capture observation ====="
        Write-ActionEnvConfig `
            -Path $ConfigPath `
            -ResetFromInitial $ShouldReset `
            -OpenHandOnSetup $ShouldReset `
            -ApplyAction $false

        Invoke-LoggedCommand `
            "$IsaacPython run\send_script_to_isaac.py eval\apply_action_env.py  # capture observation only" `
            { & $IsaacPython "run\send_script_to_isaac.py" "eval\apply_action_env.py" }

        Write-LiftStepContext `
            -Path $ContextPath `
            -StepIndex $Step `
            -StepCount $Steps `
            -SequenceId $SequenceId `
            -InstructionText $StepInstruction

        Write-Host ""
        Write-Host "===== pi0 lift step $Step / ${Steps}: request policy action ====="
        $RequestArgs = @(
            "run\request_pi0_policy_action.py",
            "--policy-url", $PolicyUrl,
            "--instruction", $StepInstruction,
            "--latest-eval-images",
            "--image-mode", $ImageMode,
            "--context-json", $ContextPath,
            "--output-action", "configs\action_input.json",
            "--validate-images"
        )

        Invoke-LoggedCommand `
            "$HostPython $($RequestArgs -join ' ')" `
            { & $HostPython @RequestArgs }

        $StepActionCopy = Join-Path $SequenceDir ("action_step_{0:00}.json" -f $Step)
        Copy-Item -LiteralPath $ActionPath -Destination $StepActionCopy -Force

        Write-Host ""
        Write-Host "===== pi0 lift step $Step / ${Steps}: apply policy action in Isaac Sim ====="
        Write-ActionEnvConfig `
            -Path $ConfigPath `
            -ResetFromInitial $false `
            -OpenHandOnSetup $false `
            -ApplyAction $true

        Invoke-LoggedCommand `
            "$IsaacPython run\send_script_to_isaac.py eval\apply_action_env.py  # apply policy action" `
            { & $IsaacPython "run\send_script_to_isaac.py" "eval\apply_action_env.py" }
    }

    if (-not $SkipMergeLogs) {
        Write-Host ""
        Write-Host "===== merge pi0 action eval logs ====="
        Invoke-LoggedCommand `
            "$IsaacPython data_tools\merge_action_eval_logs.py" `
            { & $IsaacPython "data_tools\merge_action_eval_logs.py" }
    }
}
finally {
    if ($HadConfig) {
        Copy-Item -LiteralPath $ConfigBackupPath -Destination $ConfigPath -Force
    }
    elseif (Test-Path -LiteralPath $ConfigPath) {
        Remove-Item -LiteralPath $ConfigPath -Force
    }
}

Write-Host ""
Write-Host "DONE: pi0 lift sequence finished"
Write-Host "SequenceDir: $SequenceDir"
Write-Host "Latest action file: $ActionPath"
Write-Host "Check pi0_action_eval_merged for cube motion and lift behavior."
