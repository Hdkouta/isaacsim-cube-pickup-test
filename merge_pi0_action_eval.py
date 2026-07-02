import argparse
import csv
import json
import math
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_INPUT_ROOT = Path(r"C:\VScode\Yoshida_script\pi0_action_eval")
DEFAULT_OUTPUT_ROOT = Path(r"C:\VScode\Yoshida_script\pi0_action_eval_merged")

ACTION_SCHEMA_NAME = "shadowhand_joint17_handdelta3_v1"
ACTION_JOINTS = [
    "FFJ3", "FFJ2", "FFJ1",
    "MFJ3", "MFJ2", "MFJ1",
    "RFJ3", "RFJ2", "RFJ1",
    "LFJ4", "LFJ3", "LFJ2", "LFJ1",
    "THJ4", "THJ3", "THJ2", "THJ1",
]
HAND_DELTA_NAMES = ["hand_dx", "hand_dy", "hand_dz"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Merge pi0/ShadowHand eval_steps.jsonl logs into comparison files."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help=r"pi0 action eval root. Default: C:\VScode\Yoshida_script\pi0_action_eval",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=r"Output root. Default: C:\VScode\Yoshida_script\pi0_action_eval_merged",
    )
    parser.add_argument(
        "--copy-images",
        action="store_true",
        help="Copy referenced before/after JPG images into the merged output folder.",
    )
    parser.add_argument(
        "--stable-cube-xy-threshold",
        type=float,
        default=0.001,
        help="XY cube motion threshold for stable/large_push label. Default: 0.001 m.",
    )
    parser.add_argument(
        "--preview-count",
        type=int,
        default=40,
        help="Number of readable rows to write into preview.txt.",
    )
    return parser.parse_args()


def iter_eval_jsonl(input_root):
    for path in sorted(input_root.rglob("eval_steps.jsonl")):
        if "pi0_action_eval_merged" not in path.parts:
            yield path


def load_items(jsonl_path):
    items = []
    with jsonl_path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue

            try:
                item = json.loads(text)
            except json.JSONDecodeError as e:
                items.append({
                    "_load_error": f"json decode error: {e}",
                    "_source_jsonl": str(jsonl_path),
                    "_source_line": line_no,
                })
                continue

            item["_source_jsonl"] = str(jsonl_path)
            item["_source_line"] = line_no
            items.append(item)

    return items


def sanitize_filename(text):
    safe = []
    for ch in str(text):
        if ch.isalnum() or ch in ("_", "-", "."):
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe).strip("_") or "unnamed"


