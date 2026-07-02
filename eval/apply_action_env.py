import json
import math
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
OUTPUT_ROOT = Path(r"C:\VScode\Yoshida_script\pi0_action_eval")
CONFIG_FILE = Path(r"C:\VScode\Yoshida_script\configs\action_env_config.json")
DEFAULT_ACTION_FILE = Path(r"C:\VScode\Yoshida_script\configs\action_input.json")
DEFAULT_ACTION_TEMPLATE_FILE = Path(r"C:\VScode\Yoshida_script\configs\action_input_template.json")

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
DRIVE_NAMES = ["angular", "rotX", "rotY", "rotZ"]
FINGER_KEYS = ["FFJ", "MFJ", "RFJ", "LFJ", "THJ"]
WRIST_TARGETS = {"WRJ1": 0.0, "WRJ2": 0.0}

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

DEFAULT_CONFIG = {
    "reset_from_initial": True,
    "open_hand_on_setup": True,
    "lock_wrist_on_setup": True,
    "apply_action_if_file_exists": True,
    "action_file": str(DEFAULT_ACTION_FILE),
    "action_template_file": str(DEFAULT_ACTION_TEMPLATE_FILE),
    "save_images": True,
    "save_stage_after_setup": False,
    "camera_resolution": [640, 480],
    "object_mass_kg": 0.0025,
    "cube_static_friction": 6.0,
    "cube_dynamic_friction": 5.0,
    "finger_static_friction": 5.0,
    "finger_dynamic_friction": 4.0,
    "cube_linear_damping": 0.20,
    "cube_angular_damping": 0.35,
    "open_hand_stiffness": 150.0,
    "open_hand_damping": 20.0,
    "open_hand_max_force": 800.0,
    "joint_stiffness": 260.0,
    "joint_damping": 150.0,
    "joint_max_force": 1600.0,
    "wrist_stiffness": 12000.0,
    "wrist_damping": 700.0,
    "wrist_max_force": 250000.0,
    "hand_delta_steps": 12,
    "wait_after_hand_delta_steps": 20,
    "wait_after_joint_steps": 60,
    "wait_after_setup_steps": 20,
    "joint_target_min_deg": -20.0,
    "joint_target_max_deg": 80.0,
    "max_abs_hand_delta_m": 0.03,
}

stage = omni.usd.get_context().get_stage()
_camera_cache = {}
CURRENT_JOINT_TARGETS = {}
RUN_ID = time.strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
RUN_DIR = OUTPUT_ROOT / RUN_ID
IMAGE_DIR = RUN_DIR / "images"
EVAL_JSONL = RUN_DIR / "eval_steps.jsonl"
RUN_LOG = RUN_DIR / "run.log"


def sanitize_filename(text):
    text = str(text).replace("/", "_").replace("\\", "_").replace(":", "_")
    text = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", text)
    return text.strip("_") or "unnamed"


def log(message):
    print(message)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def log_json(title, obj):
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    print(title)
    print(text)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(title + "\n")
        f.write(text + "\n")


def wait_steps(steps=60):
    for _ in range(int(steps)):
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


def get_scale(prim):
    value = get_scale_op(prim).Get()
    if value is None:
        return [1.0, 1.0, 1.0]
    return [float(value[0]), float(value[1]), float(value[2])]


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
        except Exception as e:
            log(f"PhysX gravity attr skipped: {e}")

    zero_velocity(prim)


def apply_cube_geometry_and_physics(cube, initial_data, config):
    cube_scale = initial_data.get("cube_scale", get_scale(cube))
    cube_usd_size = float(initial_data.get("cube_usd_size", 1.0))

    if cube.IsA(UsdGeom.Cube):
        UsdGeom.Cube(cube).GetSizeAttr().Set(cube_usd_size)

    set_scale(cube, cube_scale)
    UsdPhysics.CollisionAPI.Apply(cube)

    mass_api = UsdPhysics.MassAPI.Apply(cube)
    mass_api.GetMassAttr().Set(float(config["object_mass_kg"]))

    if PhysxSchema is not None:
        try:
            physx_rb = PhysxSchema.PhysxRigidBodyAPI.Apply(cube)
            set_attr_if_exists(physx_rb, "GetLinearDampingAttr", float(config["cube_linear_damping"]))
            set_attr_if_exists(physx_rb, "GetAngularDampingAttr", float(config["cube_angular_damping"]))
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


