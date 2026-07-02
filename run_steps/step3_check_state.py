hand, hand_path = get_hand()
cube, cube_path = get_cube()
camera_paths = list_all_camera_paths()

cube_pos = get_translate(cube)
cube_height = CUBE_USD_SIZE * CUBE_SCALE[2]
cube_world_bottom_z = cube_pos[2] - cube_height / 2.0
cube_bottom_above_table = cube_world_bottom_z - TABLE_Z

status = {
    "hand_path": hand_path,
    "cube_path": cube_path,
    "hand_translate": get_translate(hand),
    "cube_translate": cube_pos,
    "cube_scale": CUBE_SCALE,
    "cube_usd_size": CUBE_USD_SIZE,
    "cube_height": cube_height,
    "cube_mass_kg": CUBE_MASS_KG,
    "cube_world_bottom_z": cube_world_bottom_z,
    "table_z": TABLE_Z,
    "cube_bottom_above_table": cube_bottom_above_table,
    "camera_count": len(camera_paths),
    "camera_paths": camera_paths,
    "teacher_run_id": TEACHER_RUN_ID,
    "teacher_jsonl": str(TEACHER_JSONL),
}

record_teacher_step(
    script_name="scripu3",
    phase="status_read_only",
    action={"type": "status"},
    note="read-only status snapshot",
    save_images=True,
)

log_json("status read only", status)
print_all_cameras()
