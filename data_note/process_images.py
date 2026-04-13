#!/usr/bin/env python

import os
import logging
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

from .process_chromosome_data import extract_chromosomes_only


SERVER_DATA = os.getenv("DATA_NOTE_SERVER_DATA", str(Path.home() / "server_data"))



def convert_png_to_tif_and_gif(png_path, dpi=(300,300), max_width=None):
    """
    Given /…/Fig_N.png, writes:
      • /…/Fig_N.tif  at `dpi`
      • /…/Fig_N.gif  (optionally down‐scaled to max_width)
    Returns (tif_path, gif_path).
    These image conversions are needed for JATS XML submission, which requires TIFF for high-quality print and GIF for web display.
    """
    base, _ = os.path.splitext(png_path)
    img = Image.open(png_path)

    # optional resize to max_width
    if max_width and img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # TIFF
    tif_path = f"{base}.tif"
    img.save(tif_path, format="TIFF", dpi=dpi)

    # GIF
    gif_path = f"{base}.gif"
    img.save(gif_path, format="GIF")

    logging.info(f"Converted {png_path} → {tif_path}, {gif_path}")
    return tif_path, gif_path



def copy_gscope_image(tolid, download_dir):
    # Fetch the specified GenomeScope plot, write .png, then auto-produce .tif & .gif.
    script_dir = Path(__file__).resolve().parent
    gscope_dir = Path(SERVER_DATA) / "gscope_results" / f"{tolid}" 

    # Old and new naming conventions
    candidates = [
        gscope_dir / f"{tolid}.k31_linear_plot.png",        # old style
        gscope_dir / "fastk_genomescope_linear_plot.png"    # new style, without tolid in name
    ]

    src_path = None
    for candidate in candidates:
        if candidate.exists():
            src_path = candidate
            break

    if not src_path:
        logging.error(f"GenomeScope image not found for {tolid} in {gscope_dir}")
        return None

    try:
        download_dir_path = Path(download_dir)
        download_dir_path.mkdir(parents=True, exist_ok=True)

        png_path = download_dir_path / "Fig_2_Gscope.png"
        png_path.write_bytes(src_path.read_bytes())
        logging.info(f"Copied GenomeScope plot to {png_path}")

        tif_path, gif_path = convert_png_to_tif_and_gif(
            str(png_path),
            dpi=(300, 300),
            max_width=800
        )
        return png_path, Path(tif_path), Path(gif_path)

    except Exception as e:
        logging.error(f"Error handling GenomeScope image: {e}")
        return None



def copy_merqury_image(tolid, download_dir):
    # Fetch the specified Merqury result image, write .png, then auto-produce .tif & .gif.
    script_dir = Path(__file__).resolve().parent
    merqury_dir = Path(SERVER_DATA) / "merqury_results" / f"{tolid}" 

    # Old and new naming conventions
    candidates = [
        merqury_dir / f"{tolid}.spectra-asm.ln.png",      # standard style
        merqury_dir / f"{tolid}.spectra-cn.ln.png",       # alternative style
        merqury_dir / "fastk_merqury_linear_plot.png"     # new style, without tolid in name
    ]

    src_path = None
    for candidate in candidates:
        if candidate.exists():
            src_path = candidate
            break

    if not src_path:
        logging.error(f"Merqury image not found for {tolid} in {merqury_dir}")
        return None

    try:
        download_dir_path = Path(download_dir)
        download_dir_path.mkdir(parents=True, exist_ok=True)

        png_path = download_dir_path / "Fig_4_Merqury.png"
        png_path.write_bytes(src_path.read_bytes())
        logging.info(f"Copied Merqury plot to {png_path}")

        tif_path, gif_path = convert_png_to_tif_and_gif(
            str(png_path),
            dpi=(300, 300),
            max_width=800
        )
        return png_path, Path(tif_path), Path(gif_path)

    except Exception as e:
        logging.error(f"Error handling Merqury image: {e}")
        return None



