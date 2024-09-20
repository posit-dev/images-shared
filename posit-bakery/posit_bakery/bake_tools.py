import json
import os
import subprocess
from pathlib import Path
from typing import List, Dict

from posit_bakery.error import BakeryPlanError


def get_bake_plan(context: Path, target: List[str], bake_files: List[Path]) -> Dict[str, Dict]:
    cmd = ["docker", "buildx", "bake", "--print"]
    for bake_file in bake_files:
        if not bake_file.is_absolute():
            bake_file = context / bake_file
        if not bake_file.exists():
            raise FileNotFoundError(f"bake file {bake_file} does not exist")
        cmd.extend(["-f", bake_file])
    if target is not None:
        cmd.extend(target)
    run_env = os.environ.copy()
    p = subprocess.run(cmd, capture_output=True, env=run_env)
    if p.returncode != 0:
        raise BakeryPlanError(f"Failed to get bake plan: {p.stderr}")
    return json.loads(p.stdout.decode("utf-8"))
