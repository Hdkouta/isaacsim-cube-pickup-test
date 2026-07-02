import json


def move_hand_to(target_pos, steps=24, wait_per_step=2):
    hand, hand_path = get_hand()
    start = get_translate(hand)

    for i in range(steps):
        alpha = float(i + 1) / float(steps)
        pos = [
            start[0] + (target_pos[0] - start[0]) * alpha,
            start[1] + (target_pos[1] - start[1]) * alpha,
            start[2] + (target_pos[2] - start[2]) * alpha,
        ]
        set_translate(hand, pos)
        wait_steps(wait_per_step)

    return target_pos


def log_pose(script_name, phase):
    hand, hand_path = get_hand()
    cube, cube_path = get_cube()
    log_json(phase, {
        "hand_translate": get_translate(hand),
        "cube_translate": get_translate(cube),
    })


data = json.loads(INITIAL_FILE.read_text(encoding="utf-8"))
initial_hand_pos = data["hand_translate"]

record_teacher_step(
    script_name="scripu_run_all",
    phase="before_sequence",
    action={"type": "sequence_start"},
    note="before full grasp sequence",
    save_images=True,
)

cube, cube_path = get_cube()
enable_gravity_dynamic(cube)

log("run_all 1: open hand")
open_hand_targets()
wait_steps(40)

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_open",
    action={"type": "open_hand"},
    note="hand opened before approach",
    save_images=True,
)

approach_target_pos = [
    initial_hand_pos[0] + APPROACH_DX,
    initial_hand_pos[1] + APPROACH_DY,
    initial_hand_pos[2] + APPROACH_DZ,
]

log(f"run_all 2: approach dx={APPROACH_DX}, dy={APPROACH_DY}, dz={APPROACH_DZ}")
move_hand_to(approach_target_pos, steps=APPROACH_STEPS, wait_per_step=2)

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_approach",
    action={
        "type": "hand_pose_target",
        "target_pos": approach_target_pos,
        "hand_delta": [APPROACH_DX, APPROACH_DY, APPROACH_DZ],
        "approach_steps": APPROACH_STEPS,
    },
    note="after approach movement",
    save_images=True,
)
log_pose("scripu_run_all", "after approach")


SAFE_PRESHAPE_TARGETS = {
    "FFJ3": 8, "FFJ2": 12, "FFJ1": 8,
    "MFJ3": 10, "MFJ2": 16, "MFJ1": 12,
    "RFJ3": 8, "RFJ2": 12, "RFJ1": 8,
    "LFJ4": 4, "LFJ3": 8, "LFJ2": 12, "LFJ1": 8,
    "THJ4": 18, "THJ3": 20, "THJ2": 18, "THJ1": 14,
}

SAFE_THUMB_MIDDLE_CONTACT = {
    "MFJ3": 22, "MFJ2": 30, "MFJ1": 24,
    "THJ4": 30, "THJ3": 34, "THJ2": 32, "THJ1": 24,
}

SAFE_SUPPORT_FINGER_TARGETS = {
    "FFJ3": 10, "FFJ2": 14, "FFJ1": 10,
    "RFJ3": 10, "RFJ2": 14, "RFJ1": 10,
    "LFJ4": 5, "LFJ3": 10, "LFJ2": 14, "LFJ1": 10,
}

SAFE_FINAL_LIGHT_CONTACT = {
    "FFJ3": 12, "FFJ2": 16, "FFJ1": 12,
    "MFJ3": 26, "MFJ2": 34, "MFJ1": 26,
    "RFJ3": 12, "RFJ2": 16, "RFJ1": 12,
    "LFJ4": 6, "LFJ3": 12, "LFJ2": 16, "LFJ1": 12,
    "THJ4": 34, "THJ3": 38, "THJ2": 36, "THJ1": 28,
}

SAFE_HOLD_TARGETS = {
    "FFJ3": 12, "FFJ2": 16, "FFJ1": 12,
    "MFJ3": 26, "MFJ2": 34, "MFJ1": 26,
    "RFJ3": 12, "RFJ2": 16, "RFJ1": 12,
    "LFJ4": 6, "LFJ3": 12, "LFJ2": 16, "LFJ1": 12,
    "THJ4": 34, "THJ3": 38, "THJ2": 36, "THJ1": 28,
}

SAFE_FINAL_HOLD_TARGETS = {
    "FFJ3": 14, "FFJ2": 18, "FFJ1": 14,
    "MFJ3": 30, "MFJ2": 38, "MFJ1": 30,
    "RFJ3": 14, "RFJ2": 18, "RFJ1": 14,
    "LFJ4": 7, "LFJ3": 14, "LFJ2": 18, "LFJ1": 14,
    "THJ4": 38, "THJ3": 42, "THJ2": 40, "THJ1": 32,
}

log("run_all 3: weak preshape")
set_joint_targets(
    SAFE_PRESHAPE_TARGETS,
    stiffness=180.0,
    damping=70.0,
    max_force=900.0,
)
wait_steps(70)

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_preshape",
    action={
        "type": "joint_targets",
        "joint_targets": SAFE_PRESHAPE_TARGETS,
        "stiffness": 180.0,
        "damping": 70.0,
        "max_force": 900.0,
    },
    note="after weak preshape",
    save_images=True,
)

