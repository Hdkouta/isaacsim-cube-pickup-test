import json
from pathlib import Path

import omni.usd
from pxr import Gf, UsdGeom, UsdPhysics

try:
    from pxr import PhysxSchema
except Exception:
    PhysxSchema = None

INITIAL_FILE = Path(r"C:\robot_assets\shadow_hand_initial.json")
DEFAULT_CUBE_MASS_KG = 0.005

HAND_PATH_CANDIDATES = [
    "/World/shadow_hand",
    "/shadow_hand",
    "/World/ShadowHand",
    "/ShadowHand",
]

CUBE_PATH_CANDIDATES = [
    "/World/Cube",
    "/Cube",
]

FINGER_KEYS = ["FFJ", "MFJ", "RFJ", "LFJ", "THJ"]
DRIVE_NAMES = ["angular", "rotX", "rotY", "rotZ"]

stage = omni.usd.get_context().get_stage()


def set_attr_if_exists(api, getter_name, value):
    getter = getattr(api, getter_name, None)
    if getter is None:
        return False
    attr = getter()
    if attr:
        attr.Set(value)
        return True
    return False


def find_by_name(name):
    for prim in stage.Traverse():
        if prim.GetName() == name:
            return prim
    raise RuntimeError(f"{name} not found")


def find_prim(paths, fallback_name=None):
    for path in paths:
        prim = stage.GetPrimAtPath(path)
        if prim.IsValid():
            return prim, path

    if fallback_name:
        prim = find_by_name(fallback_name)
        return prim, str(prim.GetPath())

    raise RuntimeError(f"Prim not found: {paths}")


def get_translate_op(prim):
    xform = UsdGeom.Xformable(prim)
    for op in xform.GetOrderedXformOps():
        if op.GetOpName() == "xformOp:translate":
            return op
    return xform.AddTranslateOp()


def get_scale_op(prim):
    xform = UsdGeom.Xformable(prim)
    for op in xform.GetOrderedXformOps():
        if op.GetOpName() == "xformOp:scale":
            return op
    return xform.AddScaleOp()


def get_translate(prim):
    value = get_translate_op(prim).Get()
    if value is None:
        return [0.0, 0.0, 0.0]
    return [float(value[0]), float(value[1]), float(value[2])]


def get_scale(prim):
    value = get_scale_op(prim).Get()
    if value is None:
        return [1.0, 1.0, 1.0]
    return [float(value[0]), float(value[1]), float(value[2])]


def get_cube_usd_size(cube):
    if cube.IsA(UsdGeom.Cube):
        value = UsdGeom.Cube(cube).GetSizeAttr().Get()
        if value is not None:
            return float(value)
    return 1.0


def zero_velocity(prim):
    rb = UsdPhysics.RigidBodyAPI.Apply(prim)
    set_attr_if_exists(rb, "GetVelocityAttr", Gf.Vec3f(0.0, 0.0, 0.0))
    set_attr_if_exists(rb, "GetAngularVelocityAttr", Gf.Vec3f(0.0, 0.0, 0.0))


def enable_gravity_dynamic(prim):
    rb = UsdPhysics.RigidBodyAPI.Apply(prim)
    set_attr_if_exists(rb, "GetRigidBodyEnabledAttr", True)
    set_attr_if_exists(rb, "GetKinematicEnabledAttr", False)
    set_attr_if_exists(rb, "GetStartsAsleepAttr", False)

    if PhysxSchema is not None:
        try:
            physx_rb = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
            set_attr_if_exists(physx_rb, "GetDisableGravityAttr", False)
            print("PhysX gravity enabled")
        except Exception as e:
            print(f"PhysX gravity attr skipped: {e}")

    zero_velocity(prim)


def get_cube_mass(cube):
    mass_api = UsdPhysics.MassAPI.Apply(cube)
    value = mass_api.GetMassAttr().Get()
    if value is None:
        value = DEFAULT_CUBE_MASS_KG
    mass_api.GetMassAttr().Set(float(value))
    return float(value)


def open_hand_targets():
    count = 0

    for prim in stage.Traverse():
        name = prim.GetName()

        if any(key in name for key in FINGER_KEYS):
            for drive_name in DRIVE_NAMES:
                drive = UsdPhysics.DriveAPI.Apply(prim, drive_name)
                drive.GetTargetPositionAttr().Set(0.0)
                drive.GetStiffnessAttr().Set(150.0)
                drive.GetDampingAttr().Set(20.0)
                drive.GetMaxForceAttr().Set(800.0)

            count += 1

    print(f"opened hand targets: {count}")


hand, hand_path = find_prim(HAND_PATH_CANDIDATES, fallback_name="shadow_hand")
cube, cube_path = find_prim(CUBE_PATH_CANDIDATES, fallback_name="Cube")

open_hand_targets()

cube_translate = get_translate(cube)
cube_scale = get_scale(cube)
cube_usd_size = get_cube_usd_size(cube)
cube_mass_kg = get_cube_mass(cube)

cube_dimensions = [
    cube_usd_size * cube_scale[0],
    cube_usd_size * cube_scale[1],
    cube_usd_size * cube_scale[2],
]

table_z = cube_translate[2] - cube_dimensions[2] / 2.0

UsdPhysics.CollisionAPI.Apply(cube)
enable_gravity_dynamic(cube)

data = {
    "hand_path": hand_path,
    "cube_path": cube_path,
    "hand_translate": get_translate(hand),
    "cube_translate": cube_translate,
    "cube_scale": cube_scale,
    "cube_usd_size": cube_usd_size,
    "cube_dimensions": cube_dimensions,
    "table_z": table_z,
    "cube_mass_kg": cube_mass_kg,
}

INITIAL_FILE.parent.mkdir(parents=True, exist_ok=True)
INITIAL_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

print("saved current initial state:")
print(json.dumps(data, indent=2))

omni.usd.get_context().save_stage()
print("saved stage: current hand/cube pose and cube size saved")
