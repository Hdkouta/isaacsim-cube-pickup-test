import json

# Position-only tuning script. Edit these three values and run this after scripu2 + Play.
# Positive/negative directions depend on the scene camera, so change only 1-2 mm at a time.
TUNE_DX = 0.0
TUNE_DY = 0.0
TUNE_DZ = 0.0
TUNE_STEPS = 12

data = json.loads(INITIAL_FILE.read_text(encoding="utf-8"))
initial_hand_pos = data["hand_translate"]

target_pos = [
    initial_hand_pos[0] + APPROACH_DX + TUNE_DX,
    initial_hand_pos[1] + APPROACH_DY + TUNE_DY,
    initial_hand_pos[2] + APPROACH_DZ + TUNE_DZ,
]

hand, hand_path = get_hand()
start = get_translate(hand)

record_teacher_step(
    script_name="scripu4a_tune",
    phase="before_position_tune",
    action={
        "type": "hand_pose_target",
        "base_delta": [APPROACH_DX, APPROACH_DY, APPROACH_DZ],
        "tune_delta": [TUNE_DX, TUNE_DY, TUNE_DZ],
        "target_pos": target_pos,
    },
    note="before approach position tuning",
    save_images=True,
)

log(f"scripu4a_tune: move hand to tuned approach pose dx={APPROACH_DX + TUNE_DX}, dy={APPROACH_DY + TUNE_DY}, dz={APPROACH_DZ + TUNE_DZ}")

for i in range(TUNE_STEPS):
    alpha = float(i + 1) / float(TUNE_STEPS)
    pos = [
        start[0] + (target_pos[0] - start[0]) * alpha,
        start[1] + (target_pos[1] - start[1]) * alpha,
        start[2] + (target_pos[2] - start[2]) * alpha,
    ]
    set_translate(hand, pos)
    wait_steps(2)

hand, hand_path = get_hand()
cube, cube_path = get_cube()

record_teacher_step(
    script_name="scripu4a_tune",
    phase="after_position_tune",
    action={
        "type": "hand_pose_target",
        "base_delta": [APPROACH_DX, APPROACH_DY, APPROACH_DZ],
        "tune_delta": [TUNE_DX, TUNE_DY, TUNE_DZ],
        "target_pos": target_pos,
    },
    note="after approach position tuning",
    save_images=True,
)

log_json("after scripu4a_tune", {
    "hand_translate": get_translate(hand),
    "cube_translate": get_translate(cube),
    "base_delta": [APPROACH_DX, APPROACH_DY, APPROACH_DZ],
    "tune_delta": [TUNE_DX, TUNE_DY, TUNE_DZ],
})
