param(
    [Parameter(Mandatory = $true)]
    [string]$PolicyUrl,

    [string]$RepoRoot = "C:\VScode\Yoshida_script",
    [string]$HostPython = "python",
    [string]$IsaacPython = "C:\isaacsim\python.bat",

    [ValidateSet("data-url", "base64-object", "path")]
    [string]$ImageMode = "data-url",

    [switch]$SaveStartState,
    [switch]$SkipMergeLogs,
    [switch]$NoInitialReset
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

$Pi0Stages = @(
    [ordered]@{
        script = "scripu4a"
        phase = "approach"
        title = "approach hand toward cube"
        instruction = "Move the ShadowHand base toward the cube with the safe approach delta. Keep the hand open and avoid touching or pushing the cube. Return one safe 20D action."
        stage_goal = "approach_only"
        expected_motion = "Use hand_delta mainly for approach. Keep joint targets close to open or weak preshape."
    },
    [ordered]@{
        script = "scripu5a"
        phase = "weak_preshape"
        title = "weak preshape"
        instruction = "Make a weak ShadowHand preshape around the cube. Keep hand_delta near zero unless a tiny correction is needed. Do not push the cube sideways. Return one safe 20D action."
        stage_goal = "preshape_contact"
        expected_motion = "Begin closing fingers lightly: FF/RF/LF small, middle and thumb modest."
    },
    [ordered]@{
        script = "scripu5b"
        phase = "thumb_middle_contact"
        title = "thumb and middle light contact"
        instruction = "Use the thumb and middle finger to make light contact with the cube. Keep support fingers gentle and avoid large cube motion. Return one safe 20D action."
        stage_goal = "thumb_middle_contact"
        expected_motion = "Increase MFJ and THJ targets while keeping hand_delta near zero."
    },
    [ordered]@{
        script = "scripu6a"
        phase = "support_contact"
        title = "add support fingers"
        instruction = "Add index, ring, and little finger support contact lightly while maintaining thumb and middle contact. Keep the cube stable. Return one safe 20D action."
        stage_goal = "support_contact"
        expected_motion = "Increase FF/RF/LF support targets gently, keep hand_delta near zero."
    },
    [ordered]@{
        script = "scripu6b"
        phase = "final_light_contact"
        title = "final light contact"
        instruction = "Set the ShadowHand to the final light contact pose around the cube. Hold the cube without lifting yet and avoid sideways push. Return one safe 20D action."
        stage_goal = "final_light_contact"
        expected_motion = "Use a stronger but still safe contact target for all fingers, hand_delta near zero."
    }
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
        [bool]$ApplyAction,
        [string]$ActionPath
    )

    $config = [ordered]@{
        reset_from_initial = $ResetFromInitial
        open_hand_on_setup = $OpenHandOnSetup
        lock_wrist_on_setup = $true
        apply_action_if_file_exists = $ApplyAction
        action_file = $ActionPath
        action_template_file = (Join-Path $RepoRoot "configs\action_input_template.json")
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

function Write-ScripuStageContext {
    param(
        [string]$Path,
        [object]$Stage,
        [int]$StageIndex,
        [int]$StageCount,
        [string]$SequenceId
    )

    $context = [ordered]@{
        task = "shadowhand_cube_scripu1_to_6_with_pi0_policy"
        action_schema = $ActionSchemaName
        expected_axis_names = $AxisNames
        units = [ordered]@{
            joint_targets = "degrees"
            hand_delta = "meters"
        }
        sequence_id = $SequenceId
        stage_index = $StageIndex
        stage_count = $StageCount
        old_script_equivalent = $Stage.script
        phase = $Stage.phase
        stage_goal = $Stage.stage_goal
        instruction = $Stage.instruction
        expected_motion = $Stage.expected_motion
        legacy_mapping = [ordered]@{
            scripu1 = "save current ShadowHand/Cube start state"
            scripu2 = "reset/setup teacher env, open hand, lock wrist"
            scripu3 = "check current state and capture observation"
            scripu4 = "approach hand toward cube"
            scripu5 = "weak preshape and thumb/middle light contact"
            scripu6 = "add support fingers and final light contact"
        }
        success_criteria = [ordered]@{
            action_schema = $ActionSchemaName
            vector_length = 20
            joint_targets = 17
            hand_delta = 3
            prefer_cube_xy_motion_m_max = 0.001
            lift_not_required = $true
        }
    }

    $json = $context | ConvertTo-Json -Depth 20
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Invoke-CaptureObservation {
    param(
        [string]$Label,
        [bool]$ResetFromInitial,
        [bool]$OpenHandOnSetup,
        [string]$ConfigPath,
        [string]$ActionPath
    )

    Write-Host ""
    Write-Host "===== capture observation: $Label ====="
    Write-ActionEnvConfig `
        -Path $ConfigPath `
        -ResetFromInitial $ResetFromInitial `
        -OpenHandOnSetup $OpenHandOnSetup `
        -ApplyAction $false `
        -ActionPath $ActionPath

    Invoke-LoggedCommand `
        "$IsaacPython run\send_script_to_isaac.py eval\apply_action_env.py  # capture only: $Label" `
        { & $IsaacPython "run\send_script_to_isaac.py" "eval\apply_action_env.py" }
}

Set-Location -LiteralPath $RepoRoot

$SequenceId = Get-Date -Format "yyyyMMdd_HHmmss"
$SequenceDir = Join-Path $RepoRoot "results\pi0_scripu1_6_sequence\$SequenceId"
New-Item -ItemType Directory -Force -Path $SequenceDir | Out-Null

$ConfigPath = Join-Path $RepoRoot "configs\action_env_config.json"
$ConfigBackupPath = Join-Path $SequenceDir "action_env_config.backup.json"
$ActionPath = Join-Path $RepoRoot "configs\action_input.json"
$ContextPath = Join-Path $SequenceDir "pi0_scripu_stage_context.json"

$HadConfig = Test-Path -LiteralPath $ConfigPath
if ($HadConfig) {
    Copy-Item -LiteralPath $ConfigPath -Destination $ConfigBackupPath -Force
}

Write-Host "pi0 scripu1-6 sequence start"
Write-Host "RepoRoot: $RepoRoot"
Write-Host "PolicyUrl: $PolicyUrl"
Write-Host "SequenceDir: $SequenceDir"
Write-Host "ImageMode: $ImageMode"

try {
    if ($SaveStartState) {
        Write-Host ""
        Write-Host "===== scripu1 equivalent: save start state ====="
        Invoke-LoggedCommand `
            "$IsaacPython run\send_script_to_isaac.py eval\save_start_state.py" `
            { & $IsaacPython "run\send_script_to_isaac.py" "eval\save_start_state.py" }
    }

    $ShouldReset = -not $NoInitialReset
    Invoke-CaptureObservation `
        -Label "scripu2_setup_teacher_env" `
        -ResetFromInitial $ShouldReset `
        -OpenHandOnSetup $ShouldReset `
        -ConfigPath $ConfigPath `
        -ActionPath $ActionPath

    Invoke-CaptureObservation `
        -Label "scripu3_check_state" `
        -ResetFromInitial $false `
        -OpenHandOnSetup $false `
        -ConfigPath $ConfigPath `
        -ActionPath $ActionPath

    for ($Index = 0; $Index -lt $Pi0Stages.Count; $Index++) {
        $Stage = $Pi0Stages[$Index]
        $StageNumber = $Index + 1
        Write-Host ""
        Write-Host "===== pi0 stage $StageNumber / $($Pi0Stages.Count): $($Stage.script) $($Stage.phase) ====="

        Invoke-CaptureObservation `
            -Label "$($Stage.script)_before_$($Stage.phase)" `
            -ResetFromInitial $false `
            -OpenHandOnSetup $false `
            -ConfigPath $ConfigPath `
            -ActionPath $ActionPath

        Write-ScripuStageContext `
            -Path $ContextPath `
            -Stage $Stage `
            -StageIndex $StageNumber `
            -StageCount $Pi0Stages.Count `
            -SequenceId $SequenceId

        $RequestArgs = @(
            "run\request_pi0_policy_action.py",
            "--policy-url", $PolicyUrl,
            "--instruction", $Stage.instruction,
            "--latest-eval-images",
            "--image-mode", $ImageMode,
            "--context-json", $ContextPath,
            "--output-action", "configs\action_input.json",
            "--validate-images"
        )

        Invoke-LoggedCommand `
            "$HostPython $($RequestArgs -join ' ')" `
            { & $HostPython @RequestArgs }

        $StepActionCopy = Join-Path $SequenceDir ("{0:00}_{1}_{2}_action.json" -f $StageNumber, $Stage.script, $Stage.phase)
        Copy-Item -LiteralPath $ActionPath -Destination $StepActionCopy -Force

        Write-ActionEnvConfig `
            -Path $ConfigPath `
            -ResetFromInitial $false `
            -OpenHandOnSetup $false `
            -ApplyAction $true `
            -ActionPath $ActionPath

        Invoke-LoggedCommand `
            "$IsaacPython run\send_script_to_isaac.py eval\apply_action_env.py  # apply $($Stage.script) $($Stage.phase)" `
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
Write-Host "DONE: pi0 scripu1-6 sequence finished"
Write-Host "SequenceDir: $SequenceDir"
Write-Host "Latest action file: $ActionPath"
Write-Host "Check pi0_action_eval_merged for cube motion and contact stability."
