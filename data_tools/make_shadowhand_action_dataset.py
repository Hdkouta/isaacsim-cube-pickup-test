import argparse
import csv
import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_INPUT_ROOT = Path(r"C:\VScode\Yoshida_script\teacher_data")
DEFAULT_OUTPUT_ROOT = Path(r"C:\VScode\Yoshida_script\shadowhand_action_dataset")

SCHEMA_NAME = "shadowhand_joint17_handdelta3_v1"
DEFAULT_TASK_INSTRUCTION = "control the ShadowHand to approach, contact, and hold the cube"
DEFAULT_MAX_STABLE_CUBE_XY_MOTION_M = 0.01
ACTION_JOINTS = [
    "FFJ3", "FFJ2", "FFJ1",
    "MFJ3", "MFJ2", "MFJ1",
    "RFJ3", "RFJ2", "RFJ1",
    "LFJ4", "LFJ3", "LFJ2", "LFJ1",
    "THJ4", "THJ3", "THJ2", "THJ1",
]
HAND_DELTA_NAMES = ["hand_dx", "hand_dy", "hand_dz"]
TRAINABLE_ACTION_TYPES = {"joint_targets", "hand_delta"}


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Convert Isaac Sim teacher_data/steps.jsonl into ShadowHand "
            "image-state -> 20D action fine-tuning samples."
        )
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
        help=r"Output root. Default: C:\VScode\Yoshida_script\shadowhand_action_dataset",
    )
    parser.add_argument(
        "--copy-images",
        action="store_true",
        help="Copy referenced observation JPG images into the output folder.",
    )
    parser.add_argument(
        "--include-no-image",
        action="store_true",
        help="Keep state-only samples when no previous visual observation exists.",
    )
    parser.add_argument(
        "--max-observation-age",
        type=int,
        default=0,
        help=(
            "Maximum number of teacher steps between observation image and action. "
            "0 means unlimited. Default: 0"
        ),
    )
    parser.add_argument(
        "--action-types",
        default="joint_targets,hand_delta",
        help="Comma-separated action types to convert. Default: joint_targets,hand_delta",
    )
    parser.add_argument(
        "--instruction",
        default=DEFAULT_TASK_INSTRUCTION,
        help=(
            "Instruction written into every sample. Default focuses on approach/contact/hold, "
            "not lifting."
        ),
    )
    parser.add_argument(
        "--keep-source-instruction",
        action="store_true",
        help="Use each teacher step's original instruction instead of --instruction.",
    )
    parser.add_argument(
        "--include-lift-steps",
        action="store_true",
        help="Include scripu5b/lift_step hand-delta samples. Default excludes lift attempts.",
    )
    parser.add_argument(
        "--max-stable-cube-xy-motion",
        type=float,
        default=DEFAULT_MAX_STABLE_CUBE_XY_MOTION_M,
        help="XY cube motion threshold used for quality labels. Default: 0.01 m.",
    )
    parser.add_argument(
        "--preview-count",
        type=int,
        default=30,
        help="Number of human-readable examples to write into preview.txt.",
    )
    return parser.parse_args()


def iter_steps_jsonl(input_root):
    for path in sorted(input_root.rglob("steps.jsonl")):
        if "teacher_data_merged" not in path.parts and "shadowhand_action_dataset" not in path.parts:
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


def action_type_of(item):
    action = item.get("action") or {}
    if not isinstance(action, dict):
        return "unknown"
    return str(action.get("type") or "unknown")


def valid_images(item):
    images = item.get("images") or {}
    if not isinstance(images, dict):
        return {}

    out = {}
    for camera_path, info in images.items():
        if not isinstance(info, dict) or info.get("skipped"):
            continue

        jpg_path = info.get("merged_jpg_path") or info.get("jpg_path")
        if not jpg_path:
            continue

        clean_info = {
            "name": info.get("name"),
            "path": info.get("path") or camera_path,
            "jpg_path": jpg_path,
            "width": info.get("width"),
            "height": info.get("height"),
            "world_matrix": info.get("world_matrix"),
        }
        out[camera_path] = clean_info

    return out