def apply_high_friction_to_cube(config):
    cube, cube_path = get_cube()
    _, shade_mat = make_physics_material(
        "/World/pi0_eval_high_friction_cube_material",
        config["cube_static_friction"],
        config["cube_dynamic_friction"],
    )
    UsdShade.MaterialBindingAPI.Apply(cube).Bind(shade_mat)
    log(f"high friction applied to cube: {cube_path}")


def apply_high_friction_to_hand_links(config):
    _, shade_mat = make_physics_material(
        "/World/pi0_eval_high_friction_finger_material",
        config["finger_static_friction"],
        config["finger_dynamic_friction"],
    )

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

    log(f"high friction applied to hand links: {count}")


def remember_joint_targets(targets):
    CURRENT_JOINT_TARGETS.update({k: float(v) for k, v in targets.items()})


def set_joint_targets(targets, stiffness, damping, max_force):
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
    return count


def open_hand_targets(config):
    targets = {joint: 0.0 for joint in ACTION_JOINTS}
    count = 0

    for prim in stage.Traverse():
        name = prim.GetName()
        if any(key in name for key in FINGER_KEYS):
            for drive_name in DRIVE_NAMES:
                drive = UsdPhysics.DriveAPI.Apply(prim, drive_name)
                drive.GetTargetPositionAttr().Set(0.0)
                drive.GetStiffnessAttr().Set(float(config["open_hand_stiffness"]))
                drive.GetDampingAttr().Set(float(config["open_hand_damping"]))
                drive.GetMaxForceAttr().Set(float(config["open_hand_max_force"]))
            count += 1

    remember_joint_targets(targets)
    log(f"opened hand target joints: {count}")


def lock_wrist_targets(config):
    count = 0

    for prim in stage.Traverse():
        name = prim.GetName()

        for key, target in WRIST_TARGETS.items():
            if key in name:
                for drive_name in DRIVE_NAMES:
                    drive = UsdPhysics.DriveAPI.Apply(prim, drive_name)
                    drive.GetTargetPositionAttr().Set(float(target))
                    drive.GetStiffnessAttr().Set(float(config["wrist_stiffness"]))
                    drive.GetDampingAttr().Set(float(config["wrist_damping"]))
                    drive.GetMaxForceAttr().Set(float(config["wrist_max_force"]))
                count += 1
                break

    log(f"wrist locked joints: {count}")


def list_all_camera_prims():
    return [prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Camera)]


def list_all_camera_paths():
    return [str(prim.GetPath()) for prim in list_all_camera_prims()]


def init_all_cameras(resolution):
    camera_paths = list_all_camera_paths()

    for path in camera_paths:
        if path not in _camera_cache:
            try:
                cam = Camera(prim_path=path, resolution=tuple(resolution))
                cam.initialize()
                _camera_cache[path] = cam
                log(f"camera initialized: {path}")
            except Exception as e:
                log(f"camera initialize skipped: {path} error={e}")

    wait_steps(10)
    return camera_paths


def capture_camera_rgba(camera_path, resolution, retries=5):
    if camera_path not in _camera_cache:
        cam = Camera(prim_path=camera_path, resolution=tuple(resolution))
        cam.initialize()
        _camera_cache[camera_path] = cam
        wait_steps(20)

    cam = _camera_cache[camera_path]
    arr = None

    for attempt in range(retries):
        wait_steps(5)
        arr = np.asarray(cam.get_rgba())
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


def save_observation_images(step_id, config):
    if not config["save_images"]:
        return {}

    saved = {}
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    for camera_path in list_all_camera_paths():
        prim = stage.GetPrimAtPath(camera_path)
        try:
            arr = capture_camera_rgba(camera_path, config["camera_resolution"])
        except Exception as e:
            log(f"camera skipped: {camera_path} error={e}")
            saved[camera_path] = {
                "name": prim.GetName(),
                "path": camera_path,
                "error": str(e),
                "skipped": True,
            }
            continue

        rgb = arr[:, :, :3] if arr.shape[-1] == 4 else arr
        safe_name = sanitize_filename(camera_path)
        jpg_path = IMAGE_DIR / f"{step_id}_{safe_name}.jpg"
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


