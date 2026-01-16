import functools
import inspect
import json
import logging
import tempfile
from pathlib import Path
from typing import Annotated, Optional, Any

import typer

from posit_bakery.config.dependencies import (
    get_dependency_versions_class,
    get_dependency_constraint_class,
    DependencyConstraint,
    DependencyVersions,
)
from posit_bakery.log import init_logging
from posit_bakery.settings import SETTINGS

log = logging.getLogger(__name__)


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
            raise typer.BadParameter("Cannot set both --debug and --quiet flags.")

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
