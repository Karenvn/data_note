from __future__ import annotations

from collections import Counter
import logging
from pathlib import Path

from PIL import Image, ImageDraw

from .image_utils import GN_ASSETS_ROOT, convert_png_to_tif_and_gif

MERIAN_ELEMENTS = tuple(f"M{index}" for index in range(1, 25))
MERIAN_COLORS = (
    "#4c78a8",
    "#f58518",
    "#54a24b",
    "#e45756",
    "#72b7b2",
    "#b279a2",
    "#ff9da6",
    "#9d755d",
    "#bab0ac",
    "#8cd17d",
    "#b6992d",
    "#499894",
    "#86bcb6",
    "#d37295",
    "#fabfd2",
    "#b07aa1",
    "#d4a6c8",
    "#9c755f",
    "#d7b5a6",
    "#59a14f",
    "#edc948",
    "#af7aa1",
    "#ffbe7d",
    "#76b7b2",
)


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


def merian_output_dir(tolid):
    """Return the Merian output directory, accepting current and legacy names."""
    base = Path(GN_ASSETS_ROOT)
    for dirname in ("merians", "merian"):
        candidate = base / dirname / tolid
        if candidate.exists():
            return candidate
    return base / "merians" / tolid


def copy_merian_image(tolid, download_dir, output_stem="Fig_3_Merian", context=None):
    merian_dir = merian_output_dir(tolid)
    download_dir_path = Path(download_dir)
    download_dir_path.mkdir(parents=True, exist_ok=True)
    png_path = download_dir_path / f"{output_stem}.png"

    try:
        png_files = list(merian_dir.glob("*.png")) if merian_dir.exists() else []
        if png_files:
            png_path.write_bytes(png_files[0].read_bytes())
            logging.info(f"Copied Merian image to {png_path}")
        elif _generate_merian_plot_from_busco(tolid, png_path, context or {}):
            logging.info(f"Generated Merian image from BUSCO data at {png_path}")
        else:
            if not merian_dir.exists():
                logging.warning(f"Merian directory not found for {tolid}: {merian_dir}")
            else:
                logging.warning(f"No PNG found for {tolid} in {merian_dir}")
            return None

        tif_path, gif_path = convert_png_to_tif_and_gif(str(png_path), dpi=(300, 300), max_width=1200)
        return png_path, Path(tif_path), Path(gif_path)
    except Exception as exc:
        logging.error(f"Error copying Merian image for {tolid}: {exc}")
        return None


def _generate_merian_plot_from_busco(tolid, output_path, context):
    counts_by_chrom = _derive_merian_counts_from_busco(tolid)
    if not counts_by_chrom:
        return False

    chromosome_rows = _chromosome_rows_for_merian_plot(context, counts_by_chrom)
    if not chromosome_rows:
        return False

    cell = 28
    left = 150
    top = 88
    row_height = 34
    width = left + len(MERIAN_ELEMENTS) * cell + 40
    height = top + len(chromosome_rows) * row_height + 64
    image = Image.new("RGB", (width, max(height, 240)), "white")
    draw = ImageDraw.Draw(image)

    draw.text((24, 22), f"Merian BUSCO assignments for {tolid}", fill="#222222")
    for index, element in enumerate(MERIAN_ELEMENTS):
        x = left + index * cell + 2
        draw.text((x, 56), element, fill="#444444")

    for row_index, (label, counts) in enumerate(chromosome_rows):
        y = top + row_index * row_height
        draw.text((24, y + 6), label, fill="#222222")
        for element_index, element in enumerate(MERIAN_ELEMENTS):
            x = left + element_index * cell
            count = counts.get(element, 0)
            outline = "#dddddd"
            fill = MERIAN_COLORS[element_index] if count else "#f7f7f7"
            draw.rectangle((x, y, x + cell - 5, y + row_height - 8), fill=fill, outline=outline)
            if count:
                text = str(count)
                bbox = draw.textbbox((0, 0), text)
                text_width = bbox[2] - bbox[0]
                draw.text((x + (cell - 5 - text_width) / 2, y + 7), text, fill="white")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return True


def _derive_merian_counts_from_busco(tolid):
    reference_table = _first_existing(_merian_reference_candidates())
    busco_table = _first_existing(_busco_table_candidates(tolid))
    if reference_table is None or busco_table is None:
        return {}

    busco_to_merian = _read_merian_reference(reference_table)
    counts_by_chrom = {}
    with busco_table.open() as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 3:
                continue
            merian = busco_to_merian.get(cols[0].strip())
            if not merian:
                continue
            chrom = _normalise_accession_key(cols[2])
            counts_by_chrom.setdefault(chrom, Counter())[merian] += 1
    return counts_by_chrom


def _read_merian_reference(reference_table):
    busco_to_merian = {}
    with reference_table.open() as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 3:
                continue
            merian = cols[2].strip().upper()
            if merian in MERIAN_ELEMENTS:
                busco_to_merian[cols[0].strip()] = merian
    return busco_to_merian


def _chromosome_rows_for_merian_plot(context, counts_by_chrom):
    rows = []
    for entry in context.get("chromosome_data") or context.get("hap1_chromosome_data") or []:
        label = str(entry.get("molecule") or entry.get("name") or entry.get("INSDC") or "").strip()
        accession = str(entry.get("INSDC") or "").strip()
        counts = _lookup_merian_counts(counts_by_chrom, accession or label)
        if counts:
            rows.append((label or accession, counts))

    if rows:
        return rows
    return [(chrom, counts_by_chrom[chrom]) for chrom in sorted(counts_by_chrom)]


def _lookup_merian_counts(counts_by_chrom, value):
    key = _normalise_accession_key(value)
    if key in counts_by_chrom:
        return counts_by_chrom[key]
    base = key.split(".", 1)[0]
    if base in counts_by_chrom:
        return counts_by_chrom[base]
    for chrom, counts in counts_by_chrom.items():
        if chrom.split(".", 1)[0] == base:
            return counts
    return Counter()


def _normalise_accession_key(value):
    return str(value or "").strip()


def _first_existing(candidates):
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _busco_table_candidates(tolid):
    busco_dir = Path(GN_ASSETS_ROOT) / "busco" / str(tolid)
    return (
        busco_dir / "full_table_hap1.1.tsv",
        busco_dir / "full_table.hap1.1.tsv",
        busco_dir / "full_table.tsv",
    )


def _merian_reference_candidates():
    root = Path(GN_ASSETS_ROOT)
    return (
        root / "Merian_elements_full_table.tsv",
        root / "merian" / "Merian_elements_full_table.tsv",
        root / "merians" / "Merian_elements_full_table.tsv",
    )