def get_eval_state():
    hand, hand_path = get_hand()
    cube, cube_path = get_cube()
    cube_pos = get_translate(cube)
    cube_scale = get_scale(cube)
    cube_usd_size = 1.0
    if cube.IsA(UsdGeom.Cube):
        value = UsdGeom.Cube(cube).GetSizeAttr().Get()
        if value is not None:
            cube_usd_size = float(value)
    cube_height = cube_usd_size * cube_scale[2]

    return {
        "hand_path": hand_path,
        "cube_path": cube_path,
        "hand_translate": get_translate(hand),
        "cube_translate": cube_pos,
        "cube_scale": cube_scale,
        "cube_usd_size": cube_usd_size,
        "cube_height": cube_height,
        "cube_world_bottom_z": cube_pos[2] - cube_height / 2.0,
        "current_joint_targets": dict(CURRENT_JOINT_TARGETS),
        "action_schema": ACTION_SCHEMA_NAME,
        "action_joints": ACTION_JOINTS,
        "camera_paths": list_all_camera_paths(),
    }


def record_eval_step(phase, action=None, note="", config=None, success=None):
    if config is None:
        config = DEFAULT_CONFIG

    step_id = time.strftime("%H%M%S") + "_pi0_env_" + phase
    step_id = sanitize_filename(step_id)
    item = {
        "run_id": RUN_ID,
        "step_id": step_id,
        "timestamp": time.time(),
        "script_name": "apply_shadowhand_action_env",
        "phase": phase,
        "instruction": TASK_INSTRUCTION,
        "note": note,
        "state": get_eval_state(),
        "action": action or {},
        "success": success,
    }
    item["images"] = save_observation_images(step_id, config)

    with EVAL_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

    log_json("eval step saved", {
        "step_id": step_id,
        "phase": phase,
        "image_count": len(item["images"]),
        "eval_jsonl": str(EVAL_JSONL),
    })
    return item


def load_config():
    config = dict(DEFAULT_CONFIG)

    if CONFIG_FILE.exists():
        loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
        if not isinstance(loaded, dict):
            raise RuntimeError(f"config must be a JSON object: {CONFIG_FILE}")
        config.update(loaded)
    else:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    resolution = config.get("camera_resolution")
    if not isinstance(resolution, list) or len(resolution) != 2:
        raise RuntimeError("camera_resolution must be [width, height]")
    config["camera_resolution"] = [int(resolution[0]), int(resolution[1])]
    return config


def load_initial_data():
    if not INITIAL_FILE.exists():
        raise RuntimeError(f"initial file not found: {INITIAL_FILE}. Run scripu1.py first.")
    data = json.loads(INITIAL_FILE.read_text(encoding="utf-8-sig"))
    required = ["hand_translate", "cube_translate"]
    missing = [key for key in required if key not in data]
    if missing:
        raise RuntimeError(f"initial file missing keys {missing}: {INITIAL_FILE}")
    return data


def restore_initial_state(config):
    data = load_initial_data()

    hand = stage.GetPrimAtPath(data.get("hand_path", ""))
    if not hand.IsValid():
        hand, _ = get_hand()

    cube = stage.GetPrimAtPath(data.get("cube_path", ""))
    if not cube.IsValid():
        cube, _ = get_cube()

    set_translate(hand, data["hand_translate"])
    set_translate(cube, data["cube_translate"])
    apply_cube_geometry_and_physics(cube, data, config)
    zero_velocity(cube)
    log_json("initial state restored", {
        "hand_translate": get_translate(hand),
        "cube_translate": get_translate(cube),
        "cube_scale": get_scale(cube),
        "object_mass_kg": config["object_mass_kg"],
    })


def setup_environment(config):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    if config["reset_from_initial"]:
        restore_initial_state(config)
    else:
        cube, _ = get_cube()
        enable_gravity_dynamic(cube)

    apply_high_friction_to_cube(config)
    apply_high_friction_to_hand_links(config)

    if config["open_hand_on_setup"]:
        open_hand_targets(config)

    if config["lock_wrist_on_setup"]:
        lock_wrist_targets(config)

    init_all_cameras(config["camera_resolution"])
    wait_steps(config["wait_after_setup_steps"])

    if config["save_stage_after_setup"]:
        omni.usd.get_context().save_stage()


