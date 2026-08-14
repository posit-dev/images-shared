from typing import Self

from pydantic import BaseModel
from rich.table import Table

from posit_bakery.config.image.build_os import DEFAULT_PLATFORMS
from posit_bakery.image.image_target import ImageTarget

TAG_ALIAS_NOTE = (
    "Registry Tags counts tag aliases (version, os, latest, etc.) across registries, not distinct stored images."
)


class BuildSummaryRow(BaseModel):
    """A single labeled metric in a build summary report."""

    key: str
    label: str
    value: int


class BuildSummary(BaseModel):
    """Counts (and, once a build has produced artifacts, sizes) for a set of image targets."""

    rows: list[BuildSummaryRow]

    @classmethod
    def from_image_targets(cls, targets: list[ImageTarget], *, platforms: list[str] | None = None) -> Self:
        """Compute build and artifact counts for the given image targets.

        Performs no I/O: every count is derived from configuration already resolved onto
        the targets, so this is safe to call for both `--plan` and real builds.

        :param targets: The resolved image targets to summarize.
        :param platforms: The `--image-platform` CLI override, if any. A target that
            survives that filter keeps its full declared `image_os.platforms` list
            unchanged (`config/config.py:1056-1071` is an any-match gate, not a narrowing
            one) — the actual narrowing to fewer platforms happens later, uniformly across
            targets, via this same value (`image_target.py:664`: `platforms or (...)`).
            Passing it here keeps the count matching what will actually build.
        """
        platform_builds = sum(
            len(platforms)
            if platforms
            else (len(target.image_os.platforms) if target.image_os else len(DEFAULT_PLATFORMS))
            for target in targets
        )
        registry_tags = sum(len(target.tags) for target in targets)

        return cls(
            rows=[
                BuildSummaryRow(key="build_targets", label="Build Targets", value=len(targets)),
                BuildSummaryRow(key="platform_builds", label="Platform Builds", value=platform_builds),
                BuildSummaryRow(key="registry_tags", label="Registry Tags", value=registry_tags),
            ]
        )

    def as_dict(self) -> dict[str, int]:
        """Flatten to `{key: value}` for machine consumption (e.g. `--summary-format json`)."""
        return {row.key: row.value for row in self.rows}

    def table(self, *, sizes: bool) -> Table:
        """Render the summary as a Rich table.

        :param sizes: Reserved for the registry/local size rows added once a build has
            actually produced artifacts to measure.
        :raises NotImplementedError: if `sizes` is True. No size data source exists yet —
            there is nothing to show, so a caller asking for size columns is a bug, not a
            silent no-op.
        """
        if sizes:
            raise NotImplementedError("BuildSummary.table(sizes=True) is not supported yet; sizes ship in Phase 2.")

        table = Table(title="Build Summary", caption=TAG_ALIAS_NOTE)
        table.add_column("Metric", justify="left")
        table.add_column("Count", justify="right")

        for row in self.rows:
            table.add_row(row.label, str(row.value))

        return table
