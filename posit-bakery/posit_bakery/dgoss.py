from pathlib import Path
from typing import Dict


def construct_dgoss_command(context: Path, target_spec: Dict):
    context_path = context / target_spec["context"]
    test_path = context_path / "test"
    cmd = [
        "docker",
        "run",
        "-t",
        "--init",
        "--rm",
        "--entrypoint=''",
        "--privileged",
        f"--mount=type=bind,source={test_path},destination=/test",
    ]
    cmd.extend(custom_options(target_name, context_path))
    for name, value in target_spec["args"].items():
        cmd.extend(["--env", f'{name}="{value}"'])
    cmd.append(target_spec["tags"][0])
    cmd.extend(["/test/run_tests.sh"])
    return cmd