def as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def parse_hand_delta(action):
    values = action.get("hand_delta")
    if not isinstance(values, list) or len(values) < 3:
        return [0.0, 0.0, 0.0]
    return [as_float(values[0]), as_float(values[1]), as_float(values[2])]


def xyz(values):
    if not isinstance(values, list) or len(values) < 3:
        return None
    return [as_float(values[0]), as_float(values[1]), as_float(values[2])]


def distance_xy(a, b):
    if a is None or b is None:
        return None
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return (dx * dx + dy * dy) ** 0.5


def delta_z(a, b):
    if a is None or b is None:
        return None
    return b[2] - a[2]


def is_lift_step(item):
    script_name = str(item.get("script_name") or "")
    phase = str(item.get("phase") or "")
    return script_name == "scripu5b" or phase.startswith("lift_step") or "lift" in phase


def action_behavior_tag(item):
    script_name = str(item.get("script_name") or "")
    phase = str(item.get("phase") or "")

    if script_name == "scripu4a" or "approach" in phase:
        return "approach"
    if script_name == "scripu4b" or "preshape" in phase or "thumb_middle" in phase:
        return "preshape_contact"
    if script_name == "scripu4c" or "support" in phase or "light_contact" in phase:
        return "support_contact"
    if script_name == "scripu5a" or "hold" in phase:
        return "hold"
    if is_lift_step(item):
        return "lift_attempt"
    return "other"


def update_joint_targets_from_state(last_joint_targets, state):
    current_targets = state.get("current_joint_targets") if isinstance(state, dict) else None
    if not isinstance(current_targets, dict):
        return []

    updated = []
    for joint in ACTION_JOINTS:
        if joint in current_targets:
            last_joint_targets[joint] = as_float(current_targets[joint])
            updated.append(joint)
    return updated


def build_action(item, last_joint_targets):
    state = item.get("state") or {}
    action = item.get("action") or {}
    if not isinstance(action, dict):
        action = {}

    update_joint_targets_from_state(last_joint_targets, state)

    changed_joints = []
    action_joint_targets = action.get("joint_targets")
    if isinstance(action_joint_targets, dict):
        for joint, value in action_joint_targets.items():
            if joint in ACTION_JOINTS:
                last_joint_targets[joint] = as_float(value)
                changed_joints.append(joint)

    joint_targets = {
        joint: as_float(last_joint_targets.get(joint, 0.0))
        for joint in ACTION_JOINTS
    }
    hand_delta = parse_hand_delta(action)
    vector = [joint_targets[joint] for joint in ACTION_JOINTS] + hand_delta

    changed_dimensions = list(changed_joints)
    for name, value in zip(HAND_DELTA_NAMES, hand_delta):
        if abs(value) > 1e-12:
            changed_dimensions.append(name)

    return {
        "schema_name": SCHEMA_NAME,
        "vector": vector,
        "joint_targets": joint_targets,
        "hand_delta": hand_delta,
        "changed_joints": changed_joints,
        "changed_dimensions": changed_dimensions,
        "source_action_type": action_type_of(item),
        "source_action": action,
        "units": {
            "joint_targets": "degrees",
            "hand_delta": "meters",
        },
    }


def quality_metrics(observation_state, result_state, max_stable_cube_xy_motion):
    obs_cube = xyz(observation_state.get("cube_translate") if isinstance(observation_state, dict) else None)
    result_cube = xyz(result_state.get("cube_translate") if isinstance(result_state, dict) else None)
    cube_xy_motion = distance_xy(obs_cube, result_cube)
    cube_z_motion = delta_z(obs_cube, result_cube)

    if cube_xy_motion is None:
        cube_motion_label = "unknown"
    elif cube_xy_motion <= max_stable_cube_xy_motion:
        cube_motion_label = "stable"
    else:
        cube_motion_label = "large_push"

    return {
        "cube_xy_motion_m": cube_xy_motion,
        "cube_z_motion_m": cube_z_motion,
        "cube_motion_label": cube_motion_label,
        "max_stable_cube_xy_motion_m": max_stable_cube_xy_motion,
    }


