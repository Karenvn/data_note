from __future__ import annotations

from ..tables.psyche import (
    make_table1_rows,
    make_table2_rows,
    make_table3_rows,
    make_table4_rows,
    make_table5_rows,
)
from .base import ProgrammeProfile, TableSpec


class PsycheProfile(ProgrammeProfile):
    name = "psyche"

    def table_specs(self) -> tuple[TableSpec, ...]:
        return (
            TableSpec("table1", make_table1_rows),
            TableSpec("table2", make_table2_rows),
            TableSpec("table3", make_table3_rows),
            TableSpec("table4", make_table4_rows),
            TableSpec("table5", make_table5_rows),
        )
