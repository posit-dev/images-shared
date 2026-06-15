import functools
import inspect
import json
import logging
import tempfile
from pathlib import Path
from typing import Annotated, Optional, Any, TYPE_CHECKING

import typer
from pydantic import ValidationError

from posit_bakery.config.dependencies import (
    get_dependency_versions_class,
    get_dependency_constraint_class,
    DependencyConstraint,
    DependencyVersions,
)
from posit_bakery.config.image.dev_version.spec import DevBuildSpec
from posit_bakery.log import init_logging, stderr_console
from posit_bakery.settings import SETTINGS

# Runtime import would cycle (config.config indirectly imports the CLI package),
# and these are only needed for type hints.
if TYPE_CHECKING:
    from posit_bakery.config.config import BakeryConfig, BakerySettings

log = logging.getLogger(__name__)


def exit_if_no_targets(config: "BakeryConfig", settings: "BakerySettings") -> None:
    """Abort the command when the active filters resolved to zero image targets.

    A ``build`` or ``dgoss run`` that matches no targets is almost always a
    mistake — a typo'd or non-existent ``--image-version``, an over-narrow
    combination of filters, or a ``--dev-versions``/``--matrix-versions``
    selection that excludes everything. Exiting 0 in that case let broken CI
    jobs pass while building/testing nothing, so fail loudly and echo the
    active filters back to aid debugging.
    """
    if config.targets:
        return
    active = _describe_active_filters(settings)
    detail = f" matching {active}" if active else ""
    stderr_console.print(
        f"❌ No image targets{detail}. Check the --image-name, --image-version, "
        "--image-variant, --image-os, and --image-platform filters along with the "
        "--dev-versions/--matrix-versions selection.",
        style="error",
    )
    raise typer.Exit(code=1)


def _describe_active_filters(settings: "BakerySettings") -> str:
    """Render the set filters as a human-readable ``--flag value`` list."""
    f = settings.filter
    parts = [
        f"--{name} {value!r}"
        for name, value in (
            ("image-name", f.image_name),
            ("image-version", f.image_version),
            ("image-variant", f.image_variant),
            ("image-os", f.image_os),
            ("image-platform", f.image_platform),
        )
        if value
    ]
    return ", ".join(parts)


def parse_dev_spec(ctx: typer.Context, param: typer.CallbackParam, value: str | None) -> DevBuildSpec | None:
    if value is None:
        return None
    try:
        return DevBuildSpec.model_validate_json(value)
    except ValidationError as e:
        raise typer.BadParameter(str(e), ctx=ctx, param=param) from e


def with_verbosity_flags(fn):
    @functools.wraps(fn)
    def wrapper(
        *args,
        verbose: Annotated[Optional[bool], typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
        quiet: Annotated[
            Optional[bool], typer.Option("--quiet", "-q", help="Supress all output except errors")
        ] = False,
        **kwargs,
    ):
        if verbose and quiet:
            raise typer.BadParameter("Cannot set both --verbose and --quiet flags.")

        if verbose:
            SETTINGS.log_level = logging.DEBUG
        elif quiet:
            SETTINGS.log_level = logging.ERROR

        init_logging(SETTINGS.log_level)
        return fn(*args, **kwargs)

    # Update signature with verbosity flags
    sig = inspect.signature(wrapper)
    params = list(sig.parameters.values())
    params.extend(
        [
            inspect.Parameter(
                "verbose",
                inspect.Parameter.KEYWORD_ONLY,
                default=False,
                annotation=Annotated[Optional[bool], typer.Option("--verbose", "-v", help="Enable debug logging")],
            ),
            inspect.Parameter(
                "quiet",
                inspect.Parameter.KEYWORD_ONLY,
                default=False,
                annotation=Annotated[
                    Optional[bool], typer.Option("--quiet", "-q", help="Supress all output except errors")
                ],
            ),
        ]
    )
    sig = sig.replace(parameters=params)
    wrapper.__signature__ = sig

    return wrapper


def with_temporary_storage(fn):
    @functools.wraps(fn)
    def wrapper(ctx: typer.Context, *args, **kwargs) -> None:
        temp_dir = tempfile.TemporaryDirectory(prefix="posit-bakery")
        SETTINGS.temporary_storage = Path(temp_dir.name)
        if ctx.params.get("clean", True):
            ctx.call_on_close(temp_dir.cleanup)

        log.debug(f"Created temporary directory at {SETTINGS.temporary_storage}")

        return fn(*args, **kwargs)

    # Update signature with verbosity flags
    sig = inspect.signature(wrapper)
    params = list(sig.parameters.values())
    params.insert(0, inspect.Parameter("ctx", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=typer.Context))
    sig = sig.replace(parameters=params)
    wrapper.__signature__ = sig

    return wrapper


def __make_value_map(value: list[str] | None) -> tuple[dict[Any, Any], list[Exception]]:
    """Parses key=value option pairs into a dictionary"""
    value_map = dict()
    errors = []
    if value is not None:
        for v in value:
            sp = v.split("=", 1)
            if len(sp) != 2:
                errors.append(ValueError(f"Invalid key=value pair: {v}"))
            else:
                value_map[sp[0]] = sp[1]
    return value_map, errors


def __parse_dependency_constraint(value: str) -> DependencyConstraint:
    """Parses a dependency constraint from a JSON string to a dictionary."""
    dc = json.loads(value)

    if not dc.get("dependency"):
        raise ValueError("Dependency constraint must have a 'dependency' field.")

    dependency_name = str(dc["dependency"])
    dependency_constraint_class = get_dependency_constraint_class(dependency_name)

    return dependency_constraint_class.model_validate(dc)


def __parse_dependency_versions(value: str) -> DependencyVersions:
    """Parses a dependency versions from a JSON string to a dictionary."""
    dv = json.loads(value)

    if not dv.get("dependency"):
        raise ValueError("Dependency versions must have a 'dependency' field.")

    dependency_name = str(dv["dependency"])
    dependency_versions_class = get_dependency_versions_class(dependency_name)

    return dependency_versions_class.model_validate(dv)
