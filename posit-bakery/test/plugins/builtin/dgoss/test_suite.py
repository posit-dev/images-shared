import json
import subprocess

import pytest

from posit_bakery.error import BakeryToolRuntimeErrorGroup
from posit_bakery.parallel import ShellResult
from posit_bakery.plugins.builtin.dgoss.errors import BakeryDGossError
from posit_bakery.plugins.builtin.dgoss.suite import DGossSuite
from test.helpers import remove_images

pytestmark = [
    pytest.mark.unit,
    pytest.mark.goss,
]


class TestDGossSuite:
    def test_init(self, get_config_obj):
        """Test that DGossSuite initializes with the correct attributes."""
        basic_config_obj = get_config_obj("basic")
        dgoss_suite = DGossSuite(basic_config_obj.base_path, basic_config_obj.targets)
        assert dgoss_suite.context == basic_config_obj.base_path
        assert dgoss_suite.image_targets == basic_config_obj.targets
        assert len(dgoss_suite.dgoss_commands) == 2

    @pytest.mark.image_build
    def test_run(self, get_tmpconfig):
        """Test that DGossSuite run executes the DGoss commands."""
        basic_tmpconfig = get_tmpconfig("basic")
        basic_tmpconfig.build_targets()

        dgoss_suite = DGossSuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        report_collection, errors = dgoss_suite.run()

        assert errors is None
        assert len(report_collection.test_failures) == 0
        assert len(report_collection.get("test-image")) == 2
        for target in dgoss_suite.image_targets:
            results_file = target.context.base_path / "results" / "dgoss" / target.image_name / f"{target.uid}.json"
            assert results_file.exists()
            with open(results_file) as f:
                json.load(f)

        remove_images(basic_tmpconfig)

    def test_run_parallel_mocked(self, get_tmpconfig, mocker):
        """Suite.run() processes successful executor results into reports + files."""
        cfg = get_tmpconfig("basic")
        suite = DGossSuite(cfg.base_path, cfg.targets)

        goss_json = json.dumps(
            {
                "summary": {
                    "test-count": 2,
                    "failed-count": 0,
                    "skipped-count": 0,
                    "summary-line": "Count: 2, Failed: 0, Skipped: 0",
                    "total-duration": 1234567,
                }
            }
        ).encode("utf-8")

        def fake_run(self, tasks, *, on_result=None):
            results = []
            for t in tasks:
                r = ShellResult(task=t, returncode=0, stdout=goss_json, stderr=b"", duration=1.0)
                results.append(r)
                if on_result is not None:
                    on_result(r)
            return results

        mocker.patch("posit_bakery.plugins.builtin.dgoss.suite.ParallelShellExecutor.run", fake_run)

        report_collection, errors = suite.run()

        assert errors is None
        assert len(report_collection.get("test-image")) == 2
        for target in suite.image_targets:
            results_file = cfg.base_path / "results" / "dgoss" / target.image_name / f"{target.uid}.json"
            assert results_file.exists()
            with open(results_file) as f:
                json.load(f)

    def test_jobs_sets_max_workers(self, get_config_obj):
        cfg = get_config_obj("basic")
        # jobs is clamped to the number of commands (2 targets in the basic config)
        assert DGossSuite(cfg.base_path, cfg.targets, jobs=1).max_workers == 1
        assert DGossSuite(cfg.base_path, cfg.targets, jobs=5).max_workers == 2

    def test_run_spawn_failure_records_errors(self, get_tmpconfig, mocker):
        cfg = get_tmpconfig("basic")
        suite = DGossSuite(cfg.base_path, cfg.targets)

        def fake_run(self, tasks, *, on_result=None):
            results = []
            for t in tasks:
                r = ShellResult(
                    task=t,
                    returncode=None,
                    stdout=b"",
                    stderr=b"",
                    duration=0.0,
                    exception=FileNotFoundError("dgoss not found"),
                )
                results.append(r)
                if on_result is not None:
                    on_result(r)
            return results

        mocker.patch("posit_bakery.plugins.builtin.dgoss.suite.ParallelShellExecutor.run", fake_run)

        report_collection, errors = suite.run()

        assert len(report_collection) == 0
        assert isinstance(errors, BakeryToolRuntimeErrorGroup)
        assert len(errors.exceptions) == 2
        assert all(isinstance(e, BakeryDGossError) for e in errors.exceptions)

    def test_run_timeout_records_error(self, get_tmpconfig, mocker):
        cfg = get_tmpconfig("basic")
        suite = DGossSuite(cfg.base_path, cfg.targets)

        def fake_run(self, tasks, *, on_result=None):
            results = []
            for t in tasks:
                r = ShellResult(
                    task=t,
                    returncode=-15,
                    stdout=b"",
                    stderr=b"",
                    duration=900.0,
                    exception=subprocess.TimeoutExpired(t.cmd, 900),
                    timed_out=True,
                )
                results.append(r)
                if on_result is not None:
                    on_result(r)
            return results

        mocker.patch("posit_bakery.plugins.builtin.dgoss.suite.ParallelShellExecutor.run", fake_run)

        report_collection, errors = suite.run()

        assert len(report_collection) == 0
        assert isinstance(errors, BakeryToolRuntimeErrorGroup)
        assert len(errors.exceptions) == 2
        assert all("timed out" in str(e).lower() for e in errors.exceptions)

    def test_run_passes_timeout_to_tasks(self, get_tmpconfig, mocker):
        captured = {}

        def fake_run(self, tasks, *, on_result=None):
            captured["tasks"] = tasks
            return []

        cfg = get_tmpconfig("basic")
        suite = DGossSuite(cfg.base_path, cfg.targets)
        mocker.patch("posit_bakery.plugins.builtin.dgoss.suite.ParallelShellExecutor.run", fake_run)
        suite.run()
        assert captured["tasks"]
        assert all(t.timeout == 900 for t in captured["tasks"])  # default 900 from GossOptions