def copy_observation_images(sample, images_out_dir, copy_cache):
    run_id = sanitize_filename(sample["run_id"])
    obs_step_id = sanitize_filename(sample["observation"]["source_step_id"])
    dst_dir = images_out_dir / run_id
    dst_dir.mkdir(parents=True, exist_ok=True)

    for camera_path, info in sample["observation"]["images"].items():
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

        camera_name = sanitize_filename(info.get("name") or camera_path)
        dst_path = dst_dir / f"{obs_step_id}_{camera_name}.jpg"
        shutil.copy2(src_path, dst_path)
        copy_cache[cache_key] = str(dst_path)
        info["copied_jpg_path"] = str(dst_path)


def make_sample(
    item,
    observation_item,
    observation_images,
    observation_age_steps,
    last_joint_targets,
    instruction,
    keep_source_instruction,
    max_stable_cube_xy_motion,
):
    target_action = build_action(item, last_joint_targets)
    run_id = str(item.get("run_id") or "unknown_run")
    action_step_id = str(item.get("step_id") or "unknown_action_step")
    observation_step_id = None
    observation_phase = None
    observation_state = {}
    observation_timestamp = None

    if observation_item is not None:
        observation_step_id = observation_item.get("step_id")
        observation_phase = observation_item.get("phase")
        observation_state = observation_item.get("state") or {}
        observation_timestamp = observation_item.get("timestamp")

    if observation_step_id is None:
        observation_step_id = "state_only_no_image"
        observation_phase = "state_only"
        observation_state = item.get("state") or {}

    result_state = item.get("state") or {}
    sample_instruction = item.get("instruction") if keep_source_instruction else instruction
    metrics = quality_metrics(observation_state, result_state, max_stable_cube_xy_motion)

    return {
        "sample_id": f"{sanitize_filename(run_id)}_{sanitize_filename(action_step_id)}",
        "schema_name": SCHEMA_NAME,
        "run_id": run_id,
        "instruction": sample_instruction or DEFAULT_TASK_INSTRUCTION,
        "source_instruction": item.get("instruction"),
        "behavior_tag": action_behavior_tag(item),
        "observation": {
            "source_step_id": observation_step_id,
            "source_phase": observation_phase,
            "source_timestamp": observation_timestamp,
            "age_steps": observation_age_steps,
            "timing": "previous_visual_state" if observation_item is not None else "state_only",
            "state": observation_state,
            "images": observation_images,
        },
        "target_action": {
            **target_action,
            "source_step_id": item.get("step_id"),
            "source_script_name": item.get("script_name"),
            "source_phase": item.get("phase"),
            "source_timestamp": item.get("timestamp"),
        },
        "result_state": result_state,
        "quality": metrics,
        "success": item.get("success"),
        "source": {
            "jsonl": item.get("_source_jsonl"),
            "line": item.get("_source_line"),
        },
    }


def group_by_run(items):
    runs = defaultdict(list)
    for item in items:
        run_id = str(item.get("run_id") or "unknown_run")
        runs[run_id].append(item)

    for run_items in runs.values():
        run_items.sort(key=lambda item: (
            as_float(item.get("timestamp")),
            str(item.get("step_id") or ""),
            int(item.get("_source_line") or 0),
        ))

    return dict(sorted(runs.items()))


