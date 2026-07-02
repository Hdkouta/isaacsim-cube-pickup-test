import json

# Fine tune the approach pose here.
# Change these by 0.001-0.002 m when the hand position is slightly off.
TUNE_DX = 0.0
TUNE_DY = 0.0
TUNE_DZ = 0.0

TOTAL_APPROACH_DX = APPROACH_DX + TUNE_DX
TOTAL_APPROACH_DY = APPROACH_DY + TUNE_DY
TOTAL_APPROACH_DZ = APPROACH_DZ + TUNE_DZ

record_teacher_step(
    script_name="scripu4a",
    phase="before_approach",
    action={
        "type": "start_approach",
        "base_delta": [APPROACH_DX, APPROACH_DY, APPROACH_DZ],
        "tune_delta": [TUNE_DX, TUNE_DY, TUNE_DZ],
        "total_delta": [TOTAL_APPROACH_DX, TOTAL_APPROACH_DY, TOTAL_APPROACH_DZ],
    },
    note="before moving hand toward cube with integrated tuning",
    save_images=True,
)

data = json.loads(INITIAL_FILE.read_text(encoding="utf-8"))
initial_hand_pos = data["hand_translate"]

target_pos = [
    initial_hand_pos[0] + TOTAL_APPROACH_DX,
    initial_hand_pos[1] + TOTAL_APPROACH_DY,
    initial_hand_pos[2] + TOTAL_APPROACH_DZ,
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

log(
    "scripu4a safe v5: move hand by "
    f"base=({APPROACH_DX}, {APPROACH_DY}, {APPROACH_DZ}), "
    f"tune=({TUNE_DX}, {TUNE_DY}, {TUNE_DZ}), "
    f"total=({TOTAL_APPROACH_DX}, {TOTAL_APPROACH_DY}, {TOTAL_APPROACH_DZ})"
)

for i in range(APPROACH_STEPS):
    alpha = float(i + 1) / float(APPROACH_STEPS)
    pos = [
        start[0] + (target_pos[0] - start[0]) * alpha,
        start[1] + (target_pos[1] - start[1]) * alpha,
        start[2] + (target_pos[2] - start[2]) * alpha,
    ]
    set_translate(hand, pos)
    wait_steps(2)

    if i in [
        max(0, APPROACH_STEPS // 3 - 1),
        max(0, (APPROACH_STEPS * 2) // 3 - 1),
        APPROACH_STEPS - 1,
    ]:
        record_teacher_step(
            script_name="scripu4a",
            phase=f"approach_move_{i + 1}",
            action={
                "type": "hand_pose_target",
                "target_pos": target_pos,
                "base_delta": [APPROACH_DX, APPROACH_DY, APPROACH_DZ],
                "tune_delta": [TUNE_DX, TUNE_DY, TUNE_DZ],
                "hand_delta": [TOTAL_APPROACH_DX, TOTAL_APPROACH_DY, TOTAL_APPROACH_DZ],
                "alpha": alpha,
                "approach_steps": APPROACH_STEPS,
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
        "base_delta": [APPROACH_DX, APPROACH_DY, APPROACH_DZ],
        "tune_delta": [TUNE_DX, TUNE_DY, TUNE_DZ],
        "hand_delta": [TOTAL_APPROACH_DX, TOTAL_APPROACH_DY, TOTAL_APPROACH_DZ],
        "approach_steps": APPROACH_STEPS,
    },
    note="after hand moved to approach pose",
    save_images=True,
)

log_json("after scripu4a safe v5", {
    "hand_translate": get_translate(hand),
    "cube_translate": get_translate(cube),
    "base_delta": [APPROACH_DX, APPROACH_DY, APPROACH_DZ],
    "tune_delta": [TUNE_DX, TUNE_DY, TUNE_DZ],
    "approach_delta": [TOTAL_APPROACH_DX, TOTAL_APPROACH_DY, TOTAL_APPROACH_DZ],
})