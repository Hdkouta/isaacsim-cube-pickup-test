import csv
import json
import math
import os
import time
from pathlib import Path

import omni.kit.app
import omni.usd
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

try:
    from pxr import PhysxSchema
except Exception:
    PhysxSchema = None


OUTPUT_ROOT = Path(r"C:\VScode\Yoshida_script\data\scene_report")
ROOT = Path(r"C:\VScode\Yoshida_script")
RUN_CFG_DIR = ROOT / "run" / "cfg"
CONFIG_CANDIDATES = [
    RUN_CFG_DIR / "env.json",
    RUN_CFG_DIR / "action.json",
    RUN_CFG_DIR / "action_tpl.json",
    ROOT / "configs" / "action_env_config.json",
    ROOT / "configs" / "action_input.json",
    ROOT / "configs" / "action_input_template.json",
    Path(r"C:\robot_assets\shadow_hand_initial.json"),
]
EVAL_ROOT_CANDIDATES = [
    ROOT / "data" / "log" / "eval",
    ROOT / "pi0_action_eval",
]
IMPORTANT_NAME_TOKENS = [
    "shadow",
    "hand",
    "cube",
    "box",
    "object",
    "camera",
    "table",
    "ground",
    "plane",
]
DRIVE_NAMES = ["angular", "linear", "rotX", "rotY", "rotZ", "transX", "transY", "transZ"]


def as_float(value):
    if value is None:
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    return number


def vec_to_list(value):
    if value is None:
        return None
    try:
        return [as_float(v) for v in value]
    except Exception:
        return str(value)


def matrix_to_list(matrix):
    try:
        return [[as_float(matrix[i][j]) for j in range(4)] for i in range(4)]
    except Exception:
        return None


def attr_value(attr):
    try:
        if not attr or not attr.HasValue():
            return None
        value = attr.Get()
    except Exception:
        return None

    if isinstance(value, Sdf.Path):
        return str(value)
    if isinstance(value, (Gf.Vec2f, Gf.Vec2d, Gf.Vec3f, Gf.Vec3d, Gf.Vec4f, Gf.Vec4d)):
        return vec_to_list(value)
    if isinstance(value, (Gf.Matrix4d, Gf.Matrix4f)):
        return matrix_to_list(value)
    if isinstance(value, (list, tuple)):
        return [attr_value_like(v) for v in value]
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def attr_value_like(value):
    if isinstance(value, Sdf.Path):
        return str(value)
    if isinstance(value, (Gf.Vec2f, Gf.Vec2d, Gf.Vec3f, Gf.Vec3d, Gf.Vec4f, Gf.Vec4d)):
        return vec_to_list(value)
    if isinstance(value, (Gf.Matrix4d, Gf.Matrix4f)):
        return matrix_to_list(value)
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    return str(value)


def rel_targets(rel):
    try:
        return [str(path) for path in rel.GetTargets()]
    except Exception:
        return []


def prim_has_api(prim, api_cls):
    try:
        return prim.HasAPI(api_cls)
    except Exception:
        return False


def get_api_attr(api, getter_name):
    try:
        getter = getattr(api, getter_name)
        return attr_value(getter())
    except Exception:
        return None


def get_world_matrix(prim):
    try:
        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        return matrix
    except Exception:
        return None


def get_world_transform(prim):
    matrix = get_world_matrix(prim)
    if matrix is None:
        return {}
    try:
        translation = matrix.ExtractTranslation()
    except Exception:
        translation = None
    return {
        "translation": vec_to_list(translation),
        "matrix": matrix_to_list(matrix),
    }


def get_xform_ops(prim):
    try:
        xformable = UsdGeom.Xformable(prim)
        ops = []
        for op in xformable.GetOrderedXformOps():
            ops.append({
                "name": op.GetName(),
                "op_type": str(op.GetOpType()),
                "value": attr_value_like(op.Get()),
            })
        return ops
    except Exception:
        return []


def get_world_bbox(prim, bbox_cache):
    try:
        bound = bbox_cache.ComputeWorldBound(prim)
        box = bound.ComputeAlignedBox()
        mn = box.GetMin()
        mx = box.GetMax()
        size = [as_float(mx[i] - mn[i]) for i in range(3)]
        center = [as_float((mx[i] + mn[i]) * 0.5) for i in range(3)]
        return {
            "min": vec_to_list(mn),
            "max": vec_to_list(mx),
            "size": size,
            "center": center,
        }
    except Exception:
        return None


