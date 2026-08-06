from dataclasses import dataclass
from typing import Any, Callable

from rich.table import Table


@dataclass
class GroupColumn:
    """A leading identity column used to nest rows; a repeated value is blanked once every
    outer group column is also unchanged from the previous row, giving the same outline style
    as a nested for-loop, without requiring one.
    """

    header: str
    key: Callable[[Any], str]


@dataclass
class ValueColumn:
    """A trailing data column rendered per row, with an optional Total-row aggregation.

    :param total: Computes this column's cell in the closing `Total` row from the full list
        of items. `None` leaves that cell blank -- for a metric where summing across
        unrelated rows wouldn't mean anything (e.g. a per-image layer count).
    """

    header: str
    render: Callable[[Any], Any]
    justify: str = "right"
    header_style: str | None = None
    total: Callable[[list[Any]], Any] | None = None


def grouped_table(
    items: list[Any],
    *,
    title: str,
    group_columns: list[GroupColumn],
    value_columns: list[ValueColumn],
    caption: str | None = None,
) -> Table:
    """Render `items` as a Rich table nested by `group_columns`, followed by a `Total` row.

    Mirrors the outline style bakery's report tables already use (e.g. Goss test results):
    a group column's value is shown only when it (or an outer group column) differs from the
    previous row, and a closing row labeled `Total` summarizes whichever `value_columns`
    define a `total` reducer.

    `items` must already be ordered so that equal group keys are adjacent -- this function
    renders in the given order, it does not sort or bucket by the group keys itself.
    """
    table = Table(title=title, caption=caption)
    for group_column in group_columns:
        table.add_column(group_column.header, justify="left")
    for value_column in value_columns:
        table.add_column(value_column.header, justify=value_column.justify, header_style=value_column.header_style)

    previous_keys: list[Any] = [object()] * len(group_columns)
    for item in items:
        current_keys = [group_column.key(item) for group_column in group_columns]
        group_cells = []
        changed = False
        for index, key in enumerate(current_keys):
            changed = changed or key != previous_keys[index]
            group_cells.append(key if changed else "")
        previous_keys = current_keys

        table.add_row(*group_cells, *(value_column.render(item) for value_column in value_columns))

    table.add_section()
    total_cells = [value_column.total(items) if value_column.total else "" for value_column in value_columns]
    table.add_row("Total", *([""] * (len(group_columns) - 1)), *total_cells)

    return table
