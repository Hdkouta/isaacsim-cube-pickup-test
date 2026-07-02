# Run Steps Split

This folder is split into smaller groups.

## pickup

Pickup start and contact phase (old scripu1 to scripu6):

- pickup/step1_save_start_state.py
- pickup/step2_setup_teacher_env.py
- pickup/step3_check_state.py
- pickup/step4_approach.py
- pickup/step5_preshape_contact.py
- pickup/step6_support_contact.py

## finish

After pickup contact:

- finish/step7_hold.py
- finish/step8_lift_try.py
- finish/step9_return.py

## tools

Utility scripts:

- tools/step10_save_camera_images.py
- tools/reset_hand_start_state.py

## flow

One-shot full sequence:

- flow/run_all_steps.py
