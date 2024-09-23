import re
from pathlib import Path
from typing import Dict, List


class DGossManager:
    def __init__(
            self,
            context: Path,
            plan: Dict[str, Dict],
            skip: List[str],
            runtime_options: List[str],
    ):
        self.context = context
        self.plan = plan
        self.skip_re = [re.compile(s) for s in skip]
        self.runtime_options = runtime_options

    def exec(self):
        for target_name, target_spec in self.plan["target"].items():
            if target_name in SKIP:
                continue
            self.run_dgoss(target_name, target_spec)


    def construct_dgoss_command(self):
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
