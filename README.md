# Isaac Sim ShadowHand cube pickup test

Scripts for driving a ShadowHand cube grasp scene in Isaac Sim from VS Code.

The current control is scripted teacher-data generation, not direct pi0 control. The scripts save RGB camera observations, scene state, and actions so the run can be converted into imitation-learning / pi0 fine-tuning data.

## Paths used on the Isaac Sim machine

```powershell
C:\isaacsim\python.bat
C:\VScode\Yoshida_script
C:\robot_assets\shadow_hand_initial.json
```

Teacher data is written to:

```text
C:\VScode\Yoshida_script\teacher_data\<run_id>\
```

Camera snapshots are written to:

```text
C:\VScode\Yoshida_script\camera\<timestamp>\
```

## Setup

1. Open Isaac Sim and load the ShadowHand + Cube scene.
2. Run `isaac_vscode_bridge.py` once in the Isaac Sim Script Editor.
3. Copy this repository's `.py` files into:

```text
C:\VScode\Yoshida_script
```

4. From VS Code PowerShell, send scripts to Isaac Sim with:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu2.py
```

## Normal execution order

Run while stopped:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu1.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu2.py
```

Then in Isaac Sim: `File > Save`, then press `Play`.

Run after Play:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu3.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu4a.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu4b.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu4c.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu5a.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu5b.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu5c.py
```

Optional camera-only capture:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu6.py
```

## Merge teacher logs for machine learning

After collecting teacher-data runs, merge all `steps.jsonl` files into one ML-ready dataset:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\merge_teacher_data.py
```

Outputs are written to:

```text
C:\VScode\Yoshida_script\teacher_data_merged\<timestamp>\
```

Generated files:

| File | Purpose |
| --- | --- |
| `dataset.jsonl` | One training example per line. Use this first for fine-tuning. |
| `dataset.json` | Same data as JSON array for inspection. |
| `dataset_index.csv` | Lightweight table for checking phases, actions, cube pose, image counts. |
| `summary.json` | Counts by run/script/phase/action and source file list. |

To also copy referenced JPGs into the merged folder:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\merge_teacher_data.py --copy-images
```

## Prepare ShadowHand action fine-tuning data

For the first pi0/VLA fine-tuning pass, do not require a successful lift. Convert the current logs into image-state -> action samples for learning how ShadowHand should move from each visual state:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\prepare_shadowhand_action_dataset.py
```

Default behavior:

- Task instruction becomes `control the ShadowHand to approach, contact, and hold the cube`.
- Action schema is 20D: 17 ShadowHand joint targets + `hand_dx`, `hand_dy`, `hand_dz`.
- Lift attempts from `scripu5b` are excluded by default.
- Partial joint commands are completed by carrying forward the previous target in the same run.
- Cube XY motion is measured and labeled as `stable` or `large_push` for debugging.

Outputs are written to:

```text
C:\VScode\Yoshida_script\shadowhand_action_dataset\<timestamp>\
```

Generated files:

| File | Purpose |
| --- | --- |
| `shadowhand_action_dataset.jsonl` | Main fine-tuning dataset. Each line is one image-state -> 20D action sample. |
| `schema.json` | Action dimension order, units, and construction rules. |
| `dataset_index.csv` | Quick check of observation/action pairing, behavior tags, hand delta, and cube motion. |
| `action_debug.csv` | Full 20D action vector expanded into columns. |
| `skipped_steps.csv` | Steps not used for initial action learning and the reason. |
| `summary.json` | Counts by run, behavior, phase, action type, cube-motion label, and action min/max. |
| `preview.txt` | Human-readable examples like `this image state -> this action`. |

To copy referenced images into the output folder:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\prepare_shadowhand_action_dataset.py --copy-images
```

Later, when lift behavior is ready to train, include lift steps explicitly:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\prepare_shadowhand_action_dataset.py --include-lift-steps
```

## Script roles

| File | Role |
| --- | --- |
| `isaac_vscode_bridge.py` | Run once in Isaac Sim Script Editor. Opens localhost bridge. |
| `merge_teacher_data.py` | Merge all teacher-data logs into ML-ready JSONL/CSV/summary files. |
| `prepare_shadowhand_action_dataset.py` | Convert teacher logs into 20D ShadowHand image-state -> action samples for initial pi0/VLA fine-tuning. |
| `send_to_isaac.py` | VS Code-side sender. |
| `scripu1.py` | Save current hand/cube pose, cube scale, size, mass, and table height. |
| `scripu2.py` | Restore saved state, define common helpers, initialize cameras, start teacher-data run. |
| `scripu3.py` | Read-only status check. |
| `scripu_run_all.py` | Combined approach/contact/hold/lift/return sequence with teacher-data logging. |
| `scripu4a.py` | Approach: open hand and move to saved initial pose offset. Edit `TUNE_DX/Y/Z` in this file for 1-2 mm corrections. |
| `scripu4b.py` | Weak preshape + thumb/middle contact. |
| `scripu4c.py` | Weak support-finger contact + final light contact. |
| `scripu5a.py` | Wrist lock + weak hold. |
| `scripu5b.py` | Small lift steps, recording teacher data per step. |
| `scripu5c.py` | Return hand to saved initial pose. |
| `scripu6.py` | Save all camera images. |

## Current grasp tuning

The scripts include conservative tuning for the latest failure mode where the cube slid sideways during hold:

- Cube mass is overridden to `0.0025 kg` in `scripu2.py`.
- Cube friction is increased to static `6.0`, dynamic `5.0`.
- Finger/link material friction is increased to static `5.0`, dynamic `4.0`.
- Cube damping is increased to reduce bouncing/sliding.
- `scripu4a.py` now uses a smaller approach offset: `dx=0.002`, `dy=-0.002`, `dz=-0.002`.
- `scripu4a.py` also includes `TUNE_DX`, `TUNE_DY`, `TUNE_DZ` for small one-off approach-position corrections.
- `scripu5a.py` uses weaker hold targets and lower max force to avoid pushing the cube out.
- `scripu5b.py` uses small scoop-lift steps: `dx=0.0002`, `dz=0.0015`, `12` steps.

Tune these constants in `scripu2.py` first before changing the phase scripts.

## pi0 fine-tuning target

The current pi0 placeholder output (`vx`, `vy`, `vz`, `gripper`) is not enough for ShadowHand. The first fine-tuning target should be image-state -> ShadowHand action, not full lift success. Use the 20D action schema:

```json
{
  "action_schema": "shadowhand_joint17_handdelta3_v1",
  "joint_targets": {
    "FFJ3": 12,
    "FFJ2": 16,
    "FFJ1": 12,
    "MFJ3": 26,
    "MFJ2": 34,
    "MFJ1": 26,
    "RFJ3": 12,
    "RFJ2": 16,
    "RFJ1": 12,
    "LFJ4": 6,
    "LFJ3": 12,
    "LFJ2": 16,
    "LFJ1": 12,
    "THJ4": 34,
    "THJ3": 38,
    "THJ2": 36,
    "THJ1": 28
  },
  "hand_delta": [0.0, 0.0, -0.002],
  "behavior_tag": "support_contact"
}
```

Use `prepare_shadowhand_action_dataset.py` first. After pi0 can produce reasonable approach/contact/hold behavior, collect lift-specific data and rerun with `--include-lift-steps`.