def as_float(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(number):
        return float(default)
    return number


def xyz(values):
    if not isinstance(values, list) or len(values) < 3:
        return [0.0, 0.0, 0.0]
    return [as_float(values[0]), as_float(values[1]), as_float(values[2])]


def image_count(item):
    images = item.get("images") or {}
    if not isinstance(images, dict):
        return 0
    return sum(
        1
        for info in images.values()
        if isinstance(info, dict) and info.get("jpg_path") and not info.get("skipped")
    )


def group_by_run(items):
    runs = defaultdict(list)
    for item in items:
        run_id = str(item.get("run_id") or "unknown_run")
        runs[run_id].append(item)

    for run_items in runs.values():
        run_items.sort(key=lambda item: (
            as_float(item.get("timestamp")),
            int(item.get("_source_line") or 0),
            str(item.get("step_id") or ""),
        ))

    return dict(sorted(runs.items()))


def infer_behavior_label(action):
    joint_targets = action.get("joint_targets") or {}
    hand_delta = xyz(action.get("hand_delta"))
    nonzero_hand_delta = any(abs(value) > 1e-12 for value in hand_delta)

    if all(abs(as_float(joint_targets.get(joint, 0.0))) < 1e-12 for joint in ACTION_JOINTS):
        return "approach_only" if nonzero_hand_delta else "open_or_noop"

    ffj3 = as_float(joint_targets.get("FFJ3"))
    mfj3 = as_float(joint_targets.get("MFJ3"))
    thj4 = as_float(joint_targets.get("THJ4"))
    thj1 = as_float(joint_targets.get("THJ1"))

    if ffj3 == 8 and mfj3 == 10 and thj4 == 18:
        return "approach_preshape"
    if ffj3 == 8 and mfj3 == 22 and thj4 == 30:
        return "thumb_middle_contact"
    if ffj3 == 12 and mfj3 == 26 and thj4 == 34:
        return "final_light_contact"
    if ffj3 == 14 and mfj3 == 30 and thj4 == 38 and thj1 == 32:
        return "final_hold"

    return "custom_action"


def vector_from_action(action):
    vector = action.get("vector")
    if isinstance(vector, list) and len(vector) == len(ACTION_JOINTS) + len(HAND_DELTA_NAMES):
        return [as_float(value) for value in vector]

    joint_targets = action.get("joint_targets") or {}
    hand_delta = xyz(action.get("hand_delta"))
    return [as_float(joint_targets.get(joint, 0.0)) for joint in ACTION_JOINTS] + hand_delta


def motion_metrics(cube_motion, stable_cube_xy_threshold):
    motion = xyz(cube_motion)
    xy = math.sqrt(motion[0] * motion[0] + motion[1] * motion[1])
    xyz_norm = math.sqrt(motion[0] * motion[0] + motion[1] * motion[1] + motion[2] * motion[2])
    label = "stable" if xy <= stable_cube_xy_threshold else "large_push"
    return {
        "cube_motion": motion,
        "cube_xy_motion_m": xy,
        "cube_xyz_motion_m": xyz_norm,
        "cube_motion_label": label,
        "stable_cube_xy_threshold_m": stable_cube_xy_threshold,
    }


def make_eval_sample(after_item, before_item, env_item, stable_cube_xy_threshold):
    action = after_item.get("action") or {}
    if not isinstance(action, dict):
        action = {}

    run_id = str(after_item.get("run_id") or "unknown_run")
    vector = vector_from_action(action)
    metrics = motion_metrics(action.get("cube_motion"), stable_cube_xy_threshold)
    behavior_label = infer_behavior_label(action)

    observation_item = before_item or env_item or {}
    env_state = env_item.get("state") if isinstance(env_item, dict) else {}

    return {
        "sample_id": f"{sanitize_filename(run_id)}_{sanitize_filename(after_item.get('step_id', 'after_action'))}",
        "schema_name": action.get("schema_name") or ACTION_SCHEMA_NAME,
        "run_id": run_id,
        "behavior_label": behavior_label,
        "instruction": after_item.get("instruction"),
        "env_ready": {
            "step_id": env_item.get("step_id") if isinstance(env_item, dict) else None,
            "state": env_state or {},
            "image_count": image_count(env_item) if isinstance(env_item, dict) else 0,
        },
        "before_action": {
            "step_id": observation_item.get("step_id"),
            "state": observation_item.get("state") or {},
            "images": observation_item.get("images") or {},
            "image_count": image_count(observation_item),
        },
        "after_action": {
            "step_id": after_item.get("step_id"),
            "state": after_item.get("state") or {},
            "images": after_item.get("images") or {},
            "image_count": image_count(after_item),
        },
        "action": {
            "schema_name": action.get("schema_name") or ACTION_SCHEMA_NAME,
            "vector": vector,
            "joint_targets": action.get("joint_targets") or {},
            "hand_delta": xyz(action.get("hand_delta")),
            "joint_count": action.get("joint_count"),
            "target_hand_pos": action.get("target_hand_pos"),
        },
        "metrics": metrics,
        "source": {
            "jsonl": after_item.get("_source_jsonl"),
            "line": after_item.get("_source_line"),
            "run_dir": str(Path(after_item.get("_source_jsonl", "")).parent),
        },
    }


def build_samples(items, stable_cube_xy_threshold):
    samples = []
    skipped = []

    for run_id, run_items in group_by_run(items).items():
        latest_env_ready = None
        latest_before_action = None

        for item in run_items:
            if item.get("_load_error"):
                skipped.append(skip_row(item, "load_error"))
                continue

            phase = item.get("phase")
            if phase == "env_ready":
                latest_env_ready = item
                skipped.append(skip_row(item, "env_ready_not_action_result"))
            elif phase == "before_action":
                latest_before_action = item
                skipped.append(skip_row(item, "before_action_not_result"))
            elif phase == "after_action":
                samples.append(make_eval_sample(
                    item,
                    latest_before_action,
                    latest_env_ready,
                    stable_cube_xy_threshold,
                ))
            else:
                skipped.append(skip_row(item, f"non_eval_result_phase_{phase}"))

    return samples, skipped


def skip_row(item, reason):
    return {
        "run_id": item.get("run_id"),
        "step_id": item.get("step_id"),
        "timestamp": item.get("timestamp"),
        "phase": item.get("phase"),
        "reason": reason,
        "source_jsonl": item.get("_source_jsonl"),
        "source_line": item.get("_source_line"),
    }


def copy_images_for_sample(sample, images_out_dir, copy_cache):
    run_id = sanitize_filename(sample["run_id"])

    for phase_key in ("before_action", "after_action"):
        images = sample[phase_key].get("images") or {}
        if not isinstance(images, dict):
            continue

        for camera_path, info in images.items():
            if not isinstance(info, dict) or info.get("skipped"):
                continue

            src = info.get("jpg_path")
            if not src:
                continue

            src_path = Path(src)
            if not src_path.exists():
                info["copy_error"] = f"source image not found: {src_path}"
                continue

            cache_key = str(src_path)
            if cache_key in copy_cache:
                info["copied_jpg_path"] = copy_cache[cache_key]
                continue

            dst_dir = images_out_dir / run_id / phase_key
            dst_dir.mkdir(parents=True, exist_ok=True)
            camera_name = sanitize_filename(info.get("name") or camera_path)
            step_id = sanitize_filename(sample[phase_key].get("step_id") or phase_key)
            dst_path = dst_dir / f"{step_id}_{camera_name}.jpg"
            shutil.copy2(src_path, dst_path)
            copy_cache[cache_key] = str(dst_path)
            info["copied_jpg_path"] = str(dst_path)


def write_jsonl(path, items):
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def write_csv(path, rows, fallback_fieldnames):
    fieldnames = list(rows[0].keys()) if rows else fallback_fieldnames
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def index_row(sample):
    action = sample["action"]
    metrics = sample["metrics"]
    hand_delta = action["hand_delta"]
    cube_motion = metrics["cube_motion"]

    return {
        "sample_id": sample["sample_id"],
        "run_id": sample["run_id"],
        "behavior_label": sample["behavior_label"],
        "before_step_id": sample["before_action"]["step_id"],
        "after_step_id": sample["after_action"]["step_id"],
        "hand_dx": hand_delta[0],
        "hand_dy": hand_delta[1],
        "hand_dz": hand_delta[2],
        "cube_motion_x": cube_motion[0],
        "cube_motion_y": cube_motion[1],
        "cube_motion_z": cube_motion[2],
        "cube_xy_motion_m": metrics["cube_xy_motion_m"],
        "cube_xyz_motion_m": metrics["cube_xyz_motion_m"],
        "cube_motion_label": metrics["cube_motion_label"],
        "joint_count": action.get("joint_count"),
        "before_image_count": sample["before_action"]["image_count"],
        "after_image_count": sample["after_action"]["image_count"],
        "run_dir": sample["source"]["run_dir"],
        "source_jsonl": sample["source"]["jsonl"],
        "source_line": sample["source"]["line"],
    }


def action_debug_row(sample):
    row = index_row(sample)
    vector = sample["action"]["vector"]
    for index, name in enumerate(ACTION_JOINTS + HAND_DELTA_NAMES):
        row[f"action_{index:02d}_{name}"] = vector[index]
    return row


def index_fieldnames():
    return [
        "sample_id", "run_id", "behavior_label", "before_step_id", "after_step_id",
        "hand_dx", "hand_dy", "hand_dz",
        "cube_motion_x", "cube_motion_y", "cube_motion_z",
        "cube_xy_motion_m", "cube_xyz_motion_m", "cube_motion_label",
        "joint_count", "before_image_count", "after_image_count",
        "run_dir", "source_jsonl", "source_line",
    ]


def action_debug_fieldnames():
    return index_fieldnames() + [
        f"action_{index:02d}_{name}"
        for index, name in enumerate(ACTION_JOINTS + HAND_DELTA_NAMES)
    ]


def build_summary(samples, skipped, source_files, output_files, config):
    behavior_counter = Counter()
    motion_counter = Counter()
    skipped_counter = Counter()
    run_counter = Counter()

    for sample in samples:
        behavior_counter[sample["behavior_label"]] += 1
        motion_counter[sample["metrics"]["cube_motion_label"]] += 1
        run_counter[sample["run_id"]] += 1

    for row in skipped:
        skipped_counter[row["reason"]] += 1

    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "schema_name": ACTION_SCHEMA_NAME,
        "total_eval_samples": len(samples),
        "total_source_files": len(source_files),
        "total_skipped_steps": len(skipped),
        "source_files": [str(path) for path in source_files],
        "output_files": output_files,
        "config": config,
        "samples_by_run": dict(run_counter),
        "samples_by_behavior_label": dict(behavior_counter),
        "samples_by_cube_motion_label": dict(motion_counter),
        "skipped_by_reason": dict(skipped_counter),
    }


