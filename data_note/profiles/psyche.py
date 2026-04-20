from __future__ import annotations

from ..tables.psyche import (
    make_table1_rows,
    make_table2_rows,
    make_table3_rows,
    make_table4_rows,
    make_table5_rows,
)
from .base import FigureSpec, ProgrammeProfile, TableSpec


class PsycheProfile(ProgrammeProfile):
    name = "psyche"

    def figure_specs(self) -> tuple[FigureSpec, ...]:
        return (
            FigureSpec("gscope", "Fig_2_Gscope", "Fig_2_Gscope", "GenomeScope plot"),
            FigureSpec("pretext", "Fig_3_Pretext", "Fig_3_Pretext", "Hi-C contact map"),
            FigureSpec("merian", "Fig_4_Merian", "Fig_4_Merian", "Merian elements"),
            FigureSpec("merqury", "Fig_5_Merqury", "Fig_5_Merqury", "Merqury spectra"),
            FigureSpec("btk_snail", "Fig_6_Snail", "Fig_6_Snail", "Fig 6 Snail"),
            FigureSpec("btk_blob", "Fig_7_Blob", "Fig_7_Blob", "Fig 7 Blob"),
        )

    def table_specs(self) -> tuple[TableSpec, ...]:
        return (
            TableSpec("table1", make_table1_rows),
            TableSpec("table2", make_table2_rows),
            TableSpec("table3", make_table3_rows),
            TableSpec("table4", make_table4_rows),
            TableSpec("table5", make_table5_rows),
        )
