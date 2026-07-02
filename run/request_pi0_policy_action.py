import argparse
import base64
import json
import mimetypes
import time
import urllib.error
import urllib.request
from pathlib import Path


ACTION_SCHEMA_NAME = "shadowhand_joint17_handdelta3_v1"
TASK_INSTRUCTION = "control the ShadowHand to approach, contact, and hold the cube"
ACTION_JOINTS = [
    "FFJ3", "FFJ2", "FFJ1",
    "MFJ3", "MFJ2", "MFJ1",
    "RFJ3", "RFJ2", "RFJ1",
    "LFJ4", "LFJ3", "LFJ2", "LFJ1",
    "THJ4", "THJ3", "THJ2", "THJ1",
]
HAND_DELTA_NAMES = ["hand_dx", "hand_dy", "hand_dz"]
AXIS_NAMES = ACTION_JOINTS + HAND_DELTA_NAMES

DEFAULT_EVAL_ROOT = Path(r"C:\VScode\Yoshida_script\pi0_action_eval")
DEFAULT_OUTPUT_ACTION = Path(r"C:\VScode\Yoshida_script\configs\action_input.json")
DEFAULT_OUTPUT_ROOT = Path(r"C:\VScode\Yoshida_script\results\policy_api")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Request a 20D ShadowHand action from a pi0 policy API and write configs/action_input.json."
    )
    parser.add_argument("--policy-url", required=True, help="pi0 policy endpoint, for example http://PI0_VM_IP:8000/predict")
    parser.add_argument("--instruction", default=TASK_INSTRUCTION)
    parser.add_argument("--image", action="append", default=[], help="Observation image path. Can be repeated.")
    parser.add_argument("--image-glob", action="append", default=[], help="Glob for observation images. Can be repeated.")
    parser.add_argument(
        "--latest-eval-images",
        action="store_true",
        help=r"Use image paths from the latest C:\VScode\Yoshida_script\pi0_action_eval\*\eval_steps.jsonl.",
    )
    parser.add_argument("--latest-eval-root", type=Path, default=DEFAULT_EVAL_ROOT)
    parser.add_argument(
        "--latest-eval-phase",
        default="env_ready,before_action",
        help="Comma-separated phases to search in latest eval logs, in priority order.",
    )
    parser.add_argument(
        "--image-mode",
        choices=["data-url", "base64-object", "path"],
        default="data-url",
        help="How images are sent in the JSON request.",
    )
    parser.add_argument("--context-json", type=Path, default=None, help="Optional JSON object merged into request.context.")
    parser.add_argument("--output-action", type=Path, default=DEFAULT_OUTPUT_ACTION)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        help="Extra HTTP header as 'Name: value'. Can be repeated.",
    )
    parser.add_argument("--validate-images", action="store_true", help="Fail before POST if any image file is missing.")
    parser.add_argument(
        "--allow-check-fail",
        action="store_true",
        help="Write action_input.json even if API-format checks are not all true.",
    )
    return parser.parse_args()


