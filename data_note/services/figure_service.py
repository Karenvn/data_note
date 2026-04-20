from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..asset_images import copy_gscope_image, copy_merian_image, copy_merqury_image
from ..btk_images import download_and_process_btk
from ..models import FigureAsset, FigureBundle
from ..pretext_images import label_pretext_map
from ..profiles.base import FigureSpec, ProgrammeProfile


@dataclass(slots=True)
class FigureService:
    gscope_image_copier: Callable[..., tuple[Any, Any, Any] | None] = copy_gscope_image
    pretext_labeler: Callable[..., tuple[Any, Any, Any] | None] = label_pretext_map
    merian_image_copier: Callable[..., tuple[Any, Any, Any] | None] = copy_merian_image
    merqury_image_copier: Callable[..., tuple[Any, Any, Any] | None] = copy_merqury_image
    btk_image_processor: Callable[..., list[tuple[Any, Any, Any]]] = download_and_process_btk

    def collect(
        self,
        profile: ProgrammeProfile,
        tolid: str,
        output_dir: str,
        context: dict[str, Any],
    ) -> FigureBundle:
        bundle = FigureBundle()
        btk_specs = self._btk_spec_map(profile)

        for spec in profile.figure_specs():
            if spec.kind in {"btk_snail", "btk_blob"}:
                continue
            asset = self._collect_single(spec, tolid, output_dir, context)
            if asset is not None:
                bundle.add(asset)

        accession = self.resolve_btk_accession(context)
        if accession:
            output_names = {
                "snail": f"{btk_specs['snail'].stem}.png" if btk_specs.get("snail") else "Fig_5_Snail.png",
                "blob": f"{btk_specs['blob'].stem}.png" if btk_specs.get("blob") else "Fig_6_Blob.png",
            }
            for triple in self.btk_image_processor(accession, output_dir, output_names=output_names):
                if not triple:
                    continue
                kind = self._btk_kind_from_stem(triple[2])
                spec = btk_specs.get(kind)
                if spec is None:
                    continue
                asset = self._build_asset(spec, triple)
                if asset is not None:
                    bundle.add(asset)

        return bundle

    def _collect_single(
        self,
        spec: FigureSpec,
        tolid: str,
        output_dir: str,
        context: dict[str, Any],
    ) -> FigureAsset | None:
        if spec.kind == "gscope":
            triple = self.gscope_image_copier(tolid, output_dir, output_stem=spec.stem)
        elif spec.kind == "pretext":
            triple = self.pretext_labeler(tolid, context, output_dir, output_stem=spec.stem)
        elif spec.kind == "merian":
            triple = self.merian_image_copier(tolid, output_dir, output_stem=spec.stem)
        elif spec.kind == "merqury":
            triple = self.merqury_image_copier(tolid, output_dir, output_stem=spec.stem)
        else:
            return None

        return self._build_asset(spec, triple)

    def _build_asset(
        self,
        spec: FigureSpec,
        triple: tuple[Any, Any, Any] | None,
    ) -> FigureAsset | None:
        if not triple:
            return None
        png_path, tif_path, gif_path = (Path(item) for item in triple)
        return FigureAsset(
            kind=spec.kind,
            key=spec.key,
            stem=spec.stem,
            alt_text=spec.alt_text,
            png_path=png_path,
            tif_path=tif_path,
            gif_path=gif_path,
        )

    @staticmethod
    def resolve_btk_accession(context: dict[str, Any]) -> str | None:
        return context.get("prim_accession") or context.get("hap1_accession")

    @staticmethod
    def _btk_kind_from_stem(path_like: Any) -> str | None:
        stem = str(path_like)
        if stem.endswith(".gif") or stem.endswith(".png") or stem.endswith(".tif"):
            stem = stem.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
        if "Snail" in stem:
            return "snail"
        if "Blob" in stem:
            return "blob"
        return None

    @staticmethod
    def _btk_spec_map(profile: ProgrammeProfile) -> dict[str, FigureSpec]:
        specs = {spec.kind: spec for spec in profile.figure_specs()}
        return {
            "snail": specs.get("btk_snail"),
            "blob": specs.get("btk_blob"),
        }
