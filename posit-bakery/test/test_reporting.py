from posit_bakery.reporting import GroupColumn, ValueColumn, grouped_table


def _row(group, value):
    return {"group": group, "value": value}


def _cell(table, row_index, col_header):
    column = next(c for c in table.columns if c.header == col_header)
    return str(list(column.cells)[row_index])


class TestGroupedTable:
    def test_repeated_group_key_is_blanked(self):
        rows = [_row("a", 1), _row("a", 2), _row("b", 3)]
        table = grouped_table(
            rows,
            title="t",
            group_columns=[GroupColumn("Group", lambda r: r["group"])],
            value_columns=[
                ValueColumn("Value", lambda r: str(r["value"]), total=lambda rs: str(sum(r["value"] for r in rs)))
            ],
        )

        assert _cell(table, 0, "Group") == "a"
        assert _cell(table, 1, "Group") == ""
        assert _cell(table, 2, "Group") == "b"

    def test_outer_key_change_reshows_inner_column_even_if_value_repeats(self):
        """An inner column must not stay blanked just because its own value happens to
        repeat, once an outer group column has changed -- it belongs to a new group."""
        rows = [
            {"outer": "a", "inner": "x", "value": 1},
            {"outer": "b", "inner": "x", "value": 2},  # inner repeats "x", but outer changed
        ]
        table = grouped_table(
            rows,
            title="t",
            group_columns=[GroupColumn("Outer", lambda r: r["outer"]), GroupColumn("Inner", lambda r: r["inner"])],
            value_columns=[ValueColumn("Value", lambda r: str(r["value"]))],
        )

        assert _cell(table, 1, "Outer") == "b"
        assert _cell(table, 1, "Inner") == "x"

    def test_total_row_sums_via_reducer(self):
        rows = [_row("a", 1), _row("b", 2), _row("c", 3)]
        table = grouped_table(
            rows,
            title="t",
            group_columns=[GroupColumn("Group", lambda r: r["group"])],
            value_columns=[
                ValueColumn("Value", lambda r: str(r["value"]), total=lambda rs: str(sum(r["value"] for r in rs)))
            ],
        )

        assert _cell(table, 0, "Group") == "a"
        assert _cell(table, 3, "Group") == "Total"
        assert _cell(table, 3, "Value") == "6"

    def test_total_is_blank_when_no_reducer_given(self):
        """A column with no `total` (e.g. a per-item count that isn't meaningful summed
        across unrelated rows) must leave the Total row's cell blank, not zero."""
        rows = [_row("a", 1), _row("b", 2)]
        table = grouped_table(
            rows,
            title="t",
            group_columns=[GroupColumn("Group", lambda r: r["group"])],
            value_columns=[ValueColumn("Value", lambda r: str(r["value"]))],
        )

        assert _cell(table, 2, "Value") == ""

    def test_empty_items_still_produces_headers_and_total_row(self):
        table = grouped_table(
            [],
            title="t",
            group_columns=[GroupColumn("Group", lambda r: r["group"])],
            value_columns=[ValueColumn("Value", lambda r: str(r["value"]), total=lambda rs: str(len(rs)))],
        )

        assert [c.header for c in table.columns] == ["Group", "Value"]
        assert table.row_count == 1  # just the Total row
        assert _cell(table, 0, "Group") == "Total"
        assert _cell(table, 0, "Value") == "0"
