import logging
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont

from .chromosome_analyzer import ChromosomeAnalyzer
from .image_utils import GN_ASSETS_ROOT, convert_png_to_tif_and_gif, resolve_open_sans_font
from .ncbi_sequence_report_client import NcbiSequenceReportClient

_DEFAULT_SEQUENCE_REPORT_CLIENT = NcbiSequenceReportClient()
_DEFAULT_CHROMOSOME_ANALYZER = ChromosomeAnalyzer()
_MBP_TICK_INTERVALS = (10, 25, 50, 100, 200, 500, 1000, 2000, 5000, 10000)
_SPLIT_CHROMOSOME_RE = re.compile(r"^(.+?)[_.-](\d+)$")


def _extract_chromosomes_only(accession: str) -> list[dict]:
    reports = _DEFAULT_SEQUENCE_REPORT_CLIENT.fetch_reports(accession)
    return _DEFAULT_CHROMOSOME_ANALYZER.extract_chromosomes_for_pretext_labelling(reports)


def _chromosome_length_mb(chrom: dict) -> float:
    length_bp = chrom.get("length_bp")
    if length_bp is not None:
        return int(length_bp) / 1e6
    return float(chrom["length"])


def _select_pretext_source(matches: list[Path]) -> Path:
    def rank(path: Path) -> tuple[int, str]:
        name = path.name
        if "CustomOrder" in name:
            return (0, name)
        if "FullMap" in name:
            return (1, name)
        return (2, name)

    return sorted(matches, key=rank)[0]


def _split_chromosome_base(molecule: object) -> str | None:
    match = _SPLIT_CHROMOSOME_RE.match(str(molecule))
    if not match:
        return None
    return match.group(1)


def _group_split_chromosomes_for_labelling(chroms: list[dict]) -> list[dict]:
    split_bases = [
        base
        for chrom in chroms
        if (base := _split_chromosome_base(chrom.get("molecule")))
    ]
    if not split_bases or len(set(split_bases)) == len(split_bases):
        return chroms

    grouped: dict[str, dict] = {}
    for chrom in chroms:
        molecule = str(chrom.get("molecule"))
        base = _split_chromosome_base(molecule)
        label = base or molecule
        entry = grouped.setdefault(
            label,
            {
                "molecule": label,
                "length": 0,
                "INSDC": chrom.get("INSDC") if base is None else None,
                "GC": chrom.get("GC") if base is None else None,
                "_pretext_grouped_split": base is not None,
            },
        )
        entry["length"] += _chromosome_length_mb(chrom)
        if chrom.get("length_bp") is not None:
            entry["length_bp"] = int(entry.get("length_bp") or 0) + int(chrom["length_bp"])
            entry["length"] = entry["length_bp"] / 1e6
        if base is not None:
            entry["INSDC"] = None
            entry["GC"] = None
            entry["_pretext_grouped_split"] = True

    return list(grouped.values())


def _filter_chromosomes_for_labelling(
    chroms: list[dict],
    *,
    exclude_molecules: list | None,
    min_fraction: float,
) -> list[dict]:
    if not chroms:
        return []

    chroms = _group_split_chromosomes_for_labelling(chroms)
    max_len = max(_chromosome_length_mb(c) for c in chroms)
    excluded = set(exclude_molecules or [])
    filtered = [
        c
        for c in chroms
        if c["molecule"] not in excluded and _chromosome_length_mb(c) >= min_fraction * max_len
    ]
    return sorted(filtered, key=_chromosome_length_mb, reverse=True)


def _initial_mbp_tick_interval(total_length: float) -> int:
    if total_length <= 50:
        return 10
    if total_length <= 200:
        return 25
    if total_length <= 500:
        return 50
    if total_length <= 1000:
        return 100
    if total_length <= 2000:
        return 200
    return 500


