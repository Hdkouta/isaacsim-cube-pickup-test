import json
import re
import time
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

import omni.kit.app
import omni.usd
from pxr import Gf, UsdGeom, UsdPhysics, UsdShade

try:
    from pxr import PhysxSchema
except Exception:
    PhysxSchema = None

try:
    from omni.isaac.sensor import Camera
except Exception:
    from isaacsim.sensors.camera import Camera

INITIAL_FILE = Path(r"C:\robot_assets\shadow_hand_initial.json")
LIFT_START_FILE = Path(r"C:\robot_assets\shadow_hand_lift_start.json")
LOG_FILE = Path(r"C:\robot_assets\isaac_pi0_log.txt")
CAMERA_SAVE_DIR = Path(r"C:\VScode\Yoshida_script\camera")
TEACHER_DATA_ROOT = Path(r"C:\VScode\Yoshida_script\teacher_data")

DEFAULT_CUBE_SCALE = [0.05, 0.10, 0.05]
DEFAULT_CUBE_USD_SIZE = 1.0
DEFAULT_TABLE_Z = 0.015
DEFAULT_CUBE_MASS_KG = 0.005
OBJECT_MASS_OVERRIDE_KG = 0.0025

CUBE_STATIC_FRICTION = 6.0
CUBE_DYNAMIC_FRICTION = 5.0
FINGER_STATIC_FRICTION = 5.0
FINGER_DYNAMIC_FRICTION = 4.0
CUBE_LINEAR_DAMPING = 0.20
CUBE_ANGULAR_DAMPING = 0.35

APPROACH_DX = 0.002
APPROACH_DY = -0.002
APPROACH_DZ = -0.002
APPROACH_STEPS = 24

LIFT_STEP_DZ = 0.0015
LIFT_STEP_DX = 0.0002
LIFT_STEP_DY = 0.0
LIFT_STEPS = 12

CUBE_SCALE = DEFAULT_CUBE_SCALE
CUBE_USD_SIZE = DEFAULT_CUBE_USD_SIZE
TABLE_Z = DEFAULT_TABLE_Z
CUBE_MASS_KG = DEFAULT_CUBE_MASS_KG

CAMERA_RESOLUTION = (640, 480)

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
WRIST_TARGETS = {"WRJ1": 0.0, "WRJ2": 0.0}
FOREARM_NAME = "robot0_forearm"

ACTION_JOINTS = [
    "FFJ3", "FFJ2", "FFJ1",
    "MFJ3", "MFJ2", "MFJ1",
    "RFJ3", "RFJ2", "RFJ1",
    "LFJ4", "LFJ3", "LFJ2", "LFJ1",
    "THJ4", "THJ3", "THJ2", "THJ1",
]

PRESHAPE_TARGETS = {
    "FFJ3": 10, "FFJ2": 16, "FFJ1": 12,
    "MFJ3": 14, "MFJ2": 22, "MFJ1": 16,
    "RFJ3": 10, "RFJ2": 16, "RFJ1": 12,
    "LFJ4": 6, "LFJ3": 10, "LFJ2": 16, "LFJ1": 12,
    "THJ4": 24, "THJ3": 26, "THJ2": 24, "THJ1": 20,
}

THUMB_MIDDLE_CONTACT_TARGETS = {
    "MFJ3": 22, "MFJ2": 30, "MFJ1": 24,
    "THJ4": 30, "THJ3": 34, "THJ2": 32, "THJ1": 24,
}

SUPPORT_FINGER_TARGETS = {
    "FFJ3": 10, "FFJ2": 14, "FFJ1": 10,
    "RFJ3": 10, "RFJ2": 14, "RFJ1": 10,
    "LFJ4": 5, "LFJ3": 10, "LFJ2": 14, "LFJ1": 10,
}

CONTACT_TARGETS = {
    "FFJ3": 12, "FFJ2": 16, "FFJ1": 12,
    "MFJ3": 26, "MFJ2": 34, "MFJ1": 26,
    "RFJ3": 12, "RFJ2": 16, "RFJ1": 12,
    "LFJ4": 6, "LFJ3": 12, "LFJ2": 16, "LFJ1": 12,
    "THJ4": 34, "THJ3": 38, "THJ2": 36, "THJ1": 28,
}

