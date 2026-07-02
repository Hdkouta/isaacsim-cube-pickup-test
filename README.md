# Isaac Sim ShadowHand pi0 action dataset

This repository is now optimized for the pi0/VLA workflow:

- build and inspect `image state -> ShadowHand 20D action` datasets
- evaluate one 20D action in Isaac Sim
- keep uploaded public data snapshots for analysis outside the Isaac Sim machine

The old scripted pickup/lift step files were removed. Use the uploaded data and the tools below as the main workflow.

## Current folder layout

| Folder | Purpose |
| --- | --- |
| `bridge` | Isaac Sim bridge script. Run this once in Isaac Sim Script Editor. |
| `run` | VS Code/PowerShell sender for scripts that must execute inside Isaac Sim. |
| `eval` | One-action evaluation environment and preset writer. |
| `data_tools` | Dataset merge, conversion, and eval-log aggregation tools. |
| `configs` | Example config/action JSON files. Runtime JSON files are ignored. |
| `data_public` | Uploaded runtime data snapshot for GitHub browsing/analysis. |
| `results` | Runtime output location guide. |

## Local paths

```text
C:\isaacsim\python.bat
C:\VScode\Yoshida_script
C:\robot_assets\shadow_hand_initial.json
```

Runtime output folders are ignored by git:

```text
C:\VScode\Yoshida_script\teacher_data
C:\VScode\Yoshida_script\teacher_data_merged
C:\VScode\Yoshida_script\shadowhand_action_dataset
C:\VScode\Yoshida_script\pi0_action_eval
C:\VScode\Yoshida_script\pi0_action_eval_merged
C:\VScode\Yoshida_script\camera
```

## Data already uploaded

The latest public snapshot includes:

```text
data_public\teacher_data
data_public\shadowhand_action_dataset\20260702_041002
data_public\pi0_action_eval
data_public\pi0_action_eval_merged\20260702_041221
```

Important generated files:

```text
data_public\shadowhand_action_dataset\20260702_041002\pi0_finetune_dataset.jsonl
data_public\shadowhand_action_dataset\20260702_041002\summary.json
data_public\pi0_action_eval_merged\20260702_041221\pi0_eval_action_debug.csv
data_public\pi0_action_eval_merged\20260702_041221\summary.json
```

Current dataset snapshot:

- `total_samples`: 14
- behavior tags: `preshape_contact`, `support_contact`, `hold`
- cube motion labels: 13 `stable`, 1 `large_push`
- action schema: `shadowhand_joint17_handdelta3_v1`

## 20D action schema

The model action is:

```text
17 ShadowHand joint targets + 3 hand deltas
```

Dimension order:

```text
FFJ3, FFJ2, FFJ1,
MFJ3, MFJ2, MFJ1,
RFJ3, RFJ2, RFJ1,
LFJ4, LFJ3, LFJ2, LFJ1,
THJ4, THJ3, THJ2, THJ1,
hand_dx, hand_dy, hand_dz
```

Joint targets are degrees. Hand deltas are meters.

## Recommended next steps

1. Inspect the uploaded fine-tuning dataset:

```powershell
Get-Content C:\VScode\Yoshida_script\data_public\shadowhand_action_dataset\20260702_041002\pi0_finetune_dataset.jsonl -TotalCount 2
```

2. Start pi0/VLA fine-tuning with:

```text
C:\VScode\Yoshida_script\data_public\shadowhand_action_dataset\20260702_041002\pi0_finetune_dataset.jsonl
```

If the JSONL still contains Isaac Sim machine paths such as `C:\VScode\Yoshida_script\teacher_data\...`, create a repo-local copy first:

```powershell
python .\data_tools\convert_dataset_for_pi0.py `
  --input-jsonl .\data_public\shadowhand_action_dataset\20260702_041002\shadowhand_action_dataset.jsonl `
  --output-jsonl .\data_public\shadowhand_action_dataset\20260702_041002\pi0_finetune_dataset_local.jsonl `
  --validate-images
```

3. After training, write a predicted 20D action to:

```text
C:\VScode\Yoshida_script\configs\action_input.json
```

4. Or request a predicted 20D action from the pi0 policy API:

```powershell
.\run\connect_pi0_policy_to_isaac.ps1 `
  -PolicyUrl "http://<PI0_VM_IP>:8000/<POLICY_ENDPOINT>" `
  -CaptureObservation