def write_schema_and_templates(config):
    schema = {
        "schema_name": ACTION_SCHEMA_NAME,
        "instruction": TASK_INSTRUCTION,
        "action_dim": len(ACTION_JOINTS) + len(HAND_DELTA_NAMES),
        "dimensions": [],
        "units": {
            "joint_targets": "degrees",
            "hand_delta": "meters",
        },
    }

    for index, joint in enumerate(ACTION_JOINTS):
        schema["dimensions"].append({
            "index": index,
            "name": joint,
            "kind": "shadowhand_joint_target",
            "unit": "degrees",
        })

    for index, name in enumerate(HAND_DELTA_NAMES, start=len(ACTION_JOINTS)):
        schema["dimensions"].append({
            "index": index,
            "name": name,
            "kind": "hand_base_delta",
            "unit": "meters",
        })

    template = {
        "schema_name": ACTION_SCHEMA_NAME,
        "instruction": TASK_INSTRUCTION,
        "vector": [0.0] * (len(ACTION_JOINTS) + len(HAND_DELTA_NAMES)),
        "joint_targets": {joint: 0.0 for joint in ACTION_JOINTS},
        "hand_delta": [0.0, 0.0, 0.0],
    }

    (RUN_DIR / "schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "action_template.json").write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "config_used.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    action_template_file = Path(config["action_template_file"])
    action_template_file.parent.mkdir(parents=True, exist_ok=True)
    if not action_template_file.exists():
        action_template_file.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"action template written: {action_template_file}")


def ensure_finite_number(value, name):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise RuntimeError(f"{name} must be a number, got {value!r}")

    if not math.isfinite(number):
        raise RuntimeError(f"{name} must be finite, got {value!r}")
    return number


def normalize_action_payload(payload, config):
    if not isinstance(payload, dict):
        raise RuntimeError("action payload must be a JSON object")

    if "target_action" in payload and isinstance(payload["target_action"], dict):
        payload = payload["target_action"]

    vector = payload.get("vector")
    if vector is not None:
        if not isinstance(vector, list) or len(vector) != len(ACTION_JOINTS) + len(HAND_DELTA_NAMES):
            raise RuntimeError("vector must be a 20 element list")

        values = [
            ensure_finite_number(value, f"vector[{index}]")
            for index, value in enumerate(vector)
        ]
        joint_targets = {joint: values[index] for index, joint in enumerate(ACTION_JOINTS)}
        hand_delta = values[len(ACTION_JOINTS):]
    else:
        joint_targets_src = payload.get("joint_targets")
        hand_delta_src = payload.get("hand_delta", [0.0, 0.0, 0.0])

        if not isinstance(joint_targets_src, dict):
            raise RuntimeError("action payload must contain either vector or joint_targets")
        if not isinstance(hand_delta_src, list) or len(hand_delta_src) != 3:
            raise RuntimeError("hand_delta must be a 3 element list")

        joint_targets = {}
        for joint in ACTION_JOINTS:
            joint_targets[joint] = ensure_finite_number(
                joint_targets_src.get(joint, CURRENT_JOINT_TARGETS.get(joint, 0.0)),
                f"joint_targets.{joint}",
            )

        hand_delta = [
            ensure_finite_number(value, f"hand_delta[{index}]")
            for index, value in enumerate(hand_delta_src)
        ]
        vector = [joint_targets[joint] for joint in ACTION_JOINTS] + hand_delta

    min_deg = float(config["joint_target_min_deg"])
    max_deg = float(config["joint_target_max_deg"])
    out_of_range = {
        joint: value
        for joint, value in joint_targets.items()
        if value < min_deg or value > max_deg
    }
    if out_of_range:
        raise RuntimeError(f"joint targets outside [{min_deg}, {max_deg}] deg: {out_of_range}")

    max_abs_hand_delta = float(config["max_abs_hand_delta_m"])
    if any(abs(value) > max_abs_hand_delta for value in hand_delta):
        raise RuntimeError(f"hand_delta exceeds +/-{max_abs_hand_delta} m: {hand_delta}")

    return {
        "schema_name": payload.get("schema_name", ACTION_SCHEMA_NAME),
        "vector": vector,
        "joint_targets": joint_targets,
        "hand_delta": hand_delta,
        "source_payload": payload,
    }


