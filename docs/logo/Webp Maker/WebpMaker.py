"""
WebpMaker.py  -  makes the looping animated WebP (or APNG) of the logo with only the rotor turning.
Settings: WebpMaker_Parameters.py.

How it works: the rotor is rotated about ROTOR_PIVOT in a copy of the SVG for every frame, each copy is drawn by a
headless Chromium (transparent background, so text on arcs renders exactly as in a browser), and Pillow joins
the frames into one animated WebP or APNG, with full colour and soft transparent edges.  One full turn takes
360 / ROTATION_DEG_PER_SEC seconds.  The number of frames is a whole number, so the last frame leads straight into the first and the loop has no jump; when the turn does not divide
evenly into frames, the speed is rounded to the nearest whole frame count and the real speed is printed.

Needs: Python 3.9+, Pillow (pip install pillow) with WebP support, and a Chromium based browser (Chrome, Chromium or
Edge).
"""

import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

import WebpMaker_Parameters as P

HERE = Path(__file__).resolve().parent


def check_parameters():
    if not (isinstance(P.WIDTH_PX, int) and 16 <= P.WIDTH_PX <= 4096):
        sys.exit("WIDTH_PX must be a whole number from 16 to 4096")
    if not P.ROTATION_DEG_PER_SEC:
        sys.exit("ROTATION_DEG_PER_SEC must not be 0")
    if not 1 <= P.FRAMES_PER_SECOND <= 50:
        sys.exit("FRAMES_PER_SECOND must be from 1 to 50")
    if P.OUTPUT_FORMAT not in ("webp", "apng"):
        sys.exit('OUTPUT_FORMAT must be "webp" or "apng"')
    if not 1 <= P.WEBP_QUALITY <= 100:
        sys.exit("WEBP_QUALITY must be from 1 to 100")
    if not (isinstance(P.WORKERS, int) and P.WORKERS >= 1):
        sys.exit("WORKERS must be a whole number, 1 or more")


def find_browser():
    if P.BROWSER != "auto":
        if not Path(P.BROWSER).exists():
            sys.exit(f"BROWSER not found: {P.BROWSER}")
        return P.BROWSER
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    for path in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if Path(path).exists():
            return path
    sys.exit("No Chromium based browser found; install Chrome or Chromium, or set BROWSER in WebpMaker_Parameters.py")


def rotor_element(svg):
    found = re.search(r'<path id="rotor"[^>]*/>', svg)
    if not found:
        sys.exit(f'{P.SVG_FILE} has no element with id="rotor"')
    return found.group(0)


def frame_svg(svg, rotor, angle, width):
    turned = f'<g transform="rotate({angle:.4f} {P.ROTOR_PIVOT[0]} {P.ROTOR_PIVOT[1]})">{rotor}</g>'
    out = svg.replace(rotor, turned, 1)
    # the first <svg ...> tag gets the output size; the viewBox keeps the drawing in proportion
    return re.sub(r'(<svg[^>]*?)\swidth="[^"]*"\s+height="[^"]*"', rf'\1 width="{width}" height="{width}"', out, count=1)


def render(browser, svg_path, png_path, width):
    subprocess.run([browser, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    "--default-background-color=00000000", f"--window-size={width},{width}",
                    f"--screenshot={png_path}", svg_path.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    if not png_path.exists():
        sys.exit(f"The browser produced no image for {svg_path.name}")


def load_frame(png_path):
    return Image.open(png_path).convert("RGBA")


def main():
    check_parameters()
    svg_path = (HERE / P.SVG_FILE).resolve()
    svg = svg_path.read_text(encoding="utf-8")
    rotor = rotor_element(svg)
    browser = find_browser()

    turn_seconds = 360.0 / abs(P.ROTATION_DEG_PER_SEC)
    frames = max(2, round(turn_seconds * P.FRAMES_PER_SECOND))
    step = 360.0 / frames * (1 if P.ROTATION_DEG_PER_SEC > 0 else -1)
    real_speed = abs(step) * P.FRAMES_PER_SECOND
    print(f"{frames} frames, {step:+.3f} deg per frame, one turn in {frames / P.FRAMES_PER_SECOND:.2f} s "
          f"({real_speed:.2f} deg/s)")

    suffix = "webp" if P.OUTPUT_FORMAT == "webp" else "png"
    out_path = Path(P.OUTPUT_FILE) if P.OUTPUT_FILE else svg_path.with_name(
        f"{svg_path.stem}_rotor_spin_{P.WIDTH_PX}px.{suffix}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        jobs = []
        for i in range(frames):
            svg_i = tmp / f"f{i:04d}.svg"
            svg_i.write_text(frame_svg(svg, rotor, step * i, P.WIDTH_PX), encoding="utf-8")
            jobs.append((svg_i, svg_i.with_suffix(".png")))
        with ThreadPoolExecutor(max_workers=P.WORKERS) as pool:
            list(pool.map(lambda j: render(browser, j[0], j[1], P.WIDTH_PX), jobs))
        images = [load_frame(png) for _, png in jobs]

    duration = round(1000 / P.FRAMES_PER_SECOND)
    if P.OUTPUT_FORMAT == "webp":
        images[0].save(out_path, format="WEBP", save_all=True, append_images=images[1:], duration=duration, loop=0,
                       lossless=P.WEBP_LOSSLESS, quality=100 if P.WEBP_LOSSLESS else P.WEBP_QUALITY, method=4,
                       exact=True)
    else:
        images[0].save(out_path, format="PNG", save_all=True, append_images=images[1:], duration=duration, loop=0,
                       disposal=1, optimize=True)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