def load_json_object(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise RuntimeError(f"JSON file must contain an object: {path}")
    return data


def parse_header(header_text):
    if ":" not in header_text:
        raise RuntimeError(f"header must be 'Name: value', got: {header_text}")
    name, value = header_text.split(":", 1)
    name = name.strip()
    if not name:
        raise RuntimeError(f"header name is empty: {header_text}")
    return name, value.strip()


def read_eval_rows(eval_jsonl):
    rows = []
    with eval_jsonl.open("r", encoding="utf-8-sig") as f:
        for line in f:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def image_paths_from_eval_step(step):
    images = step.get("images") or {}
    if not isinstance(images, dict):
        return []

    paths = []
    for _, info in sorted(images.items(), key=lambda pair: str(pair[0])):
        if not isinstance(info, dict) or info.get("skipped"):
            continue
        jpg_path = info.get("jpg_path") or info.get("copied_jpg_path")
        if jpg_path:
            paths.append(str(jpg_path))
    return paths


def load_latest_eval_images(eval_root, phase_priority):
    eval_files = sorted(eval_root.glob("*/eval_steps.jsonl"))
    for eval_jsonl in reversed(eval_files):
        rows = read_eval_rows(eval_jsonl)
        for phase in phase_priority:
            for step in reversed(rows):
                if step.get("phase") != phase:
                    continue
                image_paths = image_paths_from_eval_step(step)
                if image_paths:
                    context = {
                        "observation_source": "latest_eval_step",
                        "eval_jsonl": str(eval_jsonl),
                        "run_id": step.get("run_id"),
                        "step_id": step.get("step_id"),
                        "phase": step.get("phase"),
                        "state": step.get("state") or {},
                        "image_paths": image_paths,
                    }
                    return image_paths, context
    raise FileNotFoundError(f"no matching eval images found under {eval_root}")


def collect_image_paths(args):
    paths = list(args.image)
    for pattern in args.image_glob:
        paths.extend(str(path) for path in sorted(Path().glob(pattern)))

    context = {}
    if args.latest_eval_images:
        phases = [phase.strip() for phase in args.latest_eval_phase.split(",") if phase.strip()]
        latest_paths, latest_context = load_latest_eval_images(args.latest_eval_root, phases)
        paths.extend(latest_paths)
        context.update(latest_context)

    unique_paths = []
    seen = set()
    for path in paths:
        if path not in seen:
            unique_paths.append(path)
            seen.add(path)

    return unique_paths, context


def validate_image_files(image_paths):
    missing = [path for path in image_paths if not Path(path).exists()]
    if missing:
        preview = "\n".join(missing[:20])
        raise FileNotFoundError(f"missing image files: {len(missing)}\n{preview}")


def encode_image(path, mode):
    path_obj = Path(path)
    mime_type = mimetypes.guess_type(path_obj.name)[0] or "image/jpeg"

    if mode == "path":
        return str(path)

    data = path_obj.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    if mode == "data-url":
        return f"data:{mime_type};base64,{encoded}"

    return {
        "path": str(path),
        "mime_type": mime_type,
        "data_base64": encoded,
    }


def build_request(args, image_paths, eval_context):
    context = dict(eval_context)
    if args.context_json:
        context.update(load_json_object(args.context_json))

    request_body = {
        "instruction": args.instruction,
        "images": [encode_image(path, args.image_mode) for path in image_paths],
        "context": context,
    }
    return request_body


def post_json(url, body, timeout, headers):
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        error_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} from policy API:\n{error_text}") from e

    return json.loads(text)


def find_action_candidate(data):
    if not isinstance(data, dict):
        raise RuntimeError("policy response must be a JSON object")

    if "vector" in data or "joint_targets" in data:
        return data

    for key in ("action", "target_action", "policy_action", "prediction", "result", "output"):
        value = data.get(key)
        if isinstance(value, dict):
            try:
                return find_action_candidate(value)
            except RuntimeError:
                pass

    raise RuntimeError("could not find action payload in policy response")


def ensure_number(value, name):
    try:
        return float(value)
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"{name} must be a number, got {value!r}") from e


def normalize_vector(vector, axis_names):
    if not isinstance(vector, list) or len(vector) != 20:
        raise RuntimeError("vector must be a 20 element list")

    values = [ensure_number(value, f"vector[{index}]") for index, value in enumerate(vector)]
    if isinstance(axis_names, list) and len(axis_names) == 20 and axis_names != AXIS_NAMES:
        by_name = {str(name): values[index] for index, name in enumerate(axis_names)}
        missing = [name for name in AXIS_NAMES if name not in by_name]
        if missing:
            raise RuntimeError(f"axis_names missing expected names: {missing}")
        values = [by_name[name] for name in AXIS_NAMES]
    return values


