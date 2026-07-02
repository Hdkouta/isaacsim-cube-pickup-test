import json
from pathlib import Path

import omni.usd
from pxr import UsdGeom, Gf

INITIAL_FILE = Path(r"C:\robot_assets\shadow_hand_initial.json")

CORRECT_HAND_TRANSLATE = [
    -0.2922104709302832,
    0.0326124528172253,
    0.1902782721458129,
]

stage = omni.usd.get_context().get_stage()


def find_by_name(name):
    for prim in stage.Traverse():
        if prim.GetName() == name:
            return prim
    raise RuntimeError(f"{name} not found")


def get_translate_op(prim):
    xform = UsdGeom.Xformable(prim)
    for op in xform.GetOrderedXformOps():
        if op.GetOpName() == "xformOp:translate":
            return op
    return xform.AddTranslateOp()


def get_translate(prim):
    value = get_translate_op(prim).Get()
    if value is None:
        return [0.0, 0.0, 0.0]
    return [float(value[0]), float(value[1]), float(value[2])]


def set_translate(prim, pos):
    get_translate_op(prim).Set(Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2])))


data = json.loads(INITIAL_FILE.read_text(encoding="utf-8"))

hand = stage.GetPrimAtPath(data["hand_path"])
if not hand.IsValid():
    hand = find_by_name("shadow_hand")

old_hand_pos = get_translate(hand)

set_translate(hand, CORRECT_HAND_TRANSLATE)

data["hand_translate"] = CORRECT_HAND_TRANSLATE
INITIAL_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

try:
    open_hand_targets()
except Exception:
    pass

omni.usd.get_context().save_stage()

print("hand initial position repaired")
print("old hand:", old_hand_pos)
print("new hand:", CORRECT_HAND_TRANSLATE)
print("initial file updated:", INITIAL_FILE)