def get_bound_material(prim):
    try:
        material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
        if not material:
            return None
        material_prim = material.GetPrim()
        return {
            "path": str(material_prim.GetPath()),
            "physics": get_physics_material(material_prim),
        }
    except Exception:
        return None


def get_physics_material(prim):
    try:
        api = UsdPhysics.MaterialAPI(prim)
        return {
            "static_friction": get_api_attr(api, "GetStaticFrictionAttr"),
            "dynamic_friction": get_api_attr(api, "GetDynamicFrictionAttr"),
            "restitution": get_api_attr(api, "GetRestitutionAttr"),
            "density": get_api_attr(api, "GetDensityAttr"),
        }
    except Exception:
        return {}


def get_physics_info(prim):
    info = {
        "has_rigid_body": prim_has_api(prim, UsdPhysics.RigidBodyAPI),
        "has_collision": prim_has_api(prim, UsdPhysics.CollisionAPI),
        "has_mass": prim_has_api(prim, UsdPhysics.MassAPI),
    }

    try:
        mass_api = UsdPhysics.MassAPI(prim)
        info["mass"] = get_api_attr(mass_api, "GetMassAttr")
        info["density"] = get_api_attr(mass_api, "GetDensityAttr")
        info["center_of_mass"] = get_api_attr(mass_api, "GetCenterOfMassAttr")
        info["diagonal_inertia"] = get_api_attr(mass_api, "GetDiagonalInertiaAttr")
    except Exception:
        pass

    try:
        rb_api = UsdPhysics.RigidBodyAPI(prim)
        info["rigid_body_enabled"] = get_api_attr(rb_api, "GetRigidBodyEnabledAttr")
        info["velocity"] = get_api_attr(rb_api, "GetVelocityAttr")
        info["angular_velocity"] = get_api_attr(rb_api, "GetAngularVelocityAttr")
        info["kinematic_enabled"] = get_api_attr(rb_api, "GetKinematicEnabledAttr")
    except Exception:
        pass

    try:
        collision_api = UsdPhysics.CollisionAPI(prim)
        info["collision_enabled"] = get_api_attr(collision_api, "GetCollisionEnabledAttr")
    except Exception:
        pass

    if PhysxSchema is not None:
        try:
            physx_rb = PhysxSchema.PhysxRigidBodyAPI(prim)
            info["physx_linear_damping"] = get_api_attr(physx_rb, "GetLinearDampingAttr")
            info["physx_angular_damping"] = get_api_attr(physx_rb, "GetAngularDampingAttr")
            info["physx_disable_gravity"] = get_api_attr(physx_rb, "GetDisableGravityAttr")
            info["physx_max_depenetration_velocity"] = get_api_attr(physx_rb, "GetMaxDepenetrationVelocityAttr")
        except Exception:
            pass
        try:
            physx_collision = PhysxSchema.PhysxCollisionAPI(prim)
            info["physx_contact_offset"] = get_api_attr(physx_collision, "GetContactOffsetAttr")
            info["physx_rest_offset"] = get_api_attr(physx_collision, "GetRestOffsetAttr")
        except Exception:
            pass

    material = get_bound_material(prim)
    if material:
        info["bound_material"] = material

    return info


def get_camera_info(prim, bbox_cache):
    camera = UsdGeom.Camera(prim)
    info = get_prim_base_info(prim, bbox_cache)
    info.update({
        "projection": get_api_attr(camera, "GetProjectionAttr"),
        "focal_length": get_api_attr(camera, "GetFocalLengthAttr"),
        "horizontal_aperture": get_api_attr(camera, "GetHorizontalApertureAttr"),
        "vertical_aperture": get_api_attr(camera, "GetVerticalApertureAttr"),
        "clipping_range": get_api_attr(camera, "GetClippingRangeAttr"),
        "focus_distance": get_api_attr(camera, "GetFocusDistanceAttr"),
        "f_stop": get_api_attr(camera, "GetFStopAttr"),
    })
    return info


def get_drive_info(prim):
    drives = {}
    for drive_name in DRIVE_NAMES:
        try:
            api = UsdPhysics.DriveAPI.Get(prim, drive_name)
            if not api:
                continue
            values = {
                "target_position": get_api_attr(api, "GetTargetPositionAttr"),
                "target_velocity": get_api_attr(api, "GetTargetVelocityAttr"),
                "stiffness": get_api_attr(api, "GetStiffnessAttr"),
                "damping": get_api_attr(api, "GetDampingAttr"),
                "max_force": get_api_attr(api, "GetMaxForceAttr"),
                "type": get_api_attr(api, "GetTypeAttr"),
            }
            if any(value is not None for value in values.values()):
                drives[drive_name] = values
        except Exception:
            continue
    return drives


def get_joint_info(prim, bbox_cache):
    info = get_prim_base_info(prim, bbox_cache)
    try:
        joint = UsdPhysics.Joint(prim)
        info["body0"] = rel_targets(joint.GetBody0Rel())
        info["body1"] = rel_targets(joint.GetBody1Rel())
        info["local_pos0"] = get_api_attr(joint, "GetLocalPos0Attr")
        info["local_pos1"] = get_api_attr(joint, "GetLocalPos1Attr")
        info["local_rot0"] = get_api_attr(joint, "GetLocalRot0Attr")
        info["local_rot1"] = get_api_attr(joint, "GetLocalRot1Attr")
        info["break_force"] = get_api_attr(joint, "GetBreakForceAttr")
        info["break_torque"] = get_api_attr(joint, "GetBreakTorqueAttr")
    except Exception:
        pass

    type_name = prim.GetTypeName()
    if type_name == "RevoluteJoint":
        try:
            joint = UsdPhysics.RevoluteJoint(prim)
            info["axis"] = get_api_attr(joint, "GetAxisAttr")
            info["lower_limit"] = get_api_attr(joint, "GetLowerLimitAttr")
            info["upper_limit"] = get_api_attr(joint, "GetUpperLimitAttr")
        except Exception:
            pass
    elif type_name == "PrismaticJoint":
        try:
            joint = UsdPhysics.PrismaticJoint(prim)
            info["axis"] = get_api_attr(joint, "GetAxisAttr")
            info["lower_limit"] = get_api_attr(joint, "GetLowerLimitAttr")
            info["upper_limit"] = get_api_attr(joint, "GetUpperLimitAttr")
        except Exception:
            pass

    info["drives"] = get_drive_info(prim)
    return info


def get_prim_base_info(prim, bbox_cache):
    type_name = prim.GetTypeName()
    return {
        "path": str(prim.GetPath()),
        "name": prim.GetName(),
        "type": type_name,
        "active": prim.IsActive(),
        "valid": prim.IsValid(),
        "children_count": len(list(prim.GetChildren())),
        "world_transform": get_world_transform(prim),
        "local_xform_ops": get_xform_ops(prim),
        "world_bbox": get_world_bbox(prim, bbox_cache),
        "physics": get_physics_info(prim),
    }


def is_joint_prim(prim):
    type_name = str(prim.GetTypeName())
    return type_name.endswith("Joint") or "Joint" in type_name


def is_important_prim(prim):
    path_text = str(prim.GetPath()).lower()
    type_name = str(prim.GetTypeName()).lower()
    if any(token in path_text for token in IMPORTANT_NAME_TOKENS):
        return True
    if "camera" in type_name or "joint" in type_name:
        return True
    return prim_has_api(prim, UsdPhysics.RigidBodyAPI) or prim_has_api(prim, UsdPhysics.CollisionAPI)


def maybe_load_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as e:
        return {"error": str(e)}


def summarize_config_files():
    out = {}
    for path in CONFIG_CANDIDATES:
        out[str(path)] = {
            "exists": path.exists(),
            "content": maybe_load_json(path),
        }
    return out


def latest_eval_summary():
    summaries = []
    for root in EVAL_ROOT_CANDIDATES:
        if not root.exists():
            continue
        eval_files = sorted(root.glob("*/eval_steps.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        for eval_file in eval_files[:3]:
            item = {
                "eval_jsonl": str(eval_file),
                "modified_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(eval_file.stat().st_mtime)),
                "steps": [],
            }
            try:
                rows = []
                with eval_file.open("r", encoding="utf-8-sig") as f:
                    for line in f:
                        text = line.strip()
                        if text:
                            rows.append(json.loads(text))
                for row in rows[-5:]:
                    images = row.get("images") or {}
                    action = row.get("action") or {}
                    item["steps"].append({
                        "phase": row.get("phase"),
                        "step_id": row.get("step_id"),
                        "image_count": len(images) if isinstance(images, dict) else None,
                        "hand_delta": action.get("hand_delta"),
                        "cube_motion": action.get("cube_motion"),
                        "joint_count": action.get("joint_count"),
                        "image_paths": [
                            info.get("jpg_path") or info.get("copied_jpg_path")
                            for info in images.values()
                            if isinstance(info, dict) and (info.get("jpg_path") or info.get("copied_jpg_path"))
                        ][:8] if isinstance(images, dict) else [],
                    })
            except Exception as e:
                item["error"] = str(e)
            summaries.append(item)
    return summaries


def get_stage_metadata(stage):
    root_layer = stage.GetRootLayer()
    session_layer = stage.GetSessionLayer()
    try:
        meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage)
    except Exception:
        meters_per_unit = None
    try:
        up_axis = UsdGeom.GetStageUpAxis(stage)
    except Exception:
        up_axis = None
    return {
        "root_layer_identifier": root_layer.identifier if root_layer else None,
        "root_layer_real_path": root_layer.realPath if root_layer else None,
        "session_layer_identifier": session_layer.identifier if session_layer else None,
        "meters_per_unit": meters_per_unit,
        "up_axis": str(up_axis) if up_axis else None,
        "start_time_code": stage.GetStartTimeCode(),
        "end_time_code": stage.GetEndTimeCode(),
        "time_codes_per_second": stage.GetTimeCodesPerSecond(),
        "frames_per_second": stage.GetFramesPerSecond(),
    }


def collect_scene_report():
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open in Isaac Sim")

    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        useExtentsHint=True,
    )

    prim_rows = []
    important_prims = []
    cameras = []
    joints = []
    rigid_bodies = []
    collisions = []
    cube_candidates = []
    hand_candidates = []
    material_prims = []
    physics_scenes = []

    all_prims = list(stage.Traverse())
    for prim in all_prims:
        path = str(prim.GetPath())
        name = prim.GetName()
        type_name = prim.GetTypeName()
        row = {
            "path": path,
            "name": name,
            "type": type_name,
            "active": prim.IsActive(),
            "children_count": len(list(prim.GetChildren())),
            "has_rigid_body": prim_has_api(prim, UsdPhysics.RigidBodyAPI),
            "has_collision": prim_has_api(prim, UsdPhysics.CollisionAPI),
            "has_mass": prim_has_api(prim, UsdPhysics.MassAPI),
            "is_camera": prim.IsA(UsdGeom.Camera),
            "is_joint": is_joint_prim(prim),
        }
        bbox = get_world_bbox(prim, bbox_cache)
        if bbox:
            row["bbox_center"] = bbox.get("center")
            row["bbox_size"] = bbox.get("size")
        prim_rows.append(row)

        lower_path = path.lower()
        if "cube" in lower_path or "box" in lower_path or "object" in lower_path:
            cube_candidates.append(get_prim_base_info(prim, bbox_cache))
        if "shadow" in lower_path or "hand" in lower_path:
            hand_candidates.append(get_prim_base_info(prim, bbox_cache))
        if prim.IsA(UsdGeom.Camera):
            cameras.append(get_camera_info(prim, bbox_cache))
        if is_joint_prim(prim):
            joints.append(get_joint_info(prim, bbox_cache))
        if prim_has_api(prim, UsdPhysics.RigidBodyAPI):
            rigid_bodies.append(get_prim_base_info(prim, bbox_cache))
        if prim_has_api(prim, UsdPhysics.CollisionAPI):
            collisions.append(get_prim_base_info(prim, bbox_cache))
        if type_name == "Material":
            material_prims.append({
                "path": path,
                "name": name,
                "physics": get_physics_material(prim),
            })
        if type_name == "PhysicsScene":
            physics_scenes.append(get_prim_base_info(prim, bbox_cache))
        if is_important_prim(prim):
            important_prims.append(get_prim_base_info(prim, bbox_cache))

    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stage": get_stage_metadata(stage),
        "counts": {
            "total_prims": len(all_prims),
            "important_prims": len(important_prims),
            "cameras": len(cameras),
            "joints": len(joints),
            "rigid_bodies": len(rigid_bodies),
            "collisions": len(collisions),
            "cube_candidates": len(cube_candidates),
            "hand_candidates": len(hand_candidates),
            "materials": len(material_prims),
            "physics_scenes": len(physics_scenes),
        },
        "cube_candidates": cube_candidates,
        "hand_candidates": hand_candidates[:200],
        "cameras": cameras,
        "joints": joints,
        "rigid_bodies": rigid_bodies,
        "collisions": collisions[:300],
        "materials": material_prims,
        "physics_scenes": physics_scenes,
        "important_prims": important_prims[:500],
        "config_files": summarize_config_files(),
        "latest_eval_logs": latest_eval_summary(),
        "prim_rows": prim_rows,
    }


