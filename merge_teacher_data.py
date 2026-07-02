import argparse
import csv
import json
import shutil
import time
from collections import Counter
from pathlib import Path

DEFAULT_INPUT_ROOT = Path(r"C:\VScode\Yoshida_script\teacher_data")
DEFAULT_OUTPUT_ROOT = Path(r"C:\VScode\Yoshida_script\teacher_data_merged")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Merge Isaac Sim teacher-data steps.jsonl files into ML-ready files."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help=r"Teacher data root. Default: C:\VScode\Yoshida_script\teacher_data",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=r"Output root. Default: C:\VScode\Yoshida_script\teacher_data_merged",
    )
    parser.add_argument(
        "--copy-images",
        action="store_true",
        help="Copy referenced JPG images into the merged output folder and add merged_jpg_path.",
    )
    return parser.parse_args()


def iter_steps_jsonl(input_root):
    for path in sorted(input_root.rglob("steps.jsonl")):
        if "teacher_data_merged" not in path.parts:
            yield path


def load_items(jsonl_path):
    items = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue

            try:
                item = json.loads(text)
            except json.JSONDecodeError as e:
                items.append({
                    "_merge_error": f"json decode error: {e}",
                    "_source_jsonl": str(jsonl_path),
                    "_source_line": line_no,
                })
                continue

            item["_source_jsonl"] = str(jsonl_path)
            item["_source_line"] = line_no
            items.append(item)

    return items


def image_entries(item):
    images = item.get("images") or {}
    if not isinstance(images, dict):
        return []
    return list(images.items())


def copy_item_images(item, images_out_dir):
    run_id = item.get("run_id", "unknown_run")
    step_id = item.get("step_id", "unknown_step")

    for camera_path, info in image_entries(item):
        if not isinstance(info, dict) or info.get("skipped"):
            continue

        src = info.get("jpg_path")
        if not src:
            continue

        src_path = Path(src)
        if not src_path.exists():
            info["merge_copy_error"] = f"source image not found: {src_path}"
            continue

        camera_name = info.get("name") or camera_path.replace("/", "_").strip("_")
        safe_camera_name = sanitize_filename(camera_name)
        dst_dir = images_out_dir / sanitize_filename(str(run_id))
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = dst_dir / f"{sanitize_filename(str(step_id))}_{safe_camera_name}.jpg"

        shutil.copy2(src_path, dst_path)
        info["merged_jpg_path"] = str(dst_path)


def sanitize_filename(text):
    safe = []
    for ch in str(text):
        if ch.isalnum() or ch in ("_", "-", "."):
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe).strip("_")


def flatten_xyz(values):
    if not isinstance(values, list) or len(values) < 3:
        return [None, None, None]
    return [values[0], values[1], values[2]]


def csv_row(item):
    state = item.get("state") or {}
    action = item.get("action") or {}

    hand_x, hand_y, hand_z = flatten_xyz(state.get("hand_translate"))
    cube_x, cube_y, cube_z = flatten_xyz(state.get("cube_translate"))
    hand_delta_x, hand_delta_y, hand_delta_z = flatten_xyz(action.get("hand_delta"))

    images = item.get("images") or {}
    image_count = 0
    skipped_count = 0
    if isinstance(images, dict):
        for _, info in images.items():
            if isinstance(info, dict) and info.get("skipped"):
                skipped_count += 1
            elif isinstance(info, dict) and info.get("jpg_path"):
                image_count += 1

    return {
        "run_id": item.get("run_id"),
        "step_id": item.get("step_id"),
        "timestamp": item.get("timestamp"),
        "script_name": item.get("script_name"),
        "phase": item.get("phase"),
        "instruction": item.get("instruction"),
        "action_type": action.get("type"),
        "success": item.get("success"),
        "hand_x": hand_x,
        "hand_y": hand_y,
        "hand_z": hand_z,
        "cube_x": cube_x,
        "cube_y": cube_y,
        "cube_z": cube_z,
        "cube_bottom_above_table": state.get("cube_bottom_above_table"),
        "hand_delta_x": hand_delta_x,
        "hand_delta_y": hand_delta_y,
        "hand_delta_z": hand_delta_z,
        "image_count": image_count,
        "skipped_camera_count": skipped_count,
        "source_jsonl": item.get("_source_jsonl"),
        "source_line": item.get("_source_line"),
    }


def build_summary(items, source_files, output_files):
    phase_counter = Counter()
    script_counter = Counter()
    run_counter = Counter()
    action_counter = Counter()
    image_count = 0
    skipped_camera_count = 0
    merge_error_count = 0

    for item in items:
        if item.get("_merge_error"):
            merge_error_count += 1

        phase_counter[item.get("phase", "unknown")] += 1
        script_counter[item.get("script_name", "unknown")] += 1
        run_counter[item.get("run_id", "unknown")] += 1

        action = item.get("action") or {}
        action_counter[action.get("type", "unknown")] += 1

        images = item.get("images") or {}
        if isinstance(images, dict):
            for _, info in images.items():
                if isinstance(info, dict) and info.get("skipped"):
                    skipped_camera_count += 1
                elif isinstance(info, dict) and info.get("jpg_path"):
                    image_count += 1

    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_steps": len(items),
        "total_runs": len(run_counter),
        "total_source_files": len(source_files),
        "total_images_referenced": image_count,
        "total_skipped_cameras": skipped_camera_count,
        "merge_error_count": merge_error_count,
        "source_files": [str(path) for path in source_files],
        "output_files": output_files,
        "steps_by_run": dict(run_counter),
        "steps_by_script": dict(script_counter),
        "steps_by_phase": dict(phase_counter),
        "steps_by_action_type": dict(action_counter),
    }


def main():
    args = parse_args()
    input_root = args.input_root
    output_root = args.output_root

    if not input_root.exists():
        raise FileNotFoundError(f"input root not found: {input_root}")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_jsonl = output_dir / "dataset.jsonl"
    dataset_json = output_dir / "dataset.json"
    dataset_csv = output_dir / "dataset_index.csv"
    summary_json = output_dir / "summary.json"
    images_out_dir = output_dir / "images"

    source_files = list(iter_steps_jsonl(input_root))
    items = []
    for source_file in source_files:
        items.extend(load_items(source_file))

    items.sort(key=lambda item: (
        str(item.get("run_id", "")),
        float(item.get("timestamp") or 0.0),
        str(item.get("step_id", "")),
    ))

    if args.copy_images:
        images_out_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            copy_item_images(item, images_out_dir)

    with dataset_jsonl.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    dataset_json.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = [csv_row(item) for item in items]
    fieldnames = list(rows[0].keys()) if rows else [
        "run_id", "step_id", "timestamp", "script_name", "phase",
        "instruction", "action_type", "success",
    ]
    with dataset_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    output_files = {
        "dataset_jsonl": str(dataset_jsonl),
        "dataset_json": str(dataset_json),
        "dataset_csv": str(dataset_csv),
        "summary_json": str(summary_json),
    }
    if args.copy_images:
        output_files["copied_images_dir"] = str(images_out_dir)

    summary = build_summary(items, source_files, output_files)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("teacher data merged")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

