"""
CropSight — PIL annotation overlay.
Adds title header + NDVI metrics footer + zone legend to the raw render.
"""
import sys
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import RAW_RENDER_PATH, DATA_JSON_PATH, FINAL_OUTPUT_PATH, OUTPUT_DIR


ZONE_COLORS_PIL = {
    0: "#c0392b",
    1: "#f39c12",
    2: "#27ae60",
}
ZONE_LABELS = {0: "Stressed", 1: "Moderate", 2: "Healthy"}

HEADER_H = 100
FOOTER_H = 90
BG_COLOR = (18, 18, 18)


def _font(size):
    for name in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def annotate():
    with open(DATA_JSON_PATH) as f:
        data = json.load(f)

    m   = data["metrics"]
    reg = data["region"]

    img = Image.open(RAW_RENDER_PATH).convert("RGB")
    W, H = img.size

    canvas = Image.new("RGB", (W, H + HEADER_H + FOOTER_H), BG_COLOR)
    canvas.paste(img, (0, HEADER_H))
    draw = ImageDraw.Draw(canvas)

    # ── Header ────────────────────────────────────────────────────────────────
    title_font  = _font(36)
    sub_font    = _font(18)

    draw.text((30, 18), "CropSight — NDVI Crop Health Visualizer",
              fill="white", font=title_font)
    draw.text((32, 66), f"{reg['name']}  ·  {reg['date_range']}  ·  "
              f"NDVI mean: {m['ndvi_mean']:.3f}  ·  {data['source']}",
              fill="#aaaaaa", font=sub_font)

    # ── Footer ────────────────────────────────────────────────────────────────
    fy = H + HEADER_H + 12
    metric_font = _font(22)
    label_font  = _font(16)

    metrics_text = (
        f"NDVI min: {m['ndvi_min']:.3f}   "
        f"max: {m['ndvi_max']:.3f}   "
        f"std: {m['ndvi_std']:.3f}"
    )
    draw.text((30, fy), metrics_text, fill="white", font=metric_font)

    # Zone legend swatches
    swatch_x = W - 480
    for i, zone in enumerate((0, 1, 2)):
        sx = swatch_x + i * 155
        draw.rectangle([sx, fy, sx + 22, fy + 22],
                       fill=ZONE_COLORS_PIL[zone])
        pct = {0: m["pct_stressed"], 1: m["pct_moderate"], 2: m["pct_healthy"]}[zone]
        draw.text((sx + 28, fy + 3),
                  f"{ZONE_LABELS[zone]} {pct:.1f}%",
                  fill="white", font=label_font)

    OUTPUT_DIR.mkdir(exist_ok=True)
    canvas.save(FINAL_OUTPUT_PATH)
    print(f"  Final output → {FINAL_OUTPUT_PATH}")


if __name__ == "__main__":
    annotate()