def load_action_file(config):
    action_file = Path(config["action_file"])
    if not action_file.exists():
        return None, action_file

    payload = json.loads(action_file.read_text(encoding="utf-8-sig"))
    return normalize_action_payload(payload, config), action_file


def move_hand_by_delta(hand_delta, config):
    if all(abs(value) < 1e-12 for value in hand_delta):
        return get_translate(get_hand()[0])

    hand, _ = get_hand()
    start = get_translate(hand)
    steps = max(1, int(config["hand_delta_steps"]))
    target = [
        start[0] + float(hand_delta[0]),
        start[1] + float(hand_delta[1]),
        start[2] + float(hand_delta[2]),
    ]

    for i in range(steps):
        alpha = float(i + 1) / float(steps)
        pos = [
            start[0] + (target[0] - start[0]) * alpha,
            start[1] + (target[1] - start[1]) * alpha,
            start[2] + (target[2] - start[2]) * alpha,
        ]
        set_translate(hand, pos)
        wait_steps(2)

    wait_steps(config["wait_after_hand_delta_steps"])
    return target


def apply_shadowhand_action(action, config):
    before_state = get_eval_state()

    target_pos = move_hand_by_delta(action["hand_delta"], config)
    joint_count = set_joint_targets(
        action["joint_targets"],
        stiffness=float(config["joint_stiffness"]),
        damping=float(config["joint_damping"]),
        max_force=float(config["joint_max_force"]),
    )
    wait_steps(config["wait_after_joint_steps"])

    after_state = get_eval_state()
    cube_before = before_state["cube_translate"]
    cube_after = after_state["cube_translate"]
    cube_motion = [
        cube_after[0] - cube_before[0],
        cube_after[1] - cube_before[1],
        cube_after[2] - cube_before[2],
    ]

    return {
        "type": "shadowhand_20d_action",
        "schema_name": ACTION_SCHEMA_NAME,
        "joint_count": joint_count,
        "target_hand_pos": target_pos,
        "cube_motion": cube_motion,
        "vector": action["vector"],
        "joint_targets": action["joint_targets"],
        "hand_delta": action["hand_delta"],
    }


config = load_config()
RUN_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

log_json("pi0/shadowhand action env start", {
    "run_id": RUN_ID,
    "run_dir": str(RUN_DIR),
    "config_file": str(CONFIG_FILE),
    "action_file": config["action_file"],
    "action_template_file": config["action_template_file"],
})

write_schema_and_templates(config)
setup_environment(config)

record_eval_step(
    phase="env_ready",
    action={"type": "setup", "schema_name": ACTION_SCHEMA_NAME},
    note="environment reset and ready for image-state -> ShadowHand action evaluation",
    config=config,
)

action_file_exists = Path(config["action_file"]).exists()
action = None
action_file = Path(config["action_file"])
if config["apply_action_if_file_exists"] and action_file_exists:
    action, action_file = load_action_file(config)

if action is None:
    log_json("no action file applied", {
        "expected_action_file": str(action_file),
        "action_template_file": config["action_template_file"],
        "apply_action_if_file_exists": config["apply_action_if_file_exists"],
        "message": "Copy the template to the action file path or write a pi0 20D action there, then run this script again.",
    })
else:
    record_eval_step(
        phase="before_action",
        action={
            "type": "before_action",
            "action_file": str(action_file),
            "schema_name": action["schema_name"],
        },
        note="before applying pi0/ShadowHand action",
        config=config,
    )

    applied_action = apply_shadowhand_action(action, config)
    record_eval_step(
        phase="after_action",
        action=applied_action,
        note="after applying pi0/ShadowHand action",
        config=config,
    )

    log_json("shadowhand action applied", {
        "action_file": str(action_file),
        "hand_delta": action["hand_delta"],
        "cube_motion": applied_action["cube_motion"],
        "run_dir": str(RUN_DIR),
    })