def convert_items(
    items,
    action_types,
    include_no_image,
    max_observation_age,
    include_lift_steps,
    instruction,
    keep_source_instruction,
    max_stable_cube_xy_motion,
):
    samples = []
    skipped = []

    for run_id, run_items in group_by_run(items).items():
        last_visual_item = None
        last_visual_images = {}
        last_visual_index = None
        last_joint_targets = {}

        for index, item in enumerate(run_items):
            if item.get("_load_error"):
                skipped.append(skip_row(item, "load_error"))
                continue

            current_images = valid_images(item)
            current_action_type = action_type_of(item)

            if current_action_type in action_types:
                if is_lift_step(item) and not include_lift_steps:
                    skipped.append(skip_row(item, "lift_step_excluded_for_initial_action_learning"))
                    if current_images:
                        last_visual_item = item
                        last_visual_images = current_images
                        last_visual_index = index
                    continue

                observation_item = last_visual_item
                observation_images = dict(last_visual_images)
                observation_age = None if last_visual_index is None else index - last_visual_index

                if observation_item is None and not include_no_image:
                    skipped.append(skip_row(item, "no_previous_visual_observation"))
                elif (
                    observation_age is not None
                    and max_observation_age > 0
                    and observation_age > max_observation_age
                ):
                    skipped.append(skip_row(item, f"observation_too_old_{observation_age}_steps"))
                else:
                    sample = make_sample(
                        item=item,
                        observation_item=observation_item,
                        observation_images=observation_images,
                        observation_age_steps=observation_age,
                        last_joint_targets=last_joint_targets,
                        instruction=instruction,
                        keep_source_instruction=keep_source_instruction,
                        max_stable_cube_xy_motion=max_stable_cube_xy_motion,
                    )
                    samples.append(sample)
            else:
                update_joint_targets_from_state(last_joint_targets, item.get("state") or {})
                skipped.append(skip_row(item, f"non_trainable_action_type_{current_action_type}"))

            if current_images:
                last_visual_item = item
                last_visual_images = current_images
                last_visual_index = index

    return samples, skipped


def skip_row(item, reason):
    return {
        "run_id": item.get("run_id"),
        "step_id": item.get("step_id"),
        "timestamp": item.get("timestamp"),
        "script_name": item.get("script_name"),
        "phase": item.get("phase"),
        "action_type": action_type_of(item),
        "reason": reason,
        "source_jsonl": item.get("_source_jsonl"),
        "source_line": item.get("_source_line"),
    }


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


def csv_index_row(sample):
    target = sample["target_action"]
    observation = sample["observation"]
    hand_delta = target["hand_delta"]
    quality = sample.get("quality") or {}

    return {
        "sample_id": sample["sample_id"],
        "run_id": sample["run_id"],
        "instruction": sample["instruction"],
        "behavior_tag": sample["behavior_tag"],
        "observation_step_id": observation["source_step_id"],
        "observation_phase": observation["source_phase"],
        "observation_age_steps": observation["age_steps"],
        "action_step_id": target["source_step_id"],
        "action_phase": target["source_phase"],
        "action_type": target["source_action_type"],
        "changed_dimensions": " ".join(target["changed_dimensions"]),
        "changed_joints": " ".join(target["changed_joints"]),
        "hand_dx": hand_delta[0],
        "hand_dy": hand_delta[1],
        "hand_dz": hand_delta[2],
        "cube_xy_motion_m": quality.get("cube_xy_motion_m"),
        "cube_z_motion_m": quality.get("cube_z_motion_m"),
        "cube_motion_label": quality.get("cube_motion_label"),
        "image_count": len(observation["images"]),
        "success": sample["success"],
        "source_jsonl": sample["source"]["jsonl"],
        "source_line": sample["source"]["line"],
    }


def csv_action_debug_row(sample):
    row = csv_index_row(sample)
    vector = sample["target_action"]["vector"]
    for index, name in enumerate(ACTION_JOINTS + HAND_DELTA_NAMES):
        row[f"action_{index:02d}_{name}"] = vector[index]
    return row