log("run_all 4: weak thumb + middle contact")
set_joint_targets(
    SAFE_THUMB_MIDDLE_CONTACT,
    stiffness=220.0,
    damping=90.0,
    max_force=1200.0,
)
wait_steps(90)

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_thumb_middle_contact",
    action={
        "type": "joint_targets",
        "joint_targets": SAFE_THUMB_MIDDLE_CONTACT,
        "stiffness": 220.0,
        "damping": 90.0,
        "max_force": 1200.0,
    },
    note="after thumb and middle finger light contact",
    save_images=True,
)

log("run_all 5: support fingers")
set_joint_targets(
    SAFE_SUPPORT_FINGER_TARGETS,
    stiffness=180.0,
    damping=90.0,
    max_force=900.0,
)
wait_steps(70)

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_support_contact",
    action={
        "type": "joint_targets",
        "joint_targets": SAFE_SUPPORT_FINGER_TARGETS,
        "stiffness": 180.0,
        "damping": 90.0,
        "max_force": 900.0,
    },
    note="after support fingers touch lightly",
    save_images=True,
)

log("run_all 6: final light contact")
set_joint_targets(
    SAFE_FINAL_LIGHT_CONTACT,
    stiffness=230.0,
    damping=110.0,
    max_force=1300.0,
)
wait_steps(90)

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_final_light_contact",
    action={
        "type": "joint_targets",
        "joint_targets": SAFE_FINAL_LIGHT_CONTACT,
        "stiffness": 230.0,
        "damping": 110.0,
        "max_force": 1300.0,
    },
    note="after final light contact",
    save_images=True,
)

log("run_all 7: wrist lock")
lock_wrist_targets(stiffness=12000.0, damping=700.0, max_force=250000.0)
wait_steps(30)

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_wrist_lock",
    action={
        "type": "wrist_lock",
        "stiffness": 12000.0,
        "damping": 700.0,
        "max_force": 250000.0,
    },
    note="after wrist drive lock",
    save_images=True,
)

try:
    apply_high_friction_to_cube(static_friction=CUBE_STATIC_FRICTION, dynamic_friction=CUBE_DYNAMIC_FRICTION)
    apply_high_friction_to_hand_links(static_friction=FINGER_STATIC_FRICTION, dynamic_friction=FINGER_DYNAMIC_FRICTION)
except Exception as e:
    log(f"friction refresh skipped in run_all: {e}")

log("run_all 8: hold close")
set_joint_targets(
    SAFE_HOLD_TARGETS,
    stiffness=260.0,
    damping=150.0,
    max_force=1600.0,
)
wait_steps(60)

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_hold_close",
    action={
        "type": "joint_targets",
        "joint_targets": SAFE_HOLD_TARGETS,
        "stiffness": 260.0,
        "damping": 150.0,
        "max_force": 1600.0,
    },
    note="after first hold close",
    save_images=True,
)

log("run_all 9: final hold")
set_joint_targets(
    SAFE_FINAL_HOLD_TARGETS,
    stiffness=300.0,
    damping=170.0,
    max_force=1900.0,
)
wait_steps(70)

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_final_hold",
    action={
        "type": "joint_targets",
        "joint_targets": SAFE_FINAL_HOLD_TARGETS,
        "stiffness": 300.0,
        "damping": 170.0,
        "max_force": 1900.0,
    },
    note="after final hold",
    save_images=True,
)

save_lift_start()

log("run_all 10: scoop lift")
hand, hand_path = get_hand()
cube, cube_path = get_cube()
start_cube_z = get_translate(cube)[2]

for i in range(LIFT_STEPS):
    lock_wrist_targets(stiffness=12000.0, damping=700.0, max_force=250000.0)

    before = get_translate(hand)
    pos = list(before)
    pos[0] += LIFT_STEP_DX
    pos[1] += LIFT_STEP_DY
    pos[2] += LIFT_STEP_DZ
    set_translate(hand, pos)

    wait_steps(25)

    record_teacher_step(
        script_name="scripu_run_all",
        phase=f"lift_step_{i + 1}",
        action={
            "type": "hand_delta",
            "hand_delta": [LIFT_STEP_DX, LIFT_STEP_DY, LIFT_STEP_DZ],
            "target_pos": pos,
            "step_index": i + 1,
            "total_steps": LIFT_STEPS,
        },
        note="after one small scoop-lift step",
        save_images=True,
    )

    log(f"run_all scoop lift step {i + 1}/{LIFT_STEPS}")

hand, hand_path = get_hand()
cube, cube_path = get_cube()
final_cube_z = get_translate(cube)[2]
cube_lift_m = final_cube_z - start_cube_z
lift_success = cube_lift_m > 0.004

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_lift",
    action={
        "type": "lift_done",
        "cube_lift_m": cube_lift_m,
        "success_threshold_m": 0.004,
    },
    note="after lift sequence",
    save_images=True,
    success=lift_success,
)

log("run_all 11: return hand")
return_target_pos = data["hand_translate"]
move_hand_to(return_target_pos, steps=35, wait_per_step=2)

record_teacher_step(
    script_name="scripu_run_all",
    phase="after_return",
    action={
        "type": "return_done",
        "target_pos": return_target_pos,
    },
    note="after hand returned to initial position",
    save_images=True,
)

hand, hand_path = get_hand()
cube, cube_path = get_cube()

log_json("after scripu_run_all", {
    "hand_translate": get_translate(hand),
    "cube_translate": get_translate(cube),
    "cube_lift_m": cube_lift_m,
    "lift_success": lift_success,
})