STRONG_CLOSE_TARGETS = {
    "FFJ3": 16, "FFJ2": 20, "FFJ1": 16,
    "MFJ3": 34, "MFJ2": 42, "MFJ1": 34,
    "RFJ3": 16, "RFJ2": 20, "RFJ1": 16,
    "LFJ4": 8, "LFJ3": 16, "LFJ2": 20, "LFJ1": 16,
    "THJ4": 44, "THJ3": 48, "THJ2": 46, "THJ1": 36,
}

stage = omni.usd.get_context().get_stage()
_camera_cache = {}
CURRENT_JOINT_TARGETS = {}

TEACHER_RUN_ID = time.strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
TEACHER_RUN_DIR = TEACHER_DATA_ROOT / TEACHER_RUN_ID
TEACHER_IMAGES_DIR = TEACHER_RUN_DIR / "images"
TEACHER_JSONL = TEACHER_RUN_DIR / "steps.jsonl"
TEACHER_RUN_DIR.mkdir(parents=True, exist_ok=True)
TEACHER_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def log(message):
    print(message)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def log_json(title, obj):
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    print(title)
    print(text)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(title + "\n")
        f.write(text + "\n")


def wait_steps(steps=60):
    for _ in range(steps):
        omni.kit.app.get_app().update()


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


def get_hand():
    return find_prim(HAND_PATH_CANDIDATES, fallback_name="shadow_hand")


def get_cube():
    return find_prim(CUBE_PATH_CANDIDATES, fallback_name="Cube")


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


def set_translate(prim, pos):
    get_translate_op(prim).Set(Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2])))


def set_scale(prim, scale):
    get_scale_op(prim).Set(Gf.Vec3f(float(scale[0]), float(scale[1]), float(scale[2])))


def get_world_matrix(prim):
    matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)
    return [[float(matrix[i][j]) for j in range(4)] for i in range(4)]


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
            log("PhysX gravity enabled")
        except Exception as e:
            log(f"PhysX gravity attr skipped: {e}")

    zero_velocity(prim)


def apply_cube_geometry_and_physics(cube):
    if cube.IsA(UsdGeom.Cube):
        UsdGeom.Cube(cube).GetSizeAttr().Set(float(CUBE_USD_SIZE))

    set_scale(cube, CUBE_SCALE)
    UsdPhysics.CollisionAPI.Apply(cube)

    mass_api = UsdPhysics.MassAPI.Apply(cube)
    mass_api.GetMassAttr().Set(float(CUBE_MASS_KG))

    if PhysxSchema is not None:
        try:
            physx_rb = PhysxSchema.PhysxRigidBodyAPI.Apply(cube)
            set_attr_if_exists(physx_rb, "GetLinearDampingAttr", float(CUBE_LINEAR_DAMPING))
            set_attr_if_exists(physx_rb, "GetAngularDampingAttr", float(CUBE_ANGULAR_DAMPING))
        except Exception as e:
            log(f"cube damping skipped: {e}")

    enable_gravity_dynamic(cube)


def apply_physx_material_settings(material_prim):
    if PhysxSchema is None:
        return

    try:
        physx_mat = PhysxSchema.PhysxMaterialAPI.Apply(material_prim)
        set_attr_if_exists(physx_mat, "GetFrictionCombineModeAttr", "max")
        set_attr_if_exists(physx_mat, "GetRestitutionCombineModeAttr", "min")
        set_attr_if_exists(physx_mat, "GetImprovePatchFrictionAttr", True)
    except Exception as e:
        log(f"PhysX material settings skipped: {e}")


def make_physics_material(material_path, static_friction, dynamic_friction):
    material_prim = stage.DefinePrim(material_path, "Material")

    physics_mat = UsdPhysics.MaterialAPI.Apply(material_prim)
    physics_mat.GetStaticFrictionAttr().Set(float(static_friction))
    physics_mat.GetDynamicFrictionAttr().Set(float(dynamic_friction))
    physics_mat.GetRestitutionAttr().Set(0.0)

    apply_physx_material_settings(material_prim)

    return material_prim, UsdShade.Material(material_prim)


def apply_high_friction_to_cube(static_friction=CUBE_STATIC_FRICTION, dynamic_friction=CUBE_DYNAMIC_FRICTION):
    cube, cube_path = get_cube()

    material_path = "/World/high_friction_material"
    _, shade_mat = make_physics_material(material_path, static_friction, dynamic_friction)

    UsdShade.MaterialBindingAPI.Apply(cube).Bind(shade_mat)

    log(f"high friction applied to cube: {cube_path}, static={static_friction}, dynamic={dynamic_friction}")


