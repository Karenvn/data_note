from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader

from ..asset_images import copy_gscope_image, copy_merian_image, copy_merqury_image
from ..btk_images import download_and_process_btk
from ..fetch_jira_info import download_jira_attachment
from ..pretext_images import label_pretext_map
from ..profiles.base import ProgrammeProfile
from .figure_service import FigureService
from ..text_utils import replace_special_characters

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RenderingService:
    gscope_image_copier: Callable[[str, str], tuple[Any, Any, Any]] = copy_gscope_image
    pretext_labeler: Callable[[str, dict[str, Any], str], tuple[Any, Any, Any]] = label_pretext_map
    merian_image_copier: Callable[[str, str], tuple[Any, Any, Any]] = copy_merian_image
    merqury_image_copier: Callable[[str, str], tuple[Any, Any, Any]] = copy_merqury_image
    btk_image_processor: Callable[[str, str], list[tuple[Any, Any, Any]]] = download_and_process_btk
    jira_attachment_downloader: Callable[[str, str], Any] = download_jira_attachment
    special_character_replacer: Callable[[str], str] = replace_special_characters
    figure_service: FigureService | None = None

    def __post_init__(self) -> None:
        if self.figure_service is None:
            self.figure_service = FigureService(
                gscope_image_copier=self.gscope_image_copier,
                pretext_labeler=self.pretext_labeler,
                merian_image_copier=self.merian_image_copier,
                merqury_image_copier=self.merqury_image_copier,
                btk_image_processor=self.btk_image_processor,
            )

    def write_note(self, template_file: str, context: dict[str, Any], profile: ProgrammeProfile) -> str:
        species_name = context["species"]
        tolid = context["tolid"]
        jira_ticket = context.get("jira")

        if not species_name:
            raise ValueError("species_name cannot be None or empty")

        env = Environment(loader=FileSystemLoader(searchpath=os.path.dirname(template_file)))
        tpl = env.get_template(os.path.basename(template_file))

        output_dir = os.path.join(os.getcwd(), species_name.replace(" ", "_"))
        os.makedirs(output_dir, exist_ok=True)

        self._populate_images(profile, tolid, output_dir, context)

        if jira_ticket:
            self.jira_attachment_downloader(jira_ticket, output_dir)
        else:
            logger.info("No Jira ticket available; skipping Jira attachment download.")

        self._replace_context_text(context)
        self._ensure_tables(context)

        rendered_markdown = tpl.render(**context)
        output_path = os.path.join(output_dir, f"{tolid}.md")
        with open(output_path, "w") as handle:
            handle.write(rendered_markdown)

        logger.info("Markdown genome note created: %s", output_path)
        return output_dir

    def _populate_images(
        self,
        profile: ProgrammeProfile,
        tolid: str,
        output_dir: str,
        context: dict[str, Any],
    ) -> None:
        bundle = self.figure_service.collect(profile, tolid, output_dir, context)
        context.update(bundle.to_context_dict())

    def _replace_context_text(self, context: dict[str, Any]) -> None:
        for key, value in context.items():
            if key == "tables":
                continue
            if isinstance(value, str):
                context[key] = self.special_character_replacer(value, target_format="markdown")

    @staticmethod
    def _resolve_btk_accession(context: dict[str, Any]) -> str | None:
        return FigureService.resolve_btk_accession(context)

    @staticmethod
    def _ensure_tables(context: dict[str, Any]) -> None:
        tables = context.get("tables")
        if tables is None:
            context["tables"] = {}
            return

        for name, table in list(tables.items()):
            if not isinstance(table, dict):
                tables[name] = {
                    "label": f"tbl:{name}",
                    "caption": "",
                    "alignment": "",
                    "rows": [],
                    "native_headers": [],
                    "native_align": [],
                    "native_rows": [],
                }
            else:
                table.setdefault("label", f"tbl:{name}")
                table.setdefault("caption", "")
                table.setdefault("alignment", "")
                table.setdefault("rows", [])
                table.setdefault("native_headers", [])
                table.setdefault("native_align", [])
                table.setdefault("native_rows", [])
                if name == "table4":
                    table.setdefault("width", [0.3, 0.5, 0.2])