def normalize_action(response):
    payload = find_action_candidate(response)
    response_axis_names = payload.get("axis_names") or response.get("axis_names")
    axis_names = response_axis_names or AXIS_NAMES
    schema_name = payload.get("schema_name") or response.get("schema_name")

    if "vector" in payload:
        vector = normalize_vector(payload.get("vector"), axis_names)
        joint_targets = {joint: vector[index] for index, joint in enumerate(ACTION_JOINTS)}
        hand_delta = vector[len(ACTION_JOINTS):]
    else:
        raw_joint_targets = payload.get("joint_targets")
        raw_hand_delta = payload.get("hand_delta")
        if not isinstance(raw_joint_targets, dict):
            raise RuntimeError("action payload must contain vector or joint_targets")
        if not isinstance(raw_hand_delta, list) or len(raw_hand_delta) != 3:
            raise RuntimeError("hand_delta must be a 3 element list")
        joint_targets = {
            joint: ensure_number(raw_joint_targets[joint], f"joint_targets.{joint}")
            for joint in ACTION_JOINTS
        }
        hand_delta = [ensure_number(value, f"hand_delta[{index}]") for index, value in enumerate(raw_hand_delta)]
        vector = [joint_targets[joint] for joint in ACTION_JOINTS] + hand_delta

    return {
        "schema_name": schema_name,
        "axis_names": axis_names,
        "response_axis_names": response_axis_names,
        "vector": vector,
        "joint_targets": joint_targets,
        "hand_delta": hand_delta,
    }


def validate_response(response, action):
    checks = {
        "ok_true": response.get("ok") is True,
        "schema_ok": action.get("schema_name") == ACTION_SCHEMA_NAME,
        "vector_len_20": isinstance(action.get("vector"), list) and len(action["vector"]) == 20,
        "joint_targets_len_17": isinstance(action.get("joint_targets"), dict)
        and len(action["joint_targets"]) == 17
        and all(joint in action["joint_targets"] for joint in ACTION_JOINTS),
        "hand_delta_len_3": isinstance(action.get("hand_delta"), list) and len(action["hand_delta"]) == 3,
        "axis_names_len_20": isinstance(action.get("response_axis_names"), list)
        and len(action["response_axis_names"]) == 20,
    }
    return checks


def write_outputs(args, request_body, response, action, checks):
    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_dir = args.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    request_path = run_dir / "policy_request.json"
    response_path = run_dir / "policy_response.json"
    checks_path = run_dir / "checks.json"
    request_path.write_text(json.dumps(request_body, ensure_ascii=False, indent=2), encoding="utf-8")
    response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    checks_path.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")

    action_output = {
        "schema_name": ACTION_SCHEMA_NAME,
        "axis_names": AXIS_NAMES,
        "vector": action["vector"],
        "joint_targets": action["joint_targets"],
        "hand_delta": action["hand_delta"],
        "source": {
            "policy_url": args.policy_url,
            "policy_response": str(response_path),
            "checks": str(checks_path),
        },
    }
    args.output_action.parent.mkdir(parents=True, exist_ok=True)
    args.output_action.write_text(json.dumps(action_output, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "run_dir": str(run_dir),
        "request_path": str(request_path),
        "response_path": str(response_path),
        "checks_path": str(checks_path),
        "action_file": str(args.output_action),
    }


def main():
    args = parse_args()
    headers = dict(parse_header(header) for header in args.header)

    image_paths, eval_context = collect_image_paths(args)
    if args.validate_images:
        validate_image_files(image_paths)

    request_body = build_request(args, image_paths, eval_context)
    print("policy request summary")
    print(json.dumps({
        "policy_url": args.policy_url,
        "instruction": args.instruction,
        "image_count": len(image_paths),
        "image_mode": args.image_mode,
        "context_keys": sorted(request_body["context"].keys()),
    }, ensure_ascii=False, indent=2))

    response = post_json(args.policy_url, request_body, args.timeout, headers)
    print("policy response JSON")
    print(json.dumps(response, ensure_ascii=False, indent=2))

    action = normalize_action(response)
    checks = validate_response(response, action)
    failed = [name for name, ok in checks.items() if not ok]
    print("policy response checks")
    print(json.dumps(checks, ensure_ascii=False, indent=2))

    if failed and not args.allow_check_fail:
        raise RuntimeError(f"policy response checks failed: {failed}")

    outputs = write_outputs(args, request_body, response, action, checks)
    print("pi0 policy action written")
    print(json.dumps({
        **outputs,
        "failed_checks": failed,
        "status": "PASS" if not failed else "FAIL",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