def apply_high_friction_to_hand_links(
    static_friction=FINGER_STATIC_FRICTION,
    dynamic_friction=FINGER_DYNAMIC_FRICTION,
):
    material_path = "/World/high_friction_finger_material"
    _, shade_mat = make_physics_material(material_path, static_friction, dynamic_friction)

    tokens = [
        "ff", "mf", "rf", "lf", "th",
        "finger", "thumb", "distal", "middle", "proximal",
    ]
    count = 0

    for prim in stage.Traverse():
        path_text = str(prim.GetPath()).lower()
        name_text = prim.GetName().lower()
        if "shadow_hand" not in path_text and "robot0" not in path_text:
            continue
        if not any(token in path_text or token in name_text for token in tokens):
            continue

        try:
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(shade_mat)
            count += 1
        except Exception:
            pass

    log(f"high friction applied to hand links: {count}, static={static_friction}, dynamic={dynamic_friction}")


def remember_joint_targets(targets):
    CURRENT_JOINT_TARGETS.update({k: float(v) for k, v in targets.items()})


def set_joint_targets(targets, stiffness=500.0, damping=60.0, max_force=4000.0):
    count = 0

    for prim in stage.Traverse():
        name = prim.GetName()

        for key, target in targets.items():
            if key in name:
                for drive_name in DRIVE_NAMES:
                    drive = UsdPhysics.DriveAPI.Apply(prim, drive_name)
                    drive.GetTargetPositionAttr().Set(float(target))
                    drive.GetStiffnessAttr().Set(float(stiffness))
                    drive.GetDampingAttr().Set(float(damping))
                    drive.GetMaxForceAttr().Set(float(max_force))

                count += 1
                break

    remember_joint_targets(targets)
    log(f"set joint targets: {count}")


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

    log(f"opened hand target joints: {count}")


def lock_wrist_targets(stiffness=9000.0, damping=500.0, max_force=200000.0):
    count = 0

    for prim in stage.Traverse():
        name = prim.GetName()

        for key, target in WRIST_TARGETS.items():
            if key in name:
                for drive_name in DRIVE_NAMES:
                    drive = UsdPhysics.DriveAPI.Apply(prim, drive_name)
                    drive.GetTargetPositionAttr().Set(float(target))
                    drive.GetStiffnessAttr().Set(float(stiffness))
                    drive.GetDampingAttr().Set(float(damping))
                    drive.GetMaxForceAttr().Set(float(max_force))

                count += 1
                break

    log(f"wrist locked joints: {count}")


def pin_forearm_kinematic(value=True):
    forearm = find_by_name(FOREARM_NAME)
    rb = UsdPhysics.RigidBodyAPI.Apply(forearm)

    set_attr_if_exists(rb, "GetKinematicEnabledAttr", bool(value))
    set_attr_if_exists(rb, "GetVelocityAttr", Gf.Vec3f(0.0, 0.0, 0.0))
    set_attr_if_exists(rb, "GetAngularVelocityAttr", Gf.Vec3f(0.0, 0.0, 0.0))

    log(f"forearm kinematic fixed: {value}")


