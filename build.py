#!/usr/bin/env python3
"""Build from locally supplied assets without downloading or installing anything."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
if __name__ == "__main__":
    required = [ROOT / "assets/ROVER.ACT", ROOT / "assets/rooms/source/data.json"]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.is_file()]
    if missing:
        sys.exit("Missing local input: " + ", ".join(missing) + ". Run python3 tools/download_assets.py first; see README.md.")
    for script in ("tools/build_rooms.py", "tools/extract_rover_vectors.py",
                   "tools/extract_rover_timeline.py", "tools/export_rover_poses.py",
                   "plasma/org.bobhouse.desktop/tools/build_data.py"):
        subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)
