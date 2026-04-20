from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader

from ..fetch_jira_info import download_jira_attachment
from ..process_images import (
    copy_gscope_image,
    copy_merian_image,
    copy_merqury_image,
    download_and_process_btk,
    label_pretext_map,
)
from ..profiles.base import FigureSpec, ProgrammeProfile
from ..text_utils import replace_special_characters


@dataclass(slots=True)
class RenderingService:
    gscope_image_copier: Callable[[str, str], tuple[Any, Any, Any]] = copy_gscope_image
    pretext_labeler: Callable[[str, dict[str, Any], str], tuple[Any, Any, Any]] = label_pretext_map
    merian_image_copier: Callable[[str, str], tuple[Any, Any, Any]] = copy_merian_image
    merqury_image_copier: Callable[[str, str], tuple[Any, Any, Any]] = copy_merqury_image
    btk_image_processor: Callable[[str, str], list[tuple[Any, Any, Any]]] = download_and_process_btk
    jira_attachment_downloader: Callable[[str, str], Any] = download_jira_attachment
    special_character_replacer: Callable[[str], str] = replace_special_characters

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
            print("No Jira ticket available; skipping Jira attachment download.")

        self._replace_context_text(context)
        self._ensure_tables(context)

        rendered_markdown = tpl.render(**context)
        output_path = os.path.join(output_dir, f"{tolid}.md")
        with open(output_path, "w") as handle:
            handle.write(rendered_markdown)

        print(f"Markdown genome note created: {output_path}")
        return output_dir

    def _populate_images(
        self,
        profile: ProgrammeProfile,
        tolid: str,
        output_dir: str,
        context: dict[str, Any],
    ) -> None:
        for spec in profile.figure_specs():
            if spec.kind == "gscope":
                try:
                    triple = self.gscope_image_copier(tolid, output_dir)
                    self._store_figure(spec, triple, context)
                except Exception:
                    print(f"Gscope plot not found for {tolid}.")
            elif spec.kind == "pretext":
                try:
                    triple = self.pretext_labeler(tolid, context, output_dir)
                    self._store_figure(spec, triple, context)
                except Exception as exc:
                    print(f"Pretext map failed for {tolid}: {exc}")
            elif spec.kind == "merian":
                try:
                    triple = self.merian_image_copier(tolid, output_dir)
                    self._store_figure(spec, triple, context)
                except Exception:
                    print(f"Merian plot not found for {tolid}.")
            elif spec.kind == "merqury":
                try:
                    triple = self.merqury_image_copier(tolid, output_dir)
                    self._store_figure(spec, triple, context)
                except Exception:
                    print(f"Merqury plot not found for {tolid}.")

        accession = self._resolve_btk_accession(context)
        if not accession:
            print("No valid accession found for BTK image download.")
            return

        try:
            btk_triples = self.btk_image_processor(accession, output_dir)
            btk_specs = {
                "snail": next((spec for spec in profile.figure_specs() if spec.kind == "btk_snail"), None),
                "blob": next((spec for spec in profile.figure_specs() if spec.kind == "btk_blob"), None),
            }
            for triple in btk_triples:
                if not triple:
                    continue
                _, _, gif_path = triple
                kind = self._btk_kind_from_stem(Path(gif_path).stem)
                spec = btk_specs.get(kind)
                if spec is not None:
                    self._store_figure(spec, triple, context)
        except Exception as exc:
            print(f"Error processing BTK images for {tolid}: {exc}")

    @staticmethod
    def _btk_kind_from_stem(stem: str) -> str | None:
        if "Snail" in stem:
            return "snail"
        if "Blob" in stem:
            return "blob"
        return None

    @staticmethod
    def _rename_figure_assets(
        stem: str,
        triple: tuple[Any, Any, Any] | None,
    ) -> tuple[Path, Path, Path] | None:
        if not triple:
            return None
        png_path, tif_path, gif_path = (Path(item) for item in triple)
        renamed = []
        for source in (png_path, tif_path, gif_path):
            target = source.with_name(f"{stem}{source.suffix}")
            if source != target:
                source.replace(target)
            renamed.append(target)
        return tuple(renamed)  # type: ignore[return-value]

    def _store_figure(
        self,
        spec: FigureSpec,
        triple: tuple[Any, Any, Any] | None,
        context: dict[str, Any],
    ) -> None:
        renamed = self._rename_figure_assets(spec.stem, triple)
        if not renamed:
            return
        _, _, gif_path = renamed
        context[spec.key] = f"![{spec.alt_text}](./{gif_path.name})"

    def _replace_context_text(self, context: dict[str, Any]) -> None:
        for key, value in context.items():
            if key == "tables":
                continue
            if isinstance(value, str):
                context[key] = self.special_character_replacer(value, target_format="markdown")

    @staticmethod
    def _resolve_btk_accession(context: dict[str, Any]) -> str | None:
        return context.get("prim_accession") or context.get("hap1_accession")

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
