import json

data = json.loads(INITIAL_FILE.read_text(encoding="utf-8"))
target_pos = data["hand_translate"]

hand, hand_path = get_hand()
start = get_translate(hand)

record_teacher_step(
    script_name="scripu5c",
    phase="before_return",
    action={
        "type": "before_return",
        "target_pos": target_pos,
    },
    note="before returning hand to initial position",
    save_images=True,
)

log("scripu5c: return hand to saved initial position")

for i in range(35):
    alpha = float(i + 1) / 35.0
    pos = [
        start[0] + (target_pos[0] - start[0]) * alpha,
        start[1] + (target_pos[1] - start[1]) * alpha,
        start[2] + (target_pos[2] - start[2]) * alpha,
    ]
    set_translate(hand, pos)
    wait_steps(2)

    if i in [16, 34]:
        record_teacher_step(
            script_name="scripu5c",
            phase=f"return_step_{i + 1}",
            action={
                "type": "hand_pose_target",
                "target_pos": target_pos,
                "alpha": alpha,
            },
            note="during return movement",
            save_images=True,
        )

hand, hand_path = get_hand()
cube, cube_path = get_cube()

record_teacher_step(
    script_name="scripu5c",
    phase="after_return",
    action={
        "type": "return_done",
        "target_pos": target_pos,
    },
    note="after hand returned to initial position",
    save_images=True,
)

log_json("after scripu5c return", {
    "hand_translate": get_translate(hand),
    "cube_translate": get_translate(cube),
})
