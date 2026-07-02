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

record_teacher_step(
    script_name="scripu5a",
    phase="before_hold",
    action={"type": "before_hold"},
    note="before hold close",
    save_images=True,
)

log("scripu5a: wrist drive lock only")
lock_wrist_targets(stiffness=12000.0, damping=700.0, max_force=250000.0)
wait_steps(30)

try:
    apply_high_friction_to_cube(static_friction=CUBE_STATIC_FRICTION, dynamic_friction=CUBE_DYNAMIC_FRICTION)
    apply_high_friction_to_hand_links(static_friction=FINGER_STATIC_FRICTION, dynamic_friction=FINGER_DYNAMIC_FRICTION)
except Exception as e:
    log(f"friction refresh skipped in scripu5a: {e}")

record_teacher_step(
    script_name="scripu5a",
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

log("scripu5a: hold close")
set_joint_targets(
    SAFE_HOLD_TARGETS,
    stiffness=260.0,
    damping=150.0,
    max_force=1600.0,
)
wait_steps(60)

record_teacher_step(
    script_name="scripu5a",
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

log("scripu5a: final hold")
set_joint_targets(
    SAFE_FINAL_HOLD_TARGETS,
    stiffness=300.0,
    damping=170.0,
    max_force=1900.0,
)
wait_steps(70)

record_teacher_step(
    script_name="scripu5a",
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

hand, hand_path = get_hand()
cube, cube_path = get_cube()

log_json("after scripu5a hold", {
    "hand_translate": get_translate(hand),
    "cube_translate": get_translate(cube),
})