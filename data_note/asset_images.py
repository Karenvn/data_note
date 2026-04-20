from __future__ import annotations

import logging
from pathlib import Path

from .image_utils import GN_ASSETS_ROOT, convert_png_to_tif_and_gif


def copy_gscope_image(tolid, download_dir, output_stem="Fig_2_Gscope"):
    gscope_dir = Path(GN_ASSETS_ROOT) / "gscope_results" / f"{tolid}"
    candidates = [
        gscope_dir / f"{tolid}.k31_linear_plot.png",
        gscope_dir / "fastk_genomescope_linear_plot.png",
    ]

    src_path = next((candidate for candidate in candidates if candidate.exists()), None)
    if not src_path:
        logging.error(f"GenomeScope image not found for {tolid} in {gscope_dir}")
        return None

    try:
        download_dir_path = Path(download_dir)
        download_dir_path.mkdir(parents=True, exist_ok=True)

        png_path = download_dir_path / f"{output_stem}.png"
        png_path.write_bytes(src_path.read_bytes())
        logging.info(f"Copied GenomeScope plot to {png_path}")

        tif_path, gif_path = convert_png_to_tif_and_gif(str(png_path), dpi=(300, 300), max_width=800)
        return png_path, Path(tif_path), Path(gif_path)
    except Exception as exc:
        logging.error(f"Error handling GenomeScope image: {exc}")
        return None


def copy_merqury_image(tolid, download_dir, output_stem="Fig_4_Merqury"):
    merqury_dir = Path(GN_ASSETS_ROOT) / "merqury_results" / f"{tolid}"
    candidates = [
        merqury_dir / f"{tolid}.spectra-asm.ln.png",
        merqury_dir / f"{tolid}.spectra-cn.ln.png",
        merqury_dir / "fastk_merqury_linear_plot.png",
    ]

    src_path = next((candidate for candidate in candidates if candidate.exists()), None)
    if not src_path:
        logging.error(f"Merqury image not found for {tolid} in {merqury_dir}")
        return None

    try:
        download_dir_path = Path(download_dir)
        download_dir_path.mkdir(parents=True, exist_ok=True)

        png_path = download_dir_path / f"{output_stem}.png"
        png_path.write_bytes(src_path.read_bytes())
        logging.info(f"Copied Merqury plot to {png_path}")

        tif_path, gif_path = convert_png_to_tif_and_gif(str(png_path), dpi=(300, 300), max_width=800)
        return png_path, Path(tif_path), Path(gif_path)
    except Exception as exc:
        logging.error(f"Error handling Merqury image: {exc}")
        return None


def copy_merian_image(tolid, download_dir, output_stem="Fig_3_Merian"):
    merian_dir = Path(GN_ASSETS_ROOT) / "merian" / tolid
    if not merian_dir.exists():
        logging.warning(f"Merian directory not found for {tolid}: {merian_dir}")
        return None

    png_files = list(merian_dir.glob("*.png"))
    if not png_files:
        logging.warning(f"No PNG found for {tolid} in {merian_dir}")
        return None

    src_path = png_files[0]
    download_dir_path = Path(download_dir)
    download_dir_path.mkdir(parents=True, exist_ok=True)
    png_path = download_dir_path / f"{output_stem}.png"

    try:
        png_path.write_bytes(src_path.read_bytes())
        logging.info(f"Copied Merian image to {png_path}")

        tif_path, gif_path = convert_png_to_tif_and_gif(str(png_path), dpi=(300, 300), max_width=1200)
        return png_path, Path(tif_path), Path(gif_path)
    except Exception as exc:
        logging.error(f"Error copying Merian image for {tolid}: {exc}")
        return None
