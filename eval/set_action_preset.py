import argparse
import json
from pathlib import Path

ACTION_FILE_DEFAULT = Path(r"C:\VScode\Yoshida_script\configs\action_input.json")

ACTION_JOINTS = [
    "FFJ3", "FFJ2", "FFJ1",
    "MFJ3", "MFJ2", "MFJ1",
    "RFJ3", "RFJ2", "RFJ1",
    "LFJ4", "LFJ3", "LFJ2", "LFJ1",
    "THJ4", "THJ3", "THJ2", "THJ1",
]

DEFAULT_APPROACH_DELTA = [0.002, -0.002, -0.002]

PRESET_VECTORS = {
    "approach_only": [0.0] * 17,
    "preshape": [8, 12, 8, 10, 16, 12, 8, 12, 8, 4, 8, 12, 8, 18, 20, 18, 14],
    "thumb_middle_contact": [8, 12, 8, 22, 30, 24, 8, 12, 8, 4, 8, 12, 8, 30, 34, 32, 24],
    "support_contact": [10, 14, 10, 22, 30, 24, 10, 14, 10, 5, 10, 14, 10, 30, 34, 32, 24],
    "final_light_contact": [12, 16, 12, 26, 34, 26, 12, 16, 12, 6, 12, 16, 12, 34, 38, 36, 28],
    "hold_close": [14, 18, 14, 30, 38, 30, 14, 18, 14, 7, 14, 18, 14, 40, 44, 42, 32],
    "final_hold": [14, 18, 14, 30, 38, 30, 14, 18, 14, 7, 14, 18, 14, 38, 42, 40, 32],
}

PRESET_HAND_DELTA = {
    preset: list(DEFAULT_APPROACH_DELTA)
    for preset in PRESET_VECTORS
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Write a staged 20D ShadowHand action preset to configs/action_input.json"
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESET_VECTORS.keys()),
        required=True,
        help="Action preset name to write.",
    )
    parser.add_argument(
        "--action-file",
        type=Path,
        default=ACTION_FILE_DEFAULT,
        help=r"Output action JSON path. Default: C:\VScode\Yoshida_script\configs\action_input.json",
    )
    parser.add_argument(
        "--hand-delta",
        type=float,
        nargs=3,
        metavar=("DX", "DY", "DZ"),
        default=None,
        help="Optional hand delta override in meters. Use 0 0 0 only when applying actions sequentially without reset.",
    )
    return parser.parse_args()


def build_payload(preset, hand_delta_override):
    vector = PRESET_VECTORS[preset]
    joint_targets = {joint: float(vector[index]) for index, joint in enumerate(ACTION_JOINTS)}
    hand_delta = list(hand_delta_override) if hand_delta_override is not None else PRESET_HAND_DELTA[preset]

    return {
        "schema_name": "shadowhand_joint17_handdelta3_v1",
        "preset_name": preset,
        "joint_targets": joint_targets,
        "hand_delta": [float(value) for value in hand_delta],
    }


def main():
    args = parse_args()
    payload = build_payload(args.preset, args.hand_delta)

    args.action_file.parent.mkdir(parents=True, exist_ok=True)
    args.action_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("pi0 action preset written")
    print(json.dumps({
        "action_file": str(args.action_file),
        "preset": args.preset,
        "hand_delta": payload["hand_delta"],
        "key_joints": {
            "FFJ3": payload["joint_targets"]["FFJ3"],
            "MFJ3": payload["joint_targets"]["MFJ3"],
            "THJ4": payload["joint_targets"]["THJ4"],
            "THJ1": payload["joint_targets"]["THJ1"],
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
