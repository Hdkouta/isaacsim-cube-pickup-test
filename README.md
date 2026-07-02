# Isaac Sim Cube Pickup Test

This repository is an optimized, clean version of Yoshida_script.

Goal now:
- learn image state -> ShadowHand 20D action
- focus on approach/contact/hold stability
- add lift tuning later

## Folders

- bridge: Isaac Sim bridge script (run in Script Editor)
- run: send script from VS Code to Isaac Sim
- run_steps: main execution scripts (simple English names)
- eval: apply one action and evaluate before/after
- data_tools: merge logs and build datasets
- configs: JSON examples and runtime JSON location
- results: output folder guide

## Local paths used

- C:\isaacsim\python.bat
- C:\VScode\Yoshida_script
- C:\robot_assets\shadow_hand_initial.json

Runtime output folders (ignored in git):
- C:\VScode\Yoshida_script\teacher_data
- C:\VScode\Yoshida_script\teacher_data_merged
- C:\VScode\Yoshida_script\shadowhand_action_dataset
- C:\VScode\Yoshida_script\pi0_action_eval
- C:\VScode\Yoshida_script\pi0_action_eval_merged
- C:\VScode\Yoshida_script\camera

## 1) Bridge setup

Run once in Isaac Sim Script Editor:

- bridge/isaac_bridge_server.py

## 2) Teacher run order

Run while STOP:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\run_steps\step1_save_start_state.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\run_steps\step2_setup_teacher_env.py
```

In Isaac Sim: Save stage, then Play.

Run after Play:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\run_steps\step3_check_state.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\run_steps\step4_approach.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\run_steps\step5_preshape_contact.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\run_steps\step6_support_contact.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\run_steps\step7_hold.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\run_steps\step8_lift_try.py
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\run_steps\step9_return.py
```

Optional camera save:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\run_steps\step10_save_camera_images.py
```

## 3) Build dataset for pi0

Merge teacher logs:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\data_tools\merge_teacher_logs.py
```

Create image -> 20D action dataset:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\data_tools\make_shadowhand_action_dataset.py
```

Convert to compact pi0 JSONL:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\data_tools\convert_dataset_for_pi0.py
```

## 4) Evaluate one action in Isaac Sim

Write preset action JSON:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\eval\set_action_preset.py --preset thumb_middle_contact
```

Apply action and record before/after:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\run\send_script_to_isaac.py C:\VScode\Yoshida_script\eval\apply_action_env.py
```

Merge eval logs:

```powershell
& C:\isaacsim\python.bat C:\VScode\Yoshida_script\data_tools\merge_action_eval_logs.py
```

## Config files

Tracked examples:
- configs/action_env_config.example.json
- configs/action_input_template.example.json
- configs/action_input_hold_example.json

Runtime files (ignored):
- configs/action_env_config.json
- configs/action_input.json
- configs/action_input_template.json

## Action presets

set_action_preset.py supports:
- approach_only
- preshape
- thumb_middle_contact
- support_contact
- final_light_contact
- final_hold

## Old name -> new name

- isaac_vscode_bridge.py -> bridge/isaac_bridge_server.py
- send_to_isaac.py -> run/send_script_to_isaac.py
- scripu1.py -> run_steps/step1_save_start_state.py
- scripu2.py -> run_steps/step2_setup_teacher_env.py
- scripu3.py -> run_steps/step3_check_state.py
- scripu4a.py -> run_steps/step4_approach.py
- scripu4b.py -> run_steps/step5_preshape_contact.py
- scripu4c.py -> run_steps/step6_support_contact.py
- scripu5a.py -> run_steps/step7_hold.py
- scripu5b.py -> run_steps/step8_lift_try.py
- scripu5c.py -> run_steps/step9_return.py
- scripu6.py -> run_steps/step10_save_camera_images.py
- scripu_run_all.py -> run_steps/run_all_steps.py
- scripu_reset_initial.py -> run_steps/reset_hand_start_state.py
- apply_shadowhand_action_env.py -> eval/apply_action_env.py
- set_pi0_shadowhand_action.py -> eval/set_action_preset.py
- merge_teacher_data.py -> data_tools/merge_teacher_logs.py
- prepare_shadowhand_action_dataset.py -> data_tools/make_shadowhand_action_dataset.py
- merge_pi0_action_eval.py -> data_tools/merge_action_eval_logs.py
- convert_shadowhand_dataset_to_pi0.py -> data_tools/convert_dataset_for_pi0.py
