from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader

from ..fetch_jira_info import download_jira_attachment
from ..process_images import copy_gscope_image, copy_merqury_image, download_and_process_btk, label_pretext_map
from ..text_utils import replace_special_characters


@dataclass(slots=True)
class RenderingService:
    gscope_image_copier: Callable[[str, str], tuple[Any, Any, Any]] = copy_gscope_image
    pretext_labeler: Callable[[str, dict[str, Any], str], tuple[Any, Any, Any]] = label_pretext_map
    merqury_image_copier: Callable[[str, str], tuple[Any, Any, Any]] = copy_merqury_image
    btk_image_processor: Callable[[str, str], list[tuple[Any, Any, Any]]] = download_and_process_btk
    jira_attachment_downloader: Callable[[str, str], Any] = download_jira_attachment
    special_character_replacer: Callable[[str], str] = replace_special_characters

    def write_note(self, assemblies_type: str, template_file: str, context: dict[str, Any]) -> str:
        species_name = context["species"]
        tolid = context["tolid"]
        jira_ticket = context.get("jira")

        if not species_name:
            raise ValueError("species_name cannot be None or empty")

        env = Environment(loader=FileSystemLoader(searchpath=os.path.dirname(template_file)))
        tpl = env.get_template(os.path.basename(template_file))

        output_dir = os.path.join(os.getcwd(), species_name.replace(" ", "_"))
        os.makedirs(output_dir, exist_ok=True)

        self._populate_images(assemblies_type, tolid, output_dir, context)

        if jira_ticket:
            self.jira_attachment_downloader(jira_ticket, output_dir)
        else:
            print("No Jira ticket available; skipping Jira attachment download.")

        self._replace_context_text(context)
        self._ensure_tables(context)

        rendered_markdown = tpl.render(**context)
        output_path = os.path.join(output_dir, f"{tolid}.md")
        with open(output_path, "w") as handle:
            handle.write(rendered_markdown)

        print(f"Markdown data note created: {output_path}")
        return output_dir

    def _populate_images(
        self,
        assemblies_type: str,
        tolid: str,
        output_dir: str,
        context: dict[str, Any],
    ) -> None:
        try:
            _, _, gif2 = self.gscope_image_copier(tolid, output_dir)
            context["Fig_2_Gscope"] = f"![GenomeScope plot](./{gif2.name})"
        except Exception:
            print(f"Gscope plot not found for {tolid}.")

        try:
            self.pretext_labeler(tolid, context, output_dir)
        except Exception as exc:
            print(f"Pretext map failed for {tolid}: {exc}")

        try:
            _, _, gif4 = self.merqury_image_copier(tolid, output_dir)
            context["Fig_4_Merqury"] = f"![Merqury spectra](./{gif4.name})"
        except Exception:
            print(f"Merqury plot not found for {tolid}.")

        accession = self._resolve_btk_accession(assemblies_type, context)
        if not accession:
            print("No valid accession found for BTK image download.")
            return

        try:
            btk_triples = self.btk_image_processor(accession, output_dir)
            for _, _, gif_path in btk_triples:
                stem = gif_path.stem
                context[stem] = f"![{stem.replace('_', ' ')}](./{gif_path.name})"
        except Exception as exc:
            print(f"Error processing BTK images for {tolid}: {exc}")

    def _replace_context_text(self, context: dict[str, Any]) -> None:
        for key, value in context.items():
            if key == "tables":
                continue
            if isinstance(value, str):
                context[key] = self.special_character_replacer(value, target_format="markdown")

    @staticmethod
    def _resolve_btk_accession(assemblies_type: str, context: dict[str, Any]) -> str | None:
        if assemblies_type == "prim_alt":
            return context.get("prim_accession")
        if assemblies_type == "hap_asm":
            return context.get("hap1_accession")
        return None

    @staticmethod
    def _ensure_tables(context: dict[str, Any]) -> None:
        from .. import table_rows

        print("table_rows module:", table_rows.__file__)

        tables = context.get("tables")
        print("tables keys:", list(tables.keys()) if tables else None)
        print("table4:", tables.get("table4") if tables else None)

        if tables is None:
            tables = {}
            context["tables"] = tables

        for name in ["table1", "table2", "table3", "table4", "table5"]:
            table = tables.get(name)
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