```

This captures an Isaac Sim observation image set, POSTs it to the pi0 VM, validates the 20D response, and writes:

```text
C:\VScode\Yoshida_script\configs\action_input.json
```

5. Run the predicted action in Isaac Sim:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\eval\apply_action_env.py
```

If the start-state file is missing or you intentionally changed the scene pose, save the current ShadowHand/Cube state first:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\eval\save_start_state.py
```

6. Merge evaluation logs:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\data_tools\merge_action_eval_logs.py
```

7. Judge results from:

```text
C:\VScode\Yoshida_script\pi0_action_eval_merged\<timestamp>\pi0_eval_action_debug.csv
```

Primary success criteria for the first stage:

- fingers move according to the intended action stage
- cube remains `stable`
- cube XY motion stays under about `0.001 m`
- approach/contact/hold sequence is consistent

Do not target lift first. Lift should be added after the policy reliably produces stable approach/contact/hold actions.

## Connect Isaac Sim VM to pi0 policy VM

Use this when fine-tuning/inference is running on a pi0 VM and Isaac Sim evaluation is running on the Windows Isaac Sim VM.

1. On the pi0 VM, start the policy API so it listens outside the VM:

```bash
python serve_policy.py --host 0.0.0.0 --port 8000
```

Use the actual endpoint path exposed by your server, for example `/predict` or `/act`.

2. On the Isaac Sim VM, confirm the network route:

```powershell
Test-NetConnection <PI0_VM_IP> -Port 8000
```

3. In Isaac Sim, load the ShadowHand + Cube scene, press **Play**, and run `bridge\isaac_bridge_server.py` once in the Script Editor.

4. Capture the current observation, call the pi0 API, and write `configs\action_input.json`:

```powershell
cd C:\VScode\Yoshida_script
.\run\connect_pi0_policy_to_isaac.ps1 `
  -PolicyUrl "http://<PI0_VM_IP>:8000/<POLICY_ENDPOINT>" `
  -CaptureObservation
```

The wrapper calls:

```powershell
& C:\isaacsim\python.bat .\run\send_script_to_isaac.py .\eval\apply_action_env.py
python .\run\request_pi0_policy_action.py --policy-url "http://<PI0_VM_IP>:8000/<POLICY_ENDPOINT>" --latest-eval-images --output-action .\configs\action_input.json
```

`request_pi0_policy_action.py` checks:

```text
ok_true
schema_ok
vector_len_20
joint_targets_len_17
hand_delta_len_3
axis_names_len_20
```

It writes the full API request/response under `results\policy_api\<timestamp>` and writes the Isaac Sim action file to `configs\action_input.json`.

5. Apply the action in Isaac Sim:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\eval\apply_action_env.py
```

Or do capture, API request, and Isaac application in one wrapper call:

```powershell
.\run\connect_pi0_policy_to_isaac.ps1 `
  -PolicyUrl "http://<PI0_VM_IP>:8000/<POLICY_ENDPOINT>" `
  -CaptureObservation `
  -ApplyInIsaac
```

If the policy API expects image paths instead of base64 image data, add:

```powershell
-ImageMode path
```

## Rebuild datasets from local teacher logs

If you collect more `teacher_data`, rebuild the training dataset:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\data_tools\make_shadowhand_action_dataset.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\data_tools\convert_dataset_for_pi0.py
```

The compact pi0 file is:

```text
C:\VScode\Yoshida_script\shadowhand_action_dataset\<timestamp>\pi0_finetune_dataset.jsonl
```

## Evaluate known action presets

The eval environment resets from `C:\robot_assets\shadow_hand_initial.json` by default. Therefore preset actions include the approach hand delta by default.

Write a preset:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\eval\set_action_preset.py --preset thumb_middle_contact
```

Apply it in Isaac Sim:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\eval\apply_action_env.py
```

Available presets:

```text
approach_only
preshape
thumb_middle_contact
support_contact
final_light_contact
hold_close
final_hold
```

If you intentionally apply actions sequentially without resetting the hand, override the delta:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\eval\set_action_preset.py --preset final_light_contact --hand-delta 0 0 0
```

## Runtime config files

Tracked examples:

```text
configs\action_env_config.example.json
configs\action_input_template.example.json
configs\action_input_hold_example.json
```

Runtime files, ignored by git:

```text
configs\action_env_config.json
configs\action_input.json
configs\action_input_template.json
```

## Legacy note

The previous `scripu1.py` to `scripu6.py` / `run_steps` trajectory scripts are no longer part of the optimized workflow. The repository now focuses on reusable datasets, 20D action conversion, and Isaac Sim action evaluation.
