from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from typing import Callable

import pandas as pd

from ..formatting_utils import format_with_nbsp
from ..models import FlowCytometryInfo

logger = logging.getLogger(__name__)


def _default_cyto_info_tsv() -> Path:
    explicit = os.getenv("DATA_NOTE_CYTO_INFO_TSV")
    if explicit:
        return Path(explicit).expanduser()
    assets_root = (
        os.getenv("DATA_NOTE_GN_ASSETS")
        or os.getenv("DATA_NOTE_SERVER_DATA")
        or str(Path.home() / "gn_assets")
    )
    return Path(assets_root).expanduser() / "cyto_info.tsv"


@dataclass(slots=True)
class FlowCytometryService:
    tsv_path: Path = field(default_factory=_default_cyto_info_tsv)
    csv_reader: Callable[..., pd.DataFrame] = pd.read_csv
    _dataframe_cache: pd.DataFrame | None = field(default=None, init=False, repr=False)

    def build_context(self, species_name: str | None) -> FlowCytometryInfo | None:
        if not species_name:
            return None

        dataframe = self._load_dataframe()
        if dataframe.empty:
            return None

        matches = dataframe[dataframe["species_name"].str.lower() == species_name.lower()]
        if matches.empty:
            return None

        row = self._select_preferred_match(matches).iloc[0]
        buffer_code = self._string_value(row.get("Buffer"))
        standard_name = self._string_value(row.get("Standard"))
        return FlowCytometryInfo(
            flow_pg=self._float_value(row.get("GS pg (1C)")),
            flow_mb=format_with_nbsp(self._float_value(row.get("1C/Gbp")) * 1000),
            flow_buffer=buffer_code,
            buffer_desc=self.describe_buffer(buffer_code),
            standard_desc=self.describe_standard(standard_name),
            flow_project=self._string_value(row.get("Project")) or None,
            flow_dtol_specimen_id=self._string_value(row.get("DToL Specimen ID")) or None,
        )

    def _load_dataframe(self) -> pd.DataFrame:
        if self._dataframe_cache is not None:
            return self._dataframe_cache

        if not self.tsv_path.exists():
            logger.debug("Flow cytometry TSV not found at %s", self.tsv_path)
            self._dataframe_cache = pd.DataFrame()
            return self._dataframe_cache

        dataframe = self.csv_reader(
            self.tsv_path,
            sep="\t",
            dtype={"Genus": str, "Species": str, "Species ": str},
        )
        dataframe.columns = (
            dataframe.columns.str.strip().str.replace(r"\s+", " ", regex=True)
        )
        for column in ("Genus", "Species", "Project", "DToL Specimen ID"):
            if column not in dataframe.columns:
                dataframe[column] = ""
        dataframe["Genus"] = dataframe["Genus"].fillna("").astype(str).str.strip()
        dataframe["Species"] = dataframe["Species"].fillna("").astype(str).str.strip()
        dataframe = dataframe[(dataframe["Genus"] != "") & (dataframe["Species"] != "")]

        for column in ("GS pg (1C)", "1C/Gbp"):
            if column in dataframe.columns:
                dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")
            else:
                dataframe[column] = pd.NA

        dataframe["species_name"] = dataframe["Genus"] + " " + dataframe["Species"]
        self._dataframe_cache = dataframe
        return self._dataframe_cache

    @staticmethod
    def _select_preferred_match(matches: pd.DataFrame) -> pd.DataFrame:
        preferred = matches[
            matches["Project"].fillna("").astype(str).str.strip().str.upper().eq("DTOL")
            | matches["DToL Specimen ID"].fillna("").astype(str).str.strip().ne("")
        ]
        if not preferred.empty:
            return preferred
        return matches

    @staticmethod
    def describe_buffer(code: str) -> str:
        if code.startswith("GPB3%PVPBmet"):
            return "The General Purpose Buffer (GPB) supplemented with 3% PVP and 0.08% (v/v) beta-mercaptoethanol"
        if code.startswith("OXPRO"):
            return "CyStain PI OxProtect Staining Buffer (Sysmex UK Ltd)"
        if code.startswith("Galbraith3PVP"):
            return "The General Purpose Buffer (GPB) supplemented with 3% PVP"
        if code.startswith("GPB3%PVP"):
            return "The General Purpose Buffer (GPB) supplemented with 3% PVP"
        if code.startswith("GPB"):
            return "The General Purpose Buffer (GPB)"
        return code

    @staticmethod
    def describe_standard(name: str) -> str:
        if not isinstance(name, str):
            return ""

        genus = name.strip("<> ").split()[0].capitalize() if name.strip() else ""
        if genus == "Petro" or "Petroselinum" in genus:
            return "*Petroselinum crispum* 'Champion Moss Curled' with an assumed 1C-value of 2&nbsp;200 Mb [@obermayerCval2002]"
        if genus == "Pisum":
            return "*Pisum sativum* 'Ctirad' with an assumed 1C-value of 4&nbsp;445 Mb [@dolezelFlow1998]"
        if genus == "Solanum":
            return "*Solanum lycopersicum* 'Stupike polni rane' with an assumed 1C-value of 968 Mb [@dolezelFlowDNA2007]"
        if genus == "Allium":
            return "*Allium cepa* L. 'Alice' with an assumed 1C-value of 17&nbsp;059&nbsp;Mb [@dolezelFlowDNA2007]"
        if genus == "Oryza":
            return "*Oryza sativa* 'IR36' with an assumed 1C-value of 493.89 Mb [@obermayerCval2002]"
        if genus == "Secale":
            return "*Secale cereale* 'Dankovske' with an assumed 1C-value of 8&nbsp;105&nbsp;Mb [@ddolezelFlowDNA2007]"
        if "no result" in name.lower() or "messy" in name.lower():
            return ""
        return name.strip()

    @staticmethod
    def _string_value(value: object) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        return str(value).strip()

    @staticmethod
    def _float_value(value: object) -> float:
        try:
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0
