record_teacher_step(
    script_name="scripu5b",
    phase="before_lift",
    action={"type": "before_lift"},
    note="before lift",
    save_images=True,
)

log("scripu5b: lift 3mm each step")

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
        script_name="scripu5b",
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

    log(f"scripu5b scoop lift step {i + 1}/{LIFT_STEPS}")

hand, hand_path = get_hand()
cube, cube_path = get_cube()
final_cube_z = get_translate(cube)[2]
cube_lift_m = final_cube_z - start_cube_z
lift_success = cube_lift_m > 0.004

record_teacher_step(
    script_name="scripu5b",
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

log_json("after scripu5b lift", {
    "hand_translate": get_translate(hand),
    "cube_translate": get_translate(cube),
    "cube_lift_m": cube_lift_m,
    "lift_success": lift_success,
})