def apply_initial_state():
    global CUBE_SCALE, CUBE_USD_SIZE, TABLE_Z, CUBE_MASS_KG

    if not INITIAL_FILE.exists():
        raise RuntimeError(f"initial file not found: {INITIAL_FILE}. Run scripu1.py first.")

    data = json.loads(INITIAL_FILE.read_text(encoding="utf-8"))

    CUBE_SCALE = data.get("cube_scale", DEFAULT_CUBE_SCALE)
    CUBE_USD_SIZE = float(data.get("cube_usd_size", DEFAULT_CUBE_USD_SIZE))
    TABLE_Z = float(data.get("table_z", DEFAULT_TABLE_Z))
    saved_cube_mass_kg = float(data.get("cube_mass_kg", DEFAULT_CUBE_MASS_KG))
    CUBE_MASS_KG = float(OBJECT_MASS_OVERRIDE_KG) if OBJECT_MASS_OVERRIDE_KG is not None else saved_cube_mass_kg

    hand = stage.GetPrimAtPath(data["hand_path"])
    if not hand.IsValid():
        hand, _ = get_hand()

    cube = stage.GetPrimAtPath(data["cube_path"])
    if not cube.IsValid():
        cube, _ = get_cube()

    set_translate(hand, data["hand_translate"])
    set_translate(cube, data["cube_translate"])
    apply_cube_geometry_and_physics(cube)

    cube_pos = get_translate(cube)
    cube_height = CUBE_USD_SIZE * CUBE_SCALE[2]
    cube_world_bottom_z = cube_pos[2] - cube_height / 2.0

    log_json("applied saved current state", {
        "hand_translate": get_translate(hand),
        "cube_translate": cube_pos,
        "cube_scale": CUBE_SCALE,
        "cube_usd_size": CUBE_USD_SIZE,
        "cube_height": cube_height,
        "table_z": TABLE_Z,
        "cube_world_bottom_z": cube_world_bottom_z,
        "cube_bottom_above_table": cube_world_bottom_z - TABLE_Z,
        "cube_mass_kg": CUBE_MASS_KG,
        "saved_cube_mass_kg": saved_cube_mass_kg,
        "mass_override_kg": OBJECT_MASS_OVERRIDE_KG,
        "cube_static_friction": CUBE_STATIC_FRICTION,
        "cube_dynamic_friction": CUBE_DYNAMIC_FRICTION,
        "finger_static_friction": FINGER_STATIC_FRICTION,
        "finger_dynamic_friction": FINGER_DYNAMIC_FRICTION,
    })


def save_lift_start():
    hand, hand_path = get_hand()
    data = {"hand_path": hand_path, "hand_translate": get_translate(hand)}
    LIFT_START_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log_json("saved lift start", data)


def list_all_camera_prims():
    return [prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Camera)]


def list_all_camera_paths():
    return [str(prim.GetPath()) for prim in list_all_camera_prims()]


def print_all_cameras():
    cameras = list_all_camera_prims()
    print("all cameras:")
    for i, prim in enumerate(cameras):
        print(f"{i}: {prim.GetName()}  {prim.GetPath()}")
    return [str(prim.GetPath()) for prim in cameras]


def init_all_cameras(resolution=CAMERA_RESOLUTION):
    camera_paths = list_all_camera_paths()

    for path in camera_paths:
        if path not in _camera_cache:
            try:
                cam = Camera(prim_path=path, resolution=resolution)
                cam.initialize()
                _camera_cache[path] = cam
                log(f"camera initialized: {path}")
            except Exception as e:
                log(f"camera initialize skipped: {path} error={e}")

    wait_steps(10)
    return camera_paths


def sanitize_filename(text):
    text = text.replace("/", "_").replace("\\", "_").replace(":", "_")
    text = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", text)
    return text.strip("_")


def capture_camera_rgba(camera_path, resolution=CAMERA_RESOLUTION, retries=5):
    if camera_path not in _camera_cache:
        cam = Camera(prim_path=camera_path, resolution=resolution)
        cam.initialize()
        _camera_cache[camera_path] = cam
        wait_steps(20)

    cam = _camera_cache[camera_path]

    arr = None
    for attempt in range(retries):
        wait_steps(5)
        rgba = cam.get_rgba()
        arr = np.asarray(rgba)

        if arr.size > 0:
            break

        log(f"camera returned empty frame, retry {attempt + 1}/{retries}: {camera_path}")

    if arr is None or arr.size == 0:
        raise RuntimeError(f"camera returned empty frame after retries: {camera_path}")

    if arr.dtype != np.uint8:
        if arr.max() <= 1.0:
            arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        else:
            arr = np.clip(arr, 0, 255).astype(np.uint8)

    return arr


def save_all_camera_images(save_dir=CAMERA_SAVE_DIR, resolution=CAMERA_RESOLUTION):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_dir = Path(save_dir) / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "timestamp": timestamp,
        "resolution": list(resolution),
        "save_dir": str(run_dir),
        "cameras": [],
    }

    camera_paths = list_all_camera_paths()
    log(f"saving cameras: {len(camera_paths)}")

    for camera_path in camera_paths:
        prim = stage.GetPrimAtPath(camera_path)

        try:
            arr = capture_camera_rgba(camera_path, resolution=resolution)
        except Exception as e:
            log(f"camera save skipped: {camera_path} error={e}")
            metadata["cameras"].append({
                "name": prim.GetName(),
                "path": camera_path,
                "error": str(e),
                "skipped": True,
            })
            continue

        rgb = arr[:, :, :3] if arr.shape[-1] == 4 else arr

        safe_name = sanitize_filename(camera_path)
        jpg_path = run_dir / f"{safe_name}.jpg"
        npy_path = run_dir / f"{safe_name}.npy"

        Image.fromarray(rgb).save(jpg_path, format="JPEG", quality=90)
        np.save(npy_path, arr)

        item = {
            "name": prim.GetName(),
            "path": camera_path,
            "jpg_path": str(jpg_path),
            "npy_path": str(npy_path),
            "width": int(rgb.shape[1]),
            "height": int(rgb.shape[0]),
            "world_matrix": get_world_matrix(prim),
        }
        metadata["cameras"].append(item)
        log(f"saved camera: {camera_path}")

    metadata_path = run_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    log_json("saved all camera images", metadata)
    return metadata


