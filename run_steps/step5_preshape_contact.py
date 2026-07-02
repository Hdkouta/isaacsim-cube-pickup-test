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

record_teacher_step(
    script_name="scripu4b",
    phase="before_preshape",
    action={"type": "before_joint_targets"},
    note="before weak preshape",
    save_images=True,
)

log("scripu4b safe: weak preshape")
set_joint_targets(
    SAFE_PRESHAPE_TARGETS,
    stiffness=180.0,
    damping=70.0,
    max_force=900.0,
)
wait_steps(70)

record_teacher_step(
    script_name="scripu4b",
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

log("scripu4b safe: weak thumb + middle contact")
set_joint_targets(
    SAFE_THUMB_MIDDLE_CONTACT,
    stiffness=220.0,
    damping=90.0,
    max_force=1200.0,
)
wait_steps(90)

record_teacher_step(
    script_name="scripu4b",
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

hand, hand_path = get_hand()
cube, cube_path = get_cube()

log_json("after scripu4b safe", {
    "hand_translate": get_translate(hand),
    "cube_translate": get_translate(cube),
})
