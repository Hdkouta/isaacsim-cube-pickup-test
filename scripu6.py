from pathlib import Path
import json

SAVE_ROOT = Path(r"C:\VScode\Yoshida_script\camera")

metadata = save_all_camera_images(
    save_dir=SAVE_ROOT,
    resolution=CAMERA_RESOLUTION,
)

print("all camera images saved")
print("saved root:", SAVE_ROOT)
print("saved directory:", SAVE_ROOT / metadata["timestamp"])
print(json.dumps(metadata, ensure_ascii=False, indent=2))

