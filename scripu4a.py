import json

record_teacher_step(
    script_name="scripu4a",
    phase="before_approach",
    action={"type": "start_approach"},
    note="before moving hand toward cube",
    save_images=True,
)

data = json.loads(INITIAL_FILE.read_text(encoding="utf-8"))
initial_hand_pos = data["hand_translate"]

target_pos = [
    initial_hand_pos[0] + APPROACH_DX,
    initial_hand_pos[1] + APPROACH_DY,
    initial_hand_pos[2] + APPROACH_DZ,
]

hand, hand_path = get_hand()
start = get_translate(hand)

cube, cube_path = get_cube()
enable_gravity_dynamic(cube)

log("scripu4a safe v2: open hand")
open_hand_targets()
wait_steps(40)

record_teacher_step(
    script_name="scripu4a",
    phase="after_open",
    action={"type": "open_hand"},
    note="hand opened before approach",
    save_images=True,
)

log(f"scripu4a safe v3: move hand by dx={APPROACH_DX}, dy={APPROACH_DY}, dz={APPROACH_DZ}")

for i in range(24):
    alpha = float(i + 1) / 24.0
    pos = [
        start[0] + (target_pos[0] - start[0]) * alpha,
        start[1] + (target_pos[1] - start[1]) * alpha,
        start[2] + (target_pos[2] - start[2]) * alpha,
    ]
    set_translate(hand, pos)
    wait_steps(2)

    if i in [7, 15, 23]:
        record_teacher_step(
            script_name="scripu4a",
            phase=f"approach_move_{i + 1}",
            action={
                "type": "hand_pose_target",
                "target_pos": target_pos,
                "hand_delta": [APPROACH_DX, APPROACH_DY, APPROACH_DZ],
                "alpha": alpha,
            },
            note="during approach movement",
            save_images=True,
        )

hand, hand_path = get_hand()
cube, cube_path = get_cube()

record_teacher_step(
    script_name="scripu4a",
    phase="after_approach",
    action={
        "type": "hand_pose_target",
        "target_pos": target_pos,
        "hand_delta": [APPROACH_DX, APPROACH_DY, APPROACH_DZ],
    },
    note="after hand moved to approach pose",
    save_images=True,
)

log_json("after scripu4a safe v3", {
    "hand_translate": get_translate(hand),
    "cube_translate": get_translate(cube),
})
