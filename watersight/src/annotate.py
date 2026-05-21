"""
WaterSight — side-by-side annotated comparison.
Stitches BEFORE + AFTER renders with title, stats, and legend.
"""
import sys
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import RENDER_BEFORE, RENDER_AFTER, DATA_JSON, SHOWCASE_PATH, OUTPUT_DIR

BG         = (14, 14, 18)
DIVIDER    = (40, 40, 48)
BLUE_WATER = "#1a6ea8"
RING_COLOR = "#c8a96e"
HEADER_H   = 90
FOOTER_H   = 80
DIVIDER_W  = 6


def _font(size):
    for path in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def annotate():
    with open(DATA_JSON) as f:
        data = json.load(f)

    s  = data["stats"]
    wl = data["water_levels"]

    before = Image.open(RENDER_BEFORE).convert("RGB")
    after  = Image.open(RENDER_AFTER).convert("RGB")
    W, H   = before.size   # 1920 × 1080

    # Canvas: two renders side by side + header + footer
    total_w = W * 2 + DIVIDER_W
    total_h = H + HEADER_H + FOOTER_H
    canvas  = Image.new("RGB", (total_w, total_h), BG)

    # Paste renders
    canvas.paste(before, (0, HEADER_H))
    canvas.paste(after,  (W + DIVIDER_W, HEADER_H))

    # Divider
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([W, 0, W + DIVIDER_W, total_h], fill=DIVIDER)

    # ── Header ────────────────────────────────────────────────────────────────
    title_f = _font(38)
    sub_f   = _font(20)
    draw.text((30, 14), "WaterSight — Lake Powell Drought Impact", fill="white", font=title_f)
    draw.text((32, 62), f"{data['location']['name']}  ·  "
              f"Water drop: {wl['drop_m']:.0f} m  ·  "
              f"Surface lost: {s['exposed_ring_km2']:.1f} km²  ({s['pct_water_lost']:.1f}%)",
              fill="#aaaaaa", font=sub_f)

    # ── Before / After labels ─────────────────────────────────────────────────
    label_f = _font(28)
    draw.text((30, HEADER_H + 20), f"BEFORE  ·  {wl['before_label']}",
              fill=BLUE_WATER, font=label_f)
    draw.text((W + DIVIDER_W + 30, HEADER_H + 20), f"AFTER  ·  {wl['after_label']}",
              fill=RING_COLOR, font=label_f)

    # ── Footer ────────────────────────────────────────────────────────────────
    fy      = H + HEADER_H + 14
    stat_f  = _font(22)
    leg_f   = _font(17)

    stats_text = (
        f"Before: {s['water_area_before_km2']:.1f} km²   "
        f"After: {s['water_area_after_km2']:.1f} km²   "
        f"Exposed ring: {s['exposed_ring_km2']:.1f} km²   "
        f"Drop: {wl['drop_m']:.0f} m"
    )
    draw.text((30, fy), stats_text, fill="white", font=stat_f)

    # Legend swatches
    lx = total_w - 560
    draw.rectangle([lx, fy, lx + 22, fy + 22], fill=BLUE_WATER)
    draw.text((lx + 28, fy + 3), "Open water", fill="white", font=leg_f)
    draw.rectangle([lx + 170, fy, lx + 192, fy + 22], fill=RING_COLOR)
    draw.text((lx + 198, fy + 3), "Exposed lake bed (bathtub ring)",
              fill="white", font=leg_f)

    OUTPUT_DIR.mkdir(exist_ok=True)
    canvas.save(SHOWCASE_PATH)
    print(f"  Showcase → {SHOWCASE_PATH}")


if __name__ == "__main__":
    annotate()