def resolve_open_sans_font(env_var="GENOMENOTES_FONT") -> str | None:
    """Locate an *upright* Open Sans font file.
    Preference order:
      1. $GENOMENOTES_FONT (explicit override)
      2. ~/Library/Fonts/OpenSans*.ttf (Homebrew / Font Book user install) **excluding Italic**
      3. vendored project_root/assets/fonts/OpenSans*.ttf (non-italic if available)
    Falls back to any OpenSans*.ttf if only Italic is found.
    Returns a string path or None if nothing found.
    """
    import os
    from pathlib import Path

    # 1. explicit override
    p = os.environ.get(env_var)
    if p and Path(p).is_file():
        return p

    # helper to pick first non-italic from list of paths
    def pick_upright(paths):
        upright = [x for x in paths if "italic" not in x.name.lower()]
        if upright:
            return str(sorted(upright)[0])
        return str(sorted(paths)[0]) if paths else None

    # 2. user fonts (Homebrew install ends up here)
    user_fonts = Path.home() / "Library" / "Fonts"
    hits = list(user_fonts.glob("OpenSans*.ttf"))
    chosen = pick_upright(hits)
    if chosen:
        return chosen

    # 3. vendored copy in repo assets
    script_root = Path(__file__).resolve().parent.parent
    pkg_dir = script_root / "assets" / "fonts"
    if pkg_dir.is_dir():
        hits = []
        for pat in ("OpenSans*.ttf", "open-sans*.ttf", "OpenSans-Regular.ttf"):
            hits.extend(pkg_dir.glob(pat))
        chosen = pick_upright(hits)
        if chosen:
            return chosen

    return None


