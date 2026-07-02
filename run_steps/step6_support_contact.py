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

record_teacher_step(
    script_name="scripu4c",
    phase="before_support_contact",
    action={"type": "before_support_fingers"},
    note="before adding support fingers",
    save_images=True,
)

log("scripu4c safe: add support fingers very lightly")
set_joint_targets(
    SAFE_SUPPORT_FINGER_TARGETS,
    stiffness=180.0,
    damping=90.0,
    max_force=900.0,
)
wait_steps(70)

record_teacher_step(
    script_name="scripu4c",
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

log("scripu4c safe: final light contact")
set_joint_targets(
    SAFE_FINAL_LIGHT_CONTACT,
    stiffness=230.0,
    damping=110.0,
    max_force=1300.0,
)
wait_steps(90)

record_teacher_step(
    script_name="scripu4c",
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

hand, hand_path = get_hand()
cube, cube_path = get_cube()

log_json("after scripu4c safe final light contact", {
    "hand_translate": get_translate(hand),
    "cube_translate": get_translate(cube),
})

