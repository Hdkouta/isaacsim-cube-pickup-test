SAFE_HOLD_TARGETS = {
    "FFJ3": 14, "FFJ2": 18, "FFJ1": 14,
    "MFJ3": 30, "MFJ2": 38, "MFJ1": 30,
    "RFJ3": 14, "RFJ2": 18, "RFJ1": 14,
    "LFJ4": 7, "LFJ3": 14, "LFJ2": 18, "LFJ1": 14,
    "THJ4": 40, "THJ3": 44, "THJ2": 42, "THJ1": 32,
}

SAFE_FINAL_HOLD_TARGETS = {
    "FFJ3": 16, "FFJ2": 20, "FFJ1": 16,
    "MFJ3": 34, "MFJ2": 42, "MFJ1": 34,
    "RFJ3": 16, "RFJ2": 20, "RFJ1": 16,
    "LFJ4": 8, "LFJ3": 16, "LFJ2": 20, "LFJ1": 16,
    "THJ4": 44, "THJ3": 48, "THJ2": 46, "THJ1": 36,
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
    stiffness=320.0,
    damping=130.0,
    max_force=2200.0,
)
wait_steps(60)

record_teacher_step(
    script_name="scripu5a",
    phase="after_hold_close",
    action={
        "type": "joint_targets",
        "joint_targets": SAFE_HOLD_TARGETS,
        "stiffness": 320.0,
        "damping": 130.0,
        "max_force": 2200.0,
    },
    note="after first hold close",
    save_images=True,
)

log("scripu5a: final hold")
set_joint_targets(
    SAFE_FINAL_HOLD_TARGETS,
    stiffness=360.0,
    damping=150.0,
    max_force=2600.0,
)
wait_steps(70)

record_teacher_step(
    script_name="scripu5a",
    phase="after_final_hold",
    action={
        "type": "joint_targets",
        "joint_targets": SAFE_FINAL_HOLD_TARGETS,
        "stiffness": 360.0,
        "damping": 150.0,
        "max_force": 2600.0,
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