def add_mbp_scale(draw, font, left, top, w, h, total_length, font_size, text_colour):
    """Add Mbp scale to bottom of pretext map with smart positioning"""
    
    # Calculate reasonable tick intervals based on total genome size
    if total_length <= 50:
        tick_interval = 10  # Every 10 Mbp
    elif total_length <= 200:
        tick_interval = 25  # Every 25 Mbp
    elif total_length <= 500:
        tick_interval = 50  # Every 50 Mbp
    elif total_length <= 1000:
        tick_interval = 100  # Every 100 Mbp
    elif total_length <= 2000:
        tick_interval = 200  # Every 200 Mbp
    else:
        tick_interval = 500  # Every 500 Mbp for very large genomes
    
    # === NEW: Check for label crowding and adjust interval ===
    # Estimate how many labels we'd have with current interval
    estimated_label_count = int(total_length / tick_interval) + 1
    
    # Estimate average space per label (in pixels)
    avg_space_per_label = w / estimated_label_count if estimated_label_count > 0 else w
    
    # Estimate typical 3-digit label width (e.g., "1000")
    sample_bbox = font.getbbox("1000")
    typical_label_width = sample_bbox[2] - sample_bbox[0]
    
    # If labels would be too crowded, increase interval
    min_space_needed = typical_label_width * 1.5  # 50% padding between labels
    
    if avg_space_per_label < min_space_needed:
        # Labels would overlap - increase interval
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
        
        logging.info(f"[Mbp Scale] Adjusted interval from original to {tick_interval} Mbp to prevent label crowding")
    
    # Draw scale line
    scale_y = top + h + int(font_size * 0.5)
    draw.line([(left, scale_y), (left + w, scale_y)], fill=text_colour, width=2)
    
    # Pre-calculate the last tick that would get a label
    current_pos = 0
    tick_count = 0
    last_labeled_tick = None
    
    while current_pos <= total_length:
        # Check if this tick would get a label
        if tick_count % (1 if tick_interval >= 50 else 2) == 0:
            x_pos = left + (current_pos / total_length) * w
            label = f"{int(current_pos)}"
            bbox = font.getbbox(label)
            label_width = bbox[2] - bbox[0]
            last_labeled_tick = (x_pos, label, label_width, current_pos)
        
        current_pos += tick_interval
        tick_count += 1
    
    # Calculate "Mbp" unit label dimensions
    unit_label = "Mbp"
    unit_bbox = font.getbbox(unit_label)
    unit_width = unit_bbox[2] - unit_bbox[0]
    
    # Determine optimal "Mbp" position
    min_gap = 15  # Minimum gap between labels
    right_margin_start = left + w  # End of the actual image
    ideal_mbp_x = right_margin_start + 15  # 15 pixels into the right margin
    
    skip_last_label = False
    final_mbp_x = ideal_mbp_x
    
    if last_labeled_tick:
        last_x, last_label, last_width, last_value = last_labeled_tick
        last_label_right = last_x + last_width/2
        
        # Check if right-aligned "Mbp" would overlap
        if ideal_mbp_x - min_gap < last_label_right:
            # Try positioning "Mbp" just after the last label with gap
            alt_mbp_x = last_label_right + min_gap
            
            # If there's enough space for this positioning, use it
            if alt_mbp_x + unit_width <= left + w + 20:  # Allow slight overflow into right margin
                final_mbp_x = alt_mbp_x
            else:
                # Not enough space - skip the last numerical label and use right-aligned "Mbp"
                skip_last_label = True
                final_mbp_x = ideal_mbp_x
    
    # Draw all tick marks and labels
    current_pos = 0
    tick_count = 0
    
    while current_pos <= total_length:
        x_pos = left + (current_pos / total_length) * w
        
        # Draw tick mark
        tick_height = font_size // 4
        draw.line([(x_pos, scale_y), (x_pos, scale_y + tick_height)], 
                 fill=text_colour, width=2)
        
        # Add label (every other tick for readability if interval is small)
        if tick_count % (1 if tick_interval >= 50 else 2) == 0:
            label = f"{int(current_pos)}"
            bbox = font.getbbox(label)
            label_width = bbox[2] - bbox[0]
            
            # Skip the last tick label if we determined it should be skipped
            is_last_labeled_tick = (last_labeled_tick and 
                                  current_pos == last_labeled_tick[3] and 
                                  skip_last_label)
            
            if not is_last_labeled_tick:
                draw.text((x_pos - label_width/2, scale_y + tick_height + font_size//6), 
                         label, font=font, fill=text_colour)
        
        current_pos += tick_interval
        tick_count += 1
    
    # Add "Mbp" unit label at the calculated position
    draw.text((final_mbp_x, scale_y + tick_height + font_size//6), 
             unit_label, font=font, fill=text_colour)



def label_pretext_map(
    tolid: str,
    context: dict,
    output_dir: str,
    font_path: str | None = None, 
    font_size: int = 60,
    exclude_molecules: list = None,
    min_fraction: float = 0.01,
    background_colour: str = "white",
    text_colour: str = "black",
    vertical_label_field: str = "INSDC"
) -> tuple[Path,Path,Path]:
    """
    1) Find server_data/pretext_images/{tolid}*.png
    2) Extract chrom-list + genome length from context
    3) Draw labels
    4) Save Fig_3_Pretext.png/.tif/.gif in output_dir
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # === 1) locate source folder by absolute path ===
    # Resolve font if not explicitly supplied.
    if font_path is None:
        font_path = resolve_open_sans_font()
        if font_path is None:
            font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"  # fallback
    script_root = Path(__file__).resolve().parent.parent
    pretext_dir = Path(SERVER_DATA) / "pretext_images"
    logging.debug(f"[Pretext] Looking in {pretext_dir} for files named {tolid}*.png")

    matches = list(pretext_dir.glob(f"{tolid}*.png"))
    if not matches:
        logging.error(f"[Pretext] No .png files found for {tolid} in {pretext_dir}")
        return None

    src_png = matches[0]
    logging.info(f"[Pretext] Found source PNG: {src_png}")

    # === 2) build chromosome_list & total_length ===
    if "prim_accession" in context:
        chroms = extract_chromosomes_only(context["prim_accession"])
    elif "hap1_accession" in context:
        chroms = extract_chromosomes_only(context["hap1_accession"])
    else:
        logging.error(f"[Pretext] No accession in context for {tolid}")
        return None

    raw_len = context.get("genome_length_unrounded") or context.get("hap1_genome_length_unrounded")
    total_length = (raw_len / 1e6) if raw_len else None
    logging.debug(f"[Pretext] total_length={total_length} Mb; chromosomes={len(chroms)}")

    # === 3) draw labels  ===
    img = Image.open(src_png)
    w, h = img.size
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        logging.warning(f"[Pretext] Could not load font {font_path}, using default")
        font = ImageFont.load_default()

    MAX_LABEL_FRACTION = 0.97
    DOT_WIDTH = font.getbbox(".")[2] - font.getbbox(".")[0]

    max_len = max(c["length"] for c in chroms)
    filtered = [c for c in chroms
                if c["molecule"] not in (exclude_molecules or [])
                   and c["length"] >= min_fraction * max_len]
    sorted_chroms = sorted(filtered, key=lambda x: x["length"], reverse=True)

    # === Dynamically scale font size based on label density ===
    base_font_size = font_size  # e.g. 60 (default from function argument)
    chrom_count = len(sorted_chroms)

    # Define maximum allowed font size for extremely sparse assemblies
    max_font_size = 90

    # Heuristic: fewer chromosomes → more space per label → scale up
    if chrom_count > 25:
        font_size = base_font_size
    elif chrom_count > 20:
        font_size = min(max_font_size, base_font_size + 5)
    elif chrom_count > 10:
        font_size = min(max_font_size, base_font_size + 10)
    else:
        font_size = min(max_font_size, base_font_size + 20)

    logging.info(f"[Pretext] Adjusted font size: {font_size} for {chrom_count} chromosomes")

    top    = int(font_size * 2.5)
    left   = int(font_size * 7)
    bottom = int(font_size * 2.5)
    right  = int(font_size * 2.5)

    canvas = Image.new("RGB", (w+left+right, h+top+bottom), background_colour)
    canvas.paste(img, (left, top))
    draw = ImageDraw.Draw(canvas)

    acc = 0
    x_positions = []
    total = total_length or sum(c["length"] for c in sorted_chroms)
    for c in sorted_chroms:
        block = (c["length"]/total)*w
        x_positions.append(acc + block/2)
        acc += block

    def fits_block(tw, block_width, fraction=MAX_LABEL_FRACTION):
        return tw <= block_width * fraction

    def overlaps_prev(l, r, boxes, pad=0):
        return any(l - pad < br and r + pad > bl for bl, br in boxes)

    # top labels
    drawn_boxes = []
    for i, c in enumerate(sorted_chroms):
        label = str(c["molecule"])
        block = (c["length"] / total) * w
        bbox = font.getbbox(label)
        tw   = bbox[2] - bbox[0]

        ok = fits_block(tw, block)
        if ok:
            x_left = left + x_positions[i] - tw/2
            x_right = x_left + tw
            if overlaps_prev(x_left, x_right, drawn_boxes):
                ok = False

        if ok:
            y = int(font_size * 0.6)
            draw.text((x_left, y), label, font=font, fill=text_colour)
            drawn_boxes.append((x_left, x_right))
        else:
            x = left + x_positions[i] - DOT_WIDTH/2
            y = int(font_size * 0.4)
            draw.text((x, y), ".", font=font, fill=text_colour)

    # side labels (vertical axis)
    # Dynamic: draw label if it fits the vertical "chromosome" block; otherwise draw a dot.
    # Rationale: many taxa (birds, fish) have a steep drop from macro- to microchromosomes.
    # We use the *length-derived block height* to decide if a label fits, mirroring the top-axis logic.

    # Pre-compute vertical centres by length scaling to image height (like x_positions but for y).
    y_positions = []
    acc_h = 0
    for c in sorted_chroms:
        block_h = (c["length"] / total) * h
        y_positions.append(acc_h + block_h / 2)
        acc_h += block_h

    # Cache a nominal text height (use cap-height surrogate).
    # Using "22" tends to give a reliable bounding box for numerals + ascenders.
    bbox22 = font.getbbox("22")
    nominal_th = bbox22[3] - bbox22[1]

    # Boxes of previously-drawn vertical labels: (top, bottom) pixel coords.
    drawn_y_boxes: list[tuple[float, float]] = []

    def overlaps_prev_y(t, b, boxes, pad=0):
        return any(t - pad < bb and b + pad > tt for tt, bb in boxes)

    for i, c in enumerate(sorted_chroms):
        lbl = str(c.get(vertical_label_field) or c.get("molecule") or "?")

        # Measure label height precisely for this string.
        lb = font.getbbox(lbl)
        th = lb[3] - lb[1]
        tw = lb[2] - lb[0]

        block_h = (c["length"] / total) * h
        centre_y = top + y_positions[i]
        y_top = int(centre_y - th / 2 - font_size * 0.4)
        y_bot = y_top + th

        # Decide whether we can draw or now: must fit the block and not clash with a previously drawn label.
        ok = block_h >= th * MAX_LABEL_FRACTION  # enough vertical room?
        if ok and overlaps_prev_y(y_top, y_bot, drawn_y_boxes, pad=5):
            ok = False

        if ok:
            x = left - tw - int(font_size * 0.4)  
            draw.text((x, y_top), lbl, font=font, fill=text_colour)
            drawn_y_boxes.append((y_top, y_bot))
        else:
            # Draw a dot centred on the block to mark presence
            dot_bbox = font.getbbox(".")
            dot_top = dot_bbox[1]
            dot_height = dot_bbox[3] - dot_bbox[1]
            x = left - DOT_WIDTH - int(font_size * 0.4)
            y_dot = int(centre_y - (dot_height / 2) - dot_top)
            draw.text((x, y_dot), ".", font=font, fill=text_colour)

    if total_length:  # Only add scale if we have length data
        add_mbp_scale(draw, font, left, top, w, h, total_length, font_size, text_colour)

    # === 4) save + convert ===
    out_png = output_dir / "Fig_3_Pretext.png"
    canvas.save(out_png)
    logging.info(f"[Pretext] Saved labelled PNG → {out_png}")

    tif, gif = convert_png_to_tif_and_gif(str(out_png), dpi=(300,300), max_width=1200)
    logging.info(f"[Pretext] Converted to TIFF & GIF → {tif}, {gif}")

    return out_png, Path(tif), Path(gif)


def download_btk_images(accession, download_dir):
    """
    Download BlobToolKit images for specific accession and save them to a directory.
    """
    # Define the base URL and image types
    base_api_url = f"https://blobtoolkit.genomehubs.org/api/v1/image/{accession}"
    image_types = {
        "snail": "Fig_5_Snail.png",
        "blob": "Fig_6_Blob.png"
    }

    image_paths = []

    # Loop through each image type and download it
    for image_type, file_name in image_types.items():
        # Snail: prefer the viewer's PNG download (fixes incorrect static image),
        # fall back to the static API if needed.
        if image_type == "snail":
            if download_btk_snail_from_viewer(accession, download_dir, output_name=file_name):
                image_paths.append(file_name)
                continue

        url = f"{base_api_url}/{image_type}?format=png"
        file_path = os.path.join(download_dir, file_name)

        print(f"Downloading {image_type} from {url} to {file_name}")

        # Use curl to fetch the image
        curl_command = [
            "curl", "-X", "GET", url,
            "-H", "accept: image/png",
            "-o", file_path
        ]

        try:
            result = subprocess.run(curl_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                # Read a small portion of the file to check for error text.
                with open(file_path, "r", errors="ignore") as f:
                    snippet = f.read(100)
                if "Not Found" in snippet:
                    print("Static image not found")  # if the static image is not found at the URL
                    os.remove(file_path)
                else:
                    print(f"Downloaded: {file_name}")
                    image_paths.append(file_name)
            else:
                print(f"Failed to download {file_name}. Response: {result.stderr}")
        except Exception as e:
            print(f"Error downloading {image_type}: {e}")

    return image_paths


def download_btk_snail_from_viewer(accession, download_dir, output_name="Fig_5_Snail.png", timeout_ms=60000, headless=True) -> bool:
    """
    Use the BlobToolKit viewer's PNG download button to fetch the correct snail plot.
    Returns True on success, False otherwise.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
    except Exception as e:
        logging.warning(f"Playwright not available for viewer download: {e}")
        return False

    url = f"https://blobtoolkit.genomehubs.org/view/{accession}/dataset/{accession}/snail#Filters"
    out_dir = Path(download_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page(viewport={"width": 1600, "height": 1200})
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_timeout(2000)

            # Find all visible PNG download links; pick the rightmost one (main plot toolbar).
            png_locator = page.locator("a:has-text('png')")
            count = png_locator.count()
            if count == 0:
                browser.close()
                logging.warning("No PNG download links found on viewer page.")
                return False

            best_idx = None
            best_x = -1
            best_y = 10**9
            for i in range(count):
                box = png_locator.nth(i).bounding_box()
                if not box:
                    continue
                x = box.get("x", -1)
                y = box.get("y", 10**9)
                if x > best_x or (x == best_x and y < best_y):
                    best_x = x
                    best_y = y
                    best_idx = i

            if best_idx is None:
                browser.close()
                logging.warning("PNG links found but none were visible/clickable.")
                return False

            try:
                with page.expect_download(timeout=10000) as dl_info:
                    png_locator.nth(best_idx).click()
                download = dl_info.value
            except PWTimeoutError:
                browser.close()
                logging.warning("Clicking PNG link did not trigger a download.")
                return False

            download.save_as(str(out_path))
            browser.close()
            logging.info(f"Downloaded BTK snail via viewer → {out_path}")
            return True

    except Exception as e:
        logging.warning(f"Viewer-based snail download failed: {e}")
        return False


def download_and_process_btk(accession, output_dir, dpi=(300,300), max_width=1200):
    # calls your existing download_btk_images to get the PNGs
    png_list = download_btk_images(accession, output_dir)

    # then loops over each PNG and calls convert_png_to_tif_and_gif
    processed = []
    for png in png_list:
        png_path = Path(output_dir) / png
        tif, gif = convert_png_to_tif_and_gif(str(png_path), dpi=dpi, max_width=max_width)
        processed.append((png_path, Path(tif), Path(gif)))
    return processed


def copy_merian_image(tolid, download_dir):
    """
    Locate and copy the Merian plot image from server_data/merian/{tolid}/ to the output directory
    with a standard name Fig_3_Merian.png, then auto-produce .tif and .gif.
    Returns (png_path, tif_path, gif_path).
    """
    merian_dir = Path(SERVER_DATA) / "merian" / tolid
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
    png_path = download_dir_path / "Fig_3_Merian.png"

    try:
        png_path.write_bytes(src_path.read_bytes())
        logging.info(f"Copied Merian image to {png_path}")

        # generate TIFF + GIF
        tif_path, gif_path = convert_png_to_tif_and_gif(
            str(png_path),
            dpi=(300,300),
            max_width=1200
        )

        return png_path, Path(tif_path), Path(gif_path)

    except Exception as e:
        logging.error(f"Error copying Merian image for {tolid}: {e}")
        return None


if __name__ == "__main__":
    # Minimal standalone call to label one pretext map
    label_pretext_map(
        tolid="ilDryDodo1",
        context={"hap1_accession": "GCA_965178025.1"},
        output_dir=str(Path.cwd()),
    )