def preview_line(sample):
    metrics = sample["metrics"]
    motion = metrics["cube_motion"]
    hand_delta = sample["action"]["hand_delta"]
    return (
        f"{sample['run_id']} {sample['behavior_label']}: "
        f"hand_delta={hand_delta}, "
        f"cube_motion=[{motion[0]:.6f}, {motion[1]:.6f}, {motion[2]:.6f}], "
        f"xy={metrics['cube_xy_motion_m']:.6f}m, "
        f"label={metrics['cube_motion_label']}, "
        f"run_dir={sample['source']['run_dir']}"
    )


def main():
    args = parse_args()
    input_root = args.input_root
    output_root = args.output_root

    if not input_root.exists():
        raise FileNotFoundError(f"input root not found: {input_root}")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_jsonl = output_dir / "pi0_eval_dataset.jsonl"
    dataset_json = output_dir / "pi0_eval_dataset.json"
    index_csv = output_dir / "pi0_eval_index.csv"
    action_debug_csv = output_dir / "pi0_eval_action_debug.csv"
    skipped_csv = output_dir / "skipped_steps.csv"
    summary_json = output_dir / "summary.json"
    preview_txt = output_dir / "preview.txt"
    images_out_dir = output_dir / "images"

    source_files = list(iter_eval_jsonl(input_root))
    items = []
    for source_file in source_files:
        items.extend(load_items(source_file))

    samples, skipped = build_samples(items, args.stable_cube_xy_threshold)

    if args.copy_images:
        images_out_dir.mkdir(parents=True, exist_ok=True)
        copy_cache = {}
        for sample in samples:
            copy_images_for_sample(sample, images_out_dir, copy_cache)

    write_jsonl(dataset_jsonl, samples)
    dataset_json.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")

    write_csv(index_csv, [index_row(sample) for sample in samples], index_fieldnames())
    write_csv(action_debug_csv, [action_debug_row(sample) for sample in samples], action_debug_fieldnames())
    write_csv(
        skipped_csv,
        skipped,
        ["run_id", "step_id", "timestamp", "phase", "reason", "source_jsonl", "source_line"],
    )

    preview_lines = [preview_line(sample) for sample in samples[: args.preview_count]]
    preview_txt.write_text("\n".join(preview_lines) + ("\n" if preview_lines else ""), encoding="utf-8")

    output_files = {
        "dataset_jsonl": str(dataset_jsonl),
        "dataset_json": str(dataset_json),
        "index_csv": str(index_csv),
        "action_debug_csv": str(action_debug_csv),
        "skipped_csv": str(skipped_csv),
        "summary_json": str(summary_json),
        "preview_txt": str(preview_txt),
    }
    if args.copy_images:
        output_files["copied_images_dir"] = str(images_out_dir)

    config = {
        "stable_cube_xy_threshold": args.stable_cube_xy_threshold,
        "copy_images": args.copy_images,
    }
    summary = build_summary(samples, skipped, source_files, output_files, config)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("pi0 action eval logs merged")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
