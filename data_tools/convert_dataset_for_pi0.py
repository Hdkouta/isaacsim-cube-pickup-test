import argparse
import json
from pathlib import Path

DEFAULT_INPUT_ROOT = Path(r"C:\VScode\Yoshida_script\shadowhand_action_dataset")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert shadowhand_action_dataset JSONL into pi0-friendly fine-tuning JSONL."
    )
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=None,
        help="Input dataset JSONL. If omitted, latest shadowhand_action_dataset/*/shadowhand_action_dataset.jsonl is used.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=None,
        help="Output JSONL path. Default: <input_dir>/pi0_finetune_dataset.jsonl",
    )
    parser.add_argument(
        "--camera-filter",
        default="",
        help="Comma-separated camera name filters. Empty means all cameras.",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=8,
        help="Maximum observation image paths to include per sample.",
    )
    parser.add_argument(
        "--relative-image-paths",
        action="store_true",
        help="Write image paths relative to output JSONL directory.",
    )
    return parser.parse_args()


def find_latest_input_jsonl():
    candidates = sorted(DEFAULT_INPUT_ROOT.glob("*/shadowhand_action_dataset.jsonl"))
    if not candidates:
        raise FileNotFoundError(
            f"No input dataset found under {DEFAULT_INPUT_ROOT}. Run prepare_shadowhand_action_dataset.py first."
        )
    return candidates[-1]


def parse_filter(filter_text):
    if not filter_text.strip():
        return []
    return [token.strip().lower() for token in filter_text.split(",") if token.strip()]


def camera_match(camera_info, filters):
    if not filters:
        return True
    name = str(camera_info.get("name") or "").lower()
    path = str(camera_info.get("path") or "").lower()
    return any(token in name or token in path for token in filters)


def pick_images(images_dict, filters, max_images):
    selected = []
    if not isinstance(images_dict, dict):
        return selected

    for _, info in sorted(images_dict.items(), key=lambda pair: str(pair[0])):
        if not isinstance(info, dict):
            continue
        if not camera_match(info, filters):
            continue

        jpg = info.get("copied_jpg_path") or info.get("jpg_path")
        if not jpg:
            continue
        selected.append(str(jpg))
        if len(selected) >= max_images:
            break

    return selected


def maybe_relpath(path_text, output_dir, enable_relative):
    if not enable_relative:
        return path_text
    try:
        return str(Path(path_text).resolve().relative_to(output_dir.resolve()))
    except Exception:
        return path_text


def convert_row(item, filters, max_images, output_dir, enable_relative):
    observation = item.get("observation") or {}
    action = item.get("target_action") or {}

    image_paths = pick_images(observation.get("images") or {}, filters, max_images)
    image_paths = [maybe_relpath(path, output_dir, enable_relative) for path in image_paths]

    return {
        "id": item.get("sample_id"),
        "instruction": item.get("instruction"),
        "images": image_paths,
        "action": {
            "schema_name": action.get("schema_name"),
            "vector": action.get("vector") or [],
            "joint_targets": action.get("joint_targets") or {},
            "hand_delta": action.get("hand_delta") or [0.0, 0.0, 0.0],
        },
        "metadata": {
            "run_id": item.get("run_id"),
            "behavior_tag": item.get("behavior_tag"),
            "observation_phase": observation.get("source_phase"),
            "action_phase": item.get("action_phase"),
            "cube_motion_label": (item.get("quality") or {}).get("cube_motion_label"),
            "source_jsonl": (item.get("source") or {}).get("jsonl"),
            "source_line": (item.get("source") or {}).get("line"),
        },
    }


def main():
    args = parse_args()

    input_jsonl = args.input_jsonl or find_latest_input_jsonl()
    if not input_jsonl.exists():
        raise FileNotFoundError(f"input jsonl not found: {input_jsonl}")

    output_jsonl = args.output_jsonl or (input_jsonl.parent / "pi0_finetune_dataset.jsonl")
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    filters = parse_filter(args.camera_filter)
    rows = []
    with input_jsonl.open("r", encoding="utf-8-sig") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))

    converted = [
        convert_row(item, filters, args.max_images, output_jsonl.parent, args.relative_image_paths)
        for item in rows
    ]

    with output_jsonl.open("w", encoding="utf-8") as f:
        for row in converted:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "input_jsonl": str(input_jsonl),
        "output_jsonl": str(output_jsonl),
        "total_samples": len(converted),
        "camera_filter": filters,
        "max_images": args.max_images,
        "relative_image_paths": args.relative_image_paths,
    }
    (output_jsonl.parent / "pi0_finetune_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("pi0 fine-tune dataset exported")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