def get_teacher_state():
    hand, hand_path = get_hand()
    cube, cube_path = get_cube()

    cube_pos = get_translate(cube)
    cube_height = CUBE_USD_SIZE * CUBE_SCALE[2]
    cube_world_bottom_z = cube_pos[2] - cube_height / 2.0

    return {
        "hand_path": hand_path,
        "cube_path": cube_path,
        "hand_translate": get_translate(hand),
        "cube_translate": cube_pos,
        "cube_scale": CUBE_SCALE,
        "cube_usd_size": CUBE_USD_SIZE,
        "cube_height": cube_height,
        "table_z": TABLE_Z,
        "cube_world_bottom_z": cube_world_bottom_z,
        "cube_bottom_above_table": cube_world_bottom_z - TABLE_Z,
        "current_joint_targets": dict(CURRENT_JOINT_TARGETS),
        "action_joints": ACTION_JOINTS,
    }


def save_teacher_camera_images(step_id):
    saved = {}

    for camera_path in list_all_camera_paths():
        prim = stage.GetPrimAtPath(camera_path)

        try:
            arr = capture_camera_rgba(camera_path, resolution=CAMERA_RESOLUTION)
        except Exception as e:
            log(f"teacher camera skipped: {camera_path} error={e}")
            saved[camera_path] = {
                "name": prim.GetName(),
                "path": camera_path,
                "error": str(e),
                "skipped": True,
            }
            continue

        rgb = arr[:, :, :3] if arr.shape[-1] == 4 else arr

        safe_name = sanitize_filename(camera_path)
        jpg_path = TEACHER_IMAGES_DIR / f"{step_id}_{safe_name}.jpg"
        Image.fromarray(rgb).save(jpg_path, format="JPEG", quality=90)

        saved[camera_path] = {
            "name": prim.GetName(),
            "path": camera_path,
            "jpg_path": str(jpg_path),
            "width": int(rgb.shape[1]),
            "height": int(rgb.shape[0]),
            "world_matrix": get_world_matrix(prim),
        }

    return saved


def record_teacher_step(script_name, phase, action=None, note="", save_images=True, success=None):
    step_id = time.strftime("%H%M%S") + "_" + script_name + "_" + phase
    step_id = sanitize_filename(step_id)

    item = {
        "run_id": TEACHER_RUN_ID,
        "step_id": step_id,
        "timestamp": time.time(),
        "script_name": script_name,
        "phase": phase,
        "instruction": "grasp the cube with ShadowHand and lift it",
        "note": note,
        "state": get_teacher_state(),
        "action": action or {},
        "success": success,
    }

    item["images"] = save_teacher_camera_images(step_id) if save_images else {}

    with TEACHER_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

    log_json("teacher step saved", {
        "step_id": step_id,
        "script_name": script_name,
        "phase": phase,
        "save_images": save_images,
        "teacher_jsonl": str(TEACHER_JSONL),
    })
    return item


apply_initial_state()
open_hand_targets()
apply_high_friction_to_cube(static_friction=CUBE_STATIC_FRICTION, dynamic_friction=CUBE_DYNAMIC_FRICTION)
apply_high_friction_to_hand_links(static_friction=FINGER_STATIC_FRICTION, dynamic_friction=FINGER_DYNAMIC_FRICTION)

cube, cube_path = get_cube()
enable_gravity_dynamic(cube)

init_all_cameras()
print_all_cameras()

record_teacher_step(
    script_name="scripu2",
    phase="common_setup_loaded",
    action={"type": "setup"},
    note="saved initial state restored and cameras initialized",
    save_images=True,
)

omni.usd.get_context().save_stage()
log("common code loaded: saved current hand/cube pose restored, hand open, all cameras ready")