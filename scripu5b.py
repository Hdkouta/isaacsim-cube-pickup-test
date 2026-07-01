record_teacher_step(
    script_name="scripu5b",
    phase="before_lift",
    action={"type": "before_lift"},
    note="before lift",
    save_images=True,
)

log("scripu5b: lift 3mm each step")

hand, hand_path = get_hand()

for i in range(6):
    lock_wrist_targets(stiffness=12000.0, damping=700.0, max_force=250000.0)

    before = get_translate(hand)
    pos = list(before)
    pos[2] += 0.003
    set_translate(hand, pos)

    wait_steps(25)

    record_teacher_step(
        script_name="scripu5b",
        phase=f"lift_step_{i + 1}",
        action={
            "type": "hand_delta",
            "hand_delta": [0.0, 0.0, 0.003],
            "target_pos": pos,
            "step_index": i + 1,
            "total_steps": 6,
        },
        note="after one small lift step",
        save_images=True,
    )

    log(f"scripu5b lift step {i + 1}/6")

hand, hand_path = get_hand()
cube, cube_path = get_cube()

record_teacher_step(
    script_name="scripu5b",
    phase="after_lift",
    action={"type": "lift_done"},
    note="after lift sequence",
    save_images=True,
)

log_json("after scripu5b lift", {
    "hand_translate": get_translate(hand),
    "cube_translate": get_translate(cube),
})