def _choose_mbp_tick_interval(total_length: float, width: int, font) -> int:
    tick_interval = _initial_mbp_tick_interval(total_length)
    start_index = _MBP_TICK_INTERVALS.index(tick_interval)
    sample_labels = ("1000", str(int(total_length // tick_interval * tick_interval)))
    max_label_width = max(font.getbbox(label)[2] - font.getbbox(label)[0] for label in sample_labels)
    min_space_needed = max_label_width * 1.5

    for candidate in _MBP_TICK_INTERVALS[start_index:]:
        estimated_label_count = int(total_length / candidate) + 1
        avg_space_per_label = width / max(estimated_label_count - 1, 1)
        if avg_space_per_label >= min_space_needed:
            return candidate

    return _MBP_TICK_INTERVALS[-1]


def _effective_vertical_label_field(chroms: list[dict], requested_field: str) -> str:
    if requested_field == "INSDC" and any(chrom.get("_pretext_grouped_split") for chrom in chroms):
        return "molecule"
    return requested_field


def draw_pretext_boundary(
    draw,
    left: int,
    top: int,
    width: int,
    height: int,
    *,
    grid_colour: str = "#a9a9a9",
    grid_width: int = 3,
) -> None:
    """Draw the measured Pretext image boundary on the labelled canvas."""

    if grid_width <= 0:
        return
    if width <= 0 or height <= 0:
        return

    right = left + width - 1
    bottom = top + height - 1
    draw.rectangle((left, top, right, bottom), outline=grid_colour, width=grid_width)


def add_mbp_scale(draw, font, left, top, w, h, total_length, font_size, text_colour):
    """Add Mbp scale to bottom of pretext map with smart positioning."""

    initial_tick_interval = _initial_mbp_tick_interval(total_length)
    tick_interval = _choose_mbp_tick_interval(total_length, w, font)
    if tick_interval != initial_tick_interval:
        logging.info(
            "[Mbp Scale] Adjusted interval from %s to %s Mbp to prevent label crowding",
            initial_tick_interval,
            tick_interval,
        )

    scale_y = top + h + int(font_size * 0.5)
    draw.line([(left, scale_y), (left + w, scale_y)], fill=text_colour, width=2)

    current_pos = 0
    tick_count = 0
    last_labeled_tick = None

    while current_pos <= total_length:
        if tick_count % (1 if tick_interval >= 50 else 2) == 0:
            x_pos = left + (current_pos / total_length) * w
            label = f"{int(current_pos)}"
            bbox = font.getbbox(label)
            label_width = bbox[2] - bbox[0]
            last_labeled_tick = (x_pos, label, label_width, current_pos)

        current_pos += tick_interval
        tick_count += 1

    unit_label = "Mbp"
    unit_bbox = font.getbbox(unit_label)
    unit_width = unit_bbox[2] - unit_bbox[0]

    min_gap = 15
    right_margin_start = left + w
    ideal_mbp_x = right_margin_start + 15

    skip_last_label = False
    final_mbp_x = ideal_mbp_x

    if last_labeled_tick:
        last_x, _, last_width, _ = last_labeled_tick
        last_label_right = last_x + last_width / 2

        if ideal_mbp_x - min_gap < last_label_right:
            alt_mbp_x = last_label_right + min_gap
            if alt_mbp_x + unit_width <= left + w + 20:
                final_mbp_x = alt_mbp_x
            else:
                skip_last_label = True
                final_mbp_x = ideal_mbp_x

    current_pos = 0
    tick_count = 0

    while current_pos <= total_length:
        x_pos = left + (current_pos / total_length) * w
        tick_height = font_size // 4
        draw.line([(x_pos, scale_y), (x_pos, scale_y + tick_height)], fill=text_colour, width=2)

        if tick_count % (1 if tick_interval >= 50 else 2) == 0:
            label = f"{int(current_pos)}"
            bbox = font.getbbox(label)
            label_width = bbox[2] - bbox[0]

            is_last_labeled_tick = (
                last_labeled_tick
                and current_pos == last_labeled_tick[3]
                and skip_last_label
            )

            if not is_last_labeled_tick:
                draw.text(
                    (x_pos - label_width / 2, scale_y + tick_height + font_size // 6),
                    label,
                    font=font,
                    fill=text_colour,
                )

        current_pos += tick_interval
        tick_count += 1

    draw.text(
        (final_mbp_x, scale_y + tick_height + font_size // 6),
        unit_label,
        font=font,
        fill=text_colour,
    )


def label_pretext_map(
    tolid: str,
    context: dict,
    output_dir: str,
    output_stem: str = "Fig_3_Pretext",
    font_path: str | None = None,
    font_size: int = 60,
    exclude_molecules: list = None,
    min_fraction: float = 0.01,
    background_colour: str = "white",
    text_colour: str = "black",
    vertical_label_field: str = "INSDC",
    grid_colour: str = "#a9a9a9",
    grid_width: int = 3,
) -> tuple[Path, Path, Path]:
    """Label a pretext PNG and write PNG/TIFF/GIF outputs."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if font_path is None:
        font_path = resolve_open_sans_font()
        if font_path is None:
            font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"

    pretext_dir = Path(GN_ASSETS_ROOT) / "pretext_images"
    logging.debug("[Pretext] Looking in %s for files named %s*.png", pretext_dir, tolid)

    matches = list(pretext_dir.glob(f"{tolid}*.png"))
    if not matches:
        logging.error("[Pretext] No .png files found for %s in %s", tolid, pretext_dir)
        return None

    src_png = _select_pretext_source(matches)
    logging.info("[Pretext] Found source PNG: %s", src_png)

    if "prim_accession" in context:
        chroms = _extract_chromosomes_only(context["prim_accession"])
    elif "hap1_accession" in context:
        chroms = _extract_chromosomes_only(context["hap1_accession"])
    else:
        logging.error("[Pretext] No accession in context for %s", tolid)
        return None

    raw_len = context.get("genome_length_unrounded") or context.get("hap1_genome_length_unrounded")
    total_length = (raw_len / 1e6) if raw_len else None
    logging.debug("[Pretext] total_length=%s Mb; chromosomes=%s", total_length, len(chroms))

    img = Image.open(src_png)
    w, h = img.size
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        logging.warning("[Pretext] Could not load font %s, using default", font_path)
        font = ImageFont.load_default()

    max_label_fraction = 0.97
    dot_width = font.getbbox(".")[2] - font.getbbox(".")[0]

    sorted_chroms = _filter_chromosomes_for_labelling(
        chroms,
        exclude_molecules=exclude_molecules,
        min_fraction=min_fraction,
    )
    if not sorted_chroms:
        logging.error("[Pretext] No chromosomes available for %s after filtering", tolid)
        return None
    effective_vertical_label_field = _effective_vertical_label_field(sorted_chroms, vertical_label_field)

    base_font_size = font_size
    chrom_count = len(sorted_chroms)
    max_font_size = 90

    if chrom_count > 25:
        font_size = base_font_size
    elif chrom_count > 20:
        font_size = min(max_font_size, base_font_size + 5)
    elif chrom_count > 10:
        font_size = min(max_font_size, base_font_size + 10)
    else:
        font_size = min(max_font_size, base_font_size + 20)

    logging.info("[Pretext] Adjusted font size: %s for %s chromosomes", font_size, chrom_count)

    top = int(font_size * 2.5)
    left = int(font_size * 7)
    bottom = int(font_size * 2.5)
    right = int(font_size * 2.5)

    canvas = Image.new("RGB", (w + left + right, h + top + bottom), background_colour)
    canvas.paste(img, (left, top))
    draw = ImageDraw.Draw(canvas)

    acc = 0
    x_positions = []
    total = total_length or sum(_chromosome_length_mb(c) for c in sorted_chroms)
    draw_pretext_boundary(
        draw,
        left,
        top,
        w,
        h,
        grid_colour=grid_colour,
        grid_width=grid_width,
    )
    for chrom in sorted_chroms:
        block = (_chromosome_length_mb(chrom) / total) * w
        x_positions.append(acc + block / 2)
        acc += block

    def fits_block(text_width, block_width, fraction=max_label_fraction):
        return text_width <= block_width * fraction

    def overlaps_prev(left_edge, right_edge, boxes, pad=0):
        return any(left_edge - pad < box_right and right_edge + pad > box_left for box_left, box_right in boxes)

    drawn_boxes = []
    for index, chrom in enumerate(sorted_chroms):
        label = str(chrom["molecule"])
        block = (_chromosome_length_mb(chrom) / total) * w
        bbox = font.getbbox(label)
        text_width = bbox[2] - bbox[0]

        ok = fits_block(text_width, block)
        if ok:
            x_left = left + x_positions[index] - text_width / 2
            x_right = x_left + text_width
            if overlaps_prev(x_left, x_right, drawn_boxes):
                ok = False

        if ok:
            y = int(font_size * 0.6)
            draw.text((x_left, y), label, font=font, fill=text_colour)
            drawn_boxes.append((x_left, x_right))
        else:
            x = left + x_positions[index] - dot_width / 2
            y = int(font_size * 0.4)
            draw.text((x, y), ".", font=font, fill=text_colour)

    y_positions = []
    acc_h = 0
    for chrom in sorted_chroms:
        block_h = (_chromosome_length_mb(chrom) / total) * h
        y_positions.append(acc_h + block_h / 2)
        acc_h += block_h

    bbox22 = font.getbbox("22")
    drawn_y_boxes: list[tuple[float, float]] = []

    def overlaps_prev_y(top_edge, bottom_edge, boxes, pad=0):
        return any(top_edge - pad < box_bottom and bottom_edge + pad > box_top for box_top, box_bottom in boxes)

    for index, chrom in enumerate(sorted_chroms):
        label = str(chrom.get(effective_vertical_label_field) or chrom.get("molecule") or "?")
        bbox = font.getbbox(label)
        text_height = bbox[3] - bbox[1]
        text_width = bbox[2] - bbox[0]

        block_h = (_chromosome_length_mb(chrom) / total) * h
        centre_y = top + y_positions[index]
        y_top = int(centre_y - text_height / 2 - font_size * 0.4)
        y_bottom = y_top + text_height

        ok = block_h >= text_height * max_label_fraction
        if ok and overlaps_prev_y(y_top, y_bottom, drawn_y_boxes, pad=5):
            ok = False

        if ok:
            x = left - text_width - int(font_size * 0.4)
            draw.text((x, y_top), label, font=font, fill=text_colour)
            drawn_y_boxes.append((y_top, y_bottom))
        else:
            dot_bbox = font.getbbox(".")
            dot_top = dot_bbox[1]
            dot_height = dot_bbox[3] - dot_bbox[1]
            x = left - dot_width - int(font_size * 0.4)
            y_dot = int(centre_y - (dot_height / 2) - dot_top)
            draw.text((x, y_dot), ".", font=font, fill=text_colour)

    if total_length:
        add_mbp_scale(draw, font, left, top, w, h, total_length, font_size, text_colour)

    out_png = output_dir / f"{output_stem}.png"
    canvas.save(out_png)
    logging.info("[Pretext] Saved labelled PNG -> %s", out_png)

    tif, gif = convert_png_to_tif_and_gif(str(out_png), dpi=(300, 300), max_width=1200)
    logging.info("[Pretext] Converted to TIFF & GIF -> %s, %s", tif, gif)

    return out_png, Path(tif), Path(gif)