def schema_document():
    dimensions = []
    for index, joint in enumerate(ACTION_JOINTS):
        dimensions.append({
            "index": index,
            "name": joint,
            "kind": "shadowhand_joint_target",
            "unit": "degrees",
            "meaning": f"Absolute drive target for ShadowHand joint {joint}.",
        })

    for offset, name in enumerate(HAND_DELTA_NAMES, start=len(ACTION_JOINTS)):
        dimensions.append({
            "index": offset,
            "name": name,
            "kind": "hand_base_delta",
            "unit": "meters",
            "meaning": "Small Cartesian base translation applied to the ShadowHand prim.",
        })

    return {
        "schema_name": SCHEMA_NAME,
        "version": 1,
        "action_dim": len(dimensions),
        "dimensions": dimensions,
        "construction": {
            "observation": "Most recent earlier teacher step with valid camera JPG images.",
            "target_action": "Current trainable teacher action converted to 17 joint targets + 3 hand deltas.",
            "joint_target_fill": "Partial joint targets are completed by carrying forward the previous target in the same run; missing initial values are 0.0.",
            "default_trainable_action_types": sorted(TRAINABLE_ACTION_TYPES),
            "default_instruction": DEFAULT_TASK_INSTRUCTION,
            "default_task_scope": "approach/contact/hold. Lift attempts are excluded unless --include-lift-steps is used.",
        },
        "normalization_hint": (
            "For pi0/VLA fine-tuning, normalize each of the 20 dimensions with "
            "the action_min/action_max values in summary.json or with explicit "
            "robot joint limits when available."
        ),
    }


def build_summary(samples, skipped, source_files, output_files, config):
    action_counter = Counter()
    phase_counter = Counter()
    run_counter = Counter()
    skipped_counter = Counter()
    behavior_counter = Counter()
    cube_motion_counter = Counter()
    image_count = 0
    stale_observation_count = 0

    mins = [None] * (len(ACTION_JOINTS) + len(HAND_DELTA_NAMES))
    maxs = [None] * (len(ACTION_JOINTS) + len(HAND_DELTA_NAMES))

    for sample in samples:
        target = sample["target_action"]
        observation = sample["observation"]
        vector = target["vector"]

        run_counter[sample["run_id"]] += 1
        behavior_counter[sample.get("behavior_tag") or "unknown"] += 1
        phase_counter[target.get("source_phase") or "unknown"] += 1
        action_counter[target.get("source_action_type") or "unknown"] += 1
        quality = sample.get("quality") or {}
        cube_motion_counter[quality.get("cube_motion_label") or "unknown"] += 1
        image_count += len(observation.get("images") or {})

        age = observation.get("age_steps")
        if isinstance(age, int) and age > 1:
            stale_observation_count += 1

        for index, value in enumerate(vector):
            if mins[index] is None or value < mins[index]:
                mins[index] = value
            if maxs[index] is None or value > maxs[index]:
                maxs[index] = value

    for row in skipped:
        skipped_counter[row["reason"]] += 1

    dim_names = ACTION_JOINTS + HAND_DELTA_NAMES
    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "schema_name": SCHEMA_NAME,
        "action_dim": len(dim_names),
        "total_samples": len(samples),
        "total_skipped_steps": len(skipped),
        "total_source_files": len(source_files),
        "total_observation_images_referenced": image_count,
        "stale_observation_sample_count": stale_observation_count,
        "source_files": [str(path) for path in source_files],
        "output_files": output_files,
        "config": config,
        "samples_by_run": dict(run_counter),
        "samples_by_behavior_tag": dict(behavior_counter),
        "samples_by_action_phase": dict(phase_counter),
        "samples_by_action_type": dict(action_counter),
        "samples_by_cube_motion_label": dict(cube_motion_counter),
        "skipped_by_reason": dict(skipped_counter),
        "action_min": {name: mins[index] for index, name in enumerate(dim_names)},
        "action_max": {name: maxs[index] for index, name in enumerate(dim_names)},
    }


def preview_line(sample):
    target = sample["target_action"]
    observation = sample["observation"]
    changed = ", ".join(target["changed_dimensions"]) or "carry_previous_targets"
    hand_delta = target["hand_delta"]
    return (
        f"{sample['sample_id']}: image_state={observation['source_step_id']} "
        f"({observation['source_phase']}, images={len(observation['images'])}, "
        f"age={observation['age_steps']}) -> action={target['source_step_id']} "
        f"({target['source_phase']}, type={target['source_action_type']}), "
        f"behavior={sample['behavior_tag']}, change={changed}, hand_delta={hand_delta}, "
        f"cube_motion={sample['quality']['cube_motion_label']}"
    )


