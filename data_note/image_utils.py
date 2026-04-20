from __future__ import annotations

import logging
import os
from pathlib import Path

from PIL import Image


GN_ASSETS_ROOT = os.getenv(
    "DATA_NOTE_GN_ASSETS",
    os.getenv("DATA_NOTE_SERVER_DATA", str(Path.home() / "gn_assets")),
)


def convert_png_to_tif_and_gif(png_path, dpi=(300, 300), max_width=None):
    """
    Given /…/Fig_N.png, writes:
      • /…/Fig_N.tif at `dpi`
      • /…/Fig_N.gif (optionally down-scaled to max_width)
    Returns (tif_path, gif_path).
    """
    base, _ = os.path.splitext(png_path)
    img = Image.open(png_path)

    if max_width and img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    tif_path = f"{base}.tif"
    img.save(tif_path, format="TIFF", dpi=dpi)

    gif_path = f"{base}.gif"
    img.save(gif_path, format="GIF")

    logging.info(f"Converted {png_path} → {tif_path}, {gif_path}")
    return tif_path, gif_path


def resolve_open_sans_font(env_var="GENOMENOTES_FONT") -> str | None:
    """Locate an upright Open Sans font file."""
    override = os.environ.get(env_var)
    if override and Path(override).is_file():
        return override

    def pick_upright(paths):
        upright = [x for x in paths if "italic" not in x.name.lower()]
        if upright:
            return str(sorted(upright)[0])
        return str(sorted(paths)[0]) if paths else None

    user_fonts = Path.home() / "Library" / "Fonts"
    chosen = pick_upright(list(user_fonts.glob("OpenSans*.ttf")))
    if chosen:
        return chosen

    script_root = Path(__file__).resolve().parent
    pkg_dir = script_root / "assets" / "fonts"
    if pkg_dir.is_dir():
        hits = []
        for pat in ("OpenSans*.ttf", "open-sans*.ttf", "OpenSans-Regular.ttf"):
            hits.extend(pkg_dir.glob(pat))
        chosen = pick_upright(hits)
        if chosen:
            return chosen

    return None