def write_prim_csv(path, prim_rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "path",
        "name",
        "type",
        "active",
        "children_count",
        "has_rigid_body",
        "has_collision",
        "has_mass",
        "is_camera",
        "is_joint",
        "bbox_center",
        "bbox_size",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in prim_rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def write_summary_txt(path, report):
    lines = []
    lines.append("Isaac Sim scene environment report")
    lines.append(f"created_at: {report.get('created_at')}")
    lines.append("")
    lines.append("[stage]")
    stage = report.get("stage") or {}
    for key in ["root_layer_identifier", "root_layer_real_path", "meters_per_unit", "up_axis"]:
        lines.append(f"{key}: {stage.get(key)}")
    lines.append("")
    lines.append("[counts]")
    for key, value in (report.get("counts") or {}).items():
        lines.append(f"{key}: {value}")

    lines.append("")
    lines.append("[cube candidates]")
    for item in report.get("cube_candidates", [])[:10]:
        physics = item.get("physics") or {}
        bbox = item.get("world_bbox") or {}
        lines.append(
            f"{item.get('path')} type={item.get('type')} "
            f"pos={((item.get('world_transform') or {}).get('translation'))} "
            f"bbox_size={bbox.get('size')} mass={physics.get('mass')}"
        )

    lines.append("")
    lines.append("[cameras]")
    for item in report.get("cameras", []):
        transform = item.get("world_transform") or {}
        lines.append(
            f"{item.get('path')} pos={transform.get('translation')} "
            f"focal_length={item.get('focal_length')} clipping={item.get('clipping_range')}"
        )

    lines.append("")
    lines.append("[latest eval logs]")
    for item in report.get("latest_eval_logs", [])[:3]:
        lines.append(f"{item.get('eval_jsonl')} modified={item.get('modified_time')}")
        for step in item.get("steps", [])[-3:]:
            lines.append(
                f"  phase={step.get('phase')} image_count={step.get('image_count')} "
                f"hand_delta={step.get('hand_delta')} cube_motion={step.get('cube_motion')}"
            )

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    run_id = time.strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    for _ in range(3):
        omni.kit.app.get_app().update()

    report = collect_scene_report()
    prim_rows = report.pop("prim_rows")

    report_path = out_dir / "scene_environment_report.json"
    prim_csv_path = out_dir / "prim_summary.csv"
    summary_path = out_dir / "summary.txt"

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_prim_csv(prim_csv_path, prim_rows)
    write_summary_txt(summary_path, report)

    print("scene environment report written")
    print(json.dumps({
        "run_id": run_id,
        "out_dir": str(out_dir),
        "report_json": str(report_path),
        "prim_csv": str(prim_csv_path),
        "summary_txt": str(summary_path),
        "counts": report.get("counts"),
        "camera_paths": [item.get("path") for item in report.get("cameras", [])],
        "cube_candidates": [item.get("path") for item in report.get("cube_candidates", [])[:10]],
    }, ensure_ascii=False, indent=2))


main()