def index_fieldnames():
    return [
        "sample_id", "run_id", "instruction", "behavior_tag",
        "observation_step_id", "observation_phase", "observation_age_steps",
        "action_step_id", "action_phase", "action_type",
        "changed_dimensions", "changed_joints", "hand_dx", "hand_dy", "hand_dz",
        "cube_xy_motion_m", "cube_z_motion_m", "cube_motion_label",
        "image_count", "success", "source_jsonl", "source_line",
    ]


def action_debug_fieldnames():
    return index_fieldnames() + [
        f"action_{index:02d}_{name}"
        for index, name in enumerate(ACTION_JOINTS + HAND_DELTA_NAMES)
    ]


def main():
    args = parse_args()
    input_root = args.input_root
    output_root = args.output_root
    action_types = {
        item.strip()
        for item in args.action_types.split(",")
        if item.strip()
    }

    if not input_root.exists():
        raise FileNotFoundError(f"input root not found: {input_root}")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_jsonl = output_dir / "shadowhand_action_dataset.jsonl"
    dataset_json = output_dir / "shadowhand_action_dataset.json"
    dataset_csv = output_dir / "dataset_index.csv"
    action_debug_csv = output_dir / "action_debug.csv"
    skipped_csv = output_dir / "skipped_steps.csv"
    schema_json = output_dir / "schema.json"
    summary_json = output_dir / "summary.json"
    preview_txt = output_dir / "preview.txt"
    images_out_dir = output_dir / "images"

    source_files = list(iter_steps_jsonl(input_root))
    items = []
    for source_file in source_files:
        items.extend(load_items(source_file))

    samples, skipped = convert_items(
        items=items,
        action_types=action_types,
        include_no_image=args.include_no_image,
        max_observation_age=args.max_observation_age,
        include_lift_steps=args.include_lift_steps,
        instruction=args.instruction,
        keep_source_instruction=args.keep_source_instruction,
        max_stable_cube_xy_motion=args.max_stable_cube_xy_motion,
    )

    if args.copy_images:
        images_out_dir.mkdir(parents=True, exist_ok=True)
        copy_cache = {}
        for sample in samples:
            copy_observation_images(sample, images_out_dir, copy_cache)

    write_jsonl(dataset_jsonl, samples)
    dataset_json.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
    schema_json.write_text(json.dumps(schema_document(), ensure_ascii=False, indent=2), encoding="utf-8")

    index_rows = [csv_index_row(sample) for sample in samples]
    write_csv(
        dataset_csv,
        index_rows,
        index_fieldnames(),
    )

    debug_rows = [csv_action_debug_row(sample) for sample in samples]
    write_csv(
        action_debug_csv,
        debug_rows,
        action_debug_fieldnames(),
    )

    write_csv(
        skipped_csv,
        skipped,
        [
            "run_id", "step_id", "timestamp", "script_name", "phase",
            "action_type", "reason", "source_jsonl", "source_line",
        ],
    )

    preview_lines = [preview_line(sample) for sample in samples[: args.preview_count]]
    preview_txt.write_text("\n".join(preview_lines) + ("\n" if preview_lines else ""), encoding="utf-8")

    output_files = {
        "dataset_jsonl": str(dataset_jsonl),
        "dataset_json": str(dataset_json),
        "dataset_csv": str(dataset_csv),
        "action_debug_csv": str(action_debug_csv),
        "skipped_csv": str(skipped_csv),
        "schema_json": str(schema_json),
        "summary_json": str(summary_json),
        "preview_txt": str(preview_txt),
    }
    if args.copy_images:
        output_files["copied_images_dir"] = str(images_out_dir)

    config = {
        "instruction": args.instruction,
        "keep_source_instruction": args.keep_source_instruction,
        "include_lift_steps": args.include_lift_steps,
        "include_no_image": args.include_no_image,
        "max_observation_age": args.max_observation_age,
        "max_stable_cube_xy_motion": args.max_stable_cube_xy_motion,
        "action_types": sorted(action_types),
    }
    summary = build_summary(samples, skipped, source_files, output_files, config)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("shadowhand action dataset prepared")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()