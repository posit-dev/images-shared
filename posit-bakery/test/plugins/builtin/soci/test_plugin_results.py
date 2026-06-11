"""Tests for SociPlugin.results()."""

from unittest.mock import MagicMock

import pytest
import typer

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.soci import SociPlugin
from posit_bakery.plugins.builtin.soci.soci import SociConvertWorkflowResult
from posit_bakery.plugins.protocol import ToolCallResult

pytestmark = [pytest.mark.unit]


def _result(exit_code: int, workflow_success: bool, target_uid: str = "t") -> ToolCallResult:
    target = MagicMock(spec=ImageTarget)
    target.uid = target_uid
    target.__str__ = lambda self: f"ImageTarget({target_uid})"
    return ToolCallResult(
        exit_code=exit_code,
        tool_name="soci",
        target=target,
        stdout="",
        stderr="failure" if exit_code else "",
        artifacts={
            "workflow_result": SociConvertWorkflowResult(
                success=workflow_success,
                destination_ref="ref-soci",
                resolved_namespace="default",
                error=None if workflow_success else "failure",
            )
        },
    )


def test_all_success_does_not_raise():
    SociPlugin().results([_result(0, True)])


def test_any_failure_raises_typer_exit():
    with pytest.raises(typer.Exit) as exc:
        SociPlugin().results([_result(0, True), _result(1, False, "u")])
    assert exc.value.exit_code == 1


def test_skipped_results_do_not_raise():
    target = MagicMock(spec=ImageTarget)
    target.uid = "s"
    target.__str__ = lambda self: "ImageTarget(s)"
    skipped = ToolCallResult(
        exit_code=0,
        tool_name="soci",
        target=target,
        stdout="",
        stderr="",
        artifacts={"skipped": True, "reason": "soci.enabled is false"},
    )
    SociPlugin().results([skipped])
