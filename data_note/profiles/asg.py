from __future__ import annotations

from ..tables.asg import (
    make_table1_rows,
    make_table2_rows,
    make_table3_rows,
    make_table4_rows,
    make_table5_rows,
    make_table6_rows,
)
from .base import FigureSpec, ProgrammeProfile, TableSpec


class AsgProfile(ProgrammeProfile):
    name = "asg"

    def figure_specs(self) -> tuple[FigureSpec, ...]:
        return (
            FigureSpec("gscope", "Fig_2_Gscope", "Fig_2_Gscope", "GenomeScope plot"),
            FigureSpec("pretext", "Fig_3_Pretext", "Fig_3_Pretext", "Hi-C contact map"),
            FigureSpec("merqury", "Fig_4_Merqury", "Fig_4_Merqury", "Merqury spectra"),
            FigureSpec("btk_snail", "Fig_5_Snail", "Fig_5_Snail", "Fig 5 Snail"),
            FigureSpec("btk_blob", "Fig_6_Blob", "Fig_6_Blob", "Fig 6 Blob"),
            FigureSpec(
                "metagenome_blob",
                "Fig_7_Metagenome_blob",
                "Fig_7_Metagenome_blob",
                "Metagenome blob plot",
            ),
            FigureSpec(
                "metagenome_tree",
                "Fig_8_Metagenome_tree",
                "Fig_8_Metagenome_tree",
                "Metagenome taxonomic tree",
            ),
        )

    def table_specs(self) -> tuple[TableSpec, ...]:
        return (
            TableSpec("table1", make_table1_rows),
            TableSpec("table2", make_table2_rows),
            TableSpec("table3", make_table3_rows),
            TableSpec("table4", make_table4_rows),
            TableSpec("table5", make_table5_rows),
            TableSpec("table6", make_table6_rows),
        )
