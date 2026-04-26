import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .chromosome_analyzer import ChromosomeAnalyzer
from .image_utils import GN_ASSETS_ROOT, convert_png_to_tif_and_gif, resolve_open_sans_font
from .ncbi_sequence_report_client import NcbiSequenceReportClient

_DEFAULT_SEQUENCE_REPORT_CLIENT = NcbiSequenceReportClient()
_DEFAULT_CHROMOSOME_ANALYZER = ChromosomeAnalyzer()


def _extract_chromosomes_only(accession: str) -> list[dict]:
    reports = _DEFAULT_SEQUENCE_REPORT_CLIENT.fetch_reports(accession)
    return _DEFAULT_CHROMOSOME_ANALYZER.extract_chromosomes_only(reports)


def add_mbp_scale(draw, font, left, top, w, h, total_length, font_size, text_colour):
    """Add Mbp scale to bottom of pretext map with smart positioning."""

    if total_length <= 50:
        tick_interval = 10
    elif total_length <= 200:
        tick_interval = 25
    elif total_length <= 500:
        tick_interval = 50
    elif total_length <= 1000:
        tick_interval = 100
    elif total_length <= 2000:
        tick_interval = 200
    else:
        tick_interval = 500

    estimated_label_count = int(total_length / tick_interval) + 1
    avg_space_per_label = w / estimated_label_count if estimated_label_count > 0 else w

    sample_bbox = font.getbbox("1000")
    typical_label_width = sample_bbox[2] - sample_bbox[0]
    min_space_needed = typical_label_width * 1.5

    if avg_space_per_label < min_space_needed:
        if tick_interval == 10:
            tick_interval = 25
        elif tick_interval == 25:
            tick_interval = 50
        elif tick_interval == 50:
            tick_interval = 100
        elif tick_interval == 100:
            tick_interval = 200
        elif tick_interval == 200:
            tick_interval = 500
        elif tick_interval == 500:
            tick_interval = 1000

        logging.info(
            "[Mbp Scale] Adjusted interval from original to %s Mbp to prevent label crowding",
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

    src_png = matches[0]
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

    max_len = max(c["length"] for c in chroms)
    filtered = [
        c
        for c in chroms
        if c["molecule"] not in (exclude_molecules or []) and c["length"] >= min_fraction * max_len
    ]
    sorted_chroms = sorted(filtered, key=lambda x: x["length"], reverse=True)

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
    total = total_length or sum(c["length"] for c in sorted_chroms)
    for chrom in sorted_chroms:
        block = (chrom["length"] / total) * w
        x_positions.append(acc + block / 2)
        acc += block

    def fits_block(text_width, block_width, fraction=max_label_fraction):
        return text_width <= block_width * fraction

    def overlaps_prev(left_edge, right_edge, boxes, pad=0):
        return any(left_edge - pad < box_right and right_edge + pad > box_left for box_left, box_right in boxes)

    drawn_boxes = []
    for index, chrom in enumerate(sorted_chroms):
        label = str(chrom["molecule"])
        block = (chrom["length"] / total) * w
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
        block_h = (chrom["length"] / total) * h
        y_positions.append(acc_h + block_h / 2)
        acc_h += block_h

    bbox22 = font.getbbox("22")
    drawn_y_boxes: list[tuple[float, float]] = []

    def overlaps_prev_y(top_edge, bottom_edge, boxes, pad=0):
        return any(top_edge - pad < box_bottom and bottom_edge + pad > box_top for box_top, box_bottom in boxes)

    for index, chrom in enumerate(sorted_chroms):
        label = str(chrom.get(vertical_label_field) or chrom.get("molecule") or "?")
        bbox = font.getbbox(label)
        text_height = bbox[3] - bbox[1]
        text_width = bbox[2] - bbox[0]

        block_h = (chrom["length"] / total) * h
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
