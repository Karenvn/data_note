from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from .image_utils import convert_png_to_tif_and_gif


def download_btk_images(accession, download_dir, output_names=None):
    """Download BlobToolKit images for a specific accession."""
    base_api_url = f"https://blobtoolkit.genomehubs.org/api/v1/image/{accession}"
    image_types = output_names or {
        "snail": "Fig_5_Snail.png",
        "blob": "Fig_6_Blob.png",
    }

    image_paths = []
    for image_type, file_name in image_types.items():
        if image_type == "snail":
            if download_btk_snail_from_viewer(accession, download_dir, output_name=file_name):
                image_paths.append(file_name)
                continue

        url = f"{base_api_url}/{image_type}?format=png"
        file_path = os.path.join(download_dir, file_name)

        curl_command = [
            "curl",
            "-X",
            "GET",
            url,
            "-H",
            "accept: image/png",
            "-o",
            file_path,
        ]

        try:
            result = subprocess.run(curl_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, "r", errors="ignore") as handle:
                    snippet = handle.read(100)
                if "Not Found" in snippet:
                    os.remove(file_path)
                else:
                    image_paths.append(file_name)
            else:
                logging.warning(f"Failed to download {file_name}. Response: {result.stderr}")
        except Exception as exc:
            logging.warning(f"Error downloading {image_type}: {exc}")

    return image_paths


def download_btk_snail_from_viewer(
    accession,
    download_dir,
    output_name="Fig_5_Snail.png",
    timeout_ms=60000,
    headless=True,
) -> bool:
    """Use the BlobToolKit viewer's PNG download button to fetch the correct snail plot."""
    try:
        from playwright.sync_api import TimeoutError as PWTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        logging.warning(f"Playwright not available for viewer download: {exc}")
        return False

    url = f"https://blobtoolkit.genomehubs.org/view/{accession}/dataset/{accession}/snail#Filters"
    out_dir = Path(download_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_name

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            page = browser.new_page(viewport={"width": 1600, "height": 1200})
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_timeout(2000)

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
    except Exception as exc:
        logging.warning(f"Viewer-based snail download failed: {exc}")
        return False


def download_and_process_btk(accession, output_dir, output_names=None, dpi=(300, 300), max_width=1200):
    """Download BTK PNGs and convert them to TIFF/GIF variants."""
    png_list = download_btk_images(accession, output_dir, output_names=output_names)
    processed = []
    for png in png_list:
        png_path = Path(output_dir) / png
        tif, gif = convert_png_to_tif_and_gif(str(png_path), dpi=dpi, max_width=max_width)
        processed.append((png_path, Path(tif), Path(gif)))
    return processed
