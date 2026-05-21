"""
ForestWatch — annotate.py

Composites six year renders into a showcase grid with:
  • 2×3 render grid (one cell per year)
  • Forest loss bar chart on the right
  • Title + data source footer
  • Animated GIF saved alongside showcase PNG
"""
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT   = Path(__file__).resolve().parent.parent
OUT    = ROOT / "output"
DATA   = ROOT / "data"
YEARS  = [2018, 2019, 2020, 2021, 2022, 2023]

THUMB_W, THUMB_H = 560, 315
COLS, ROWS_GRID  = 3, 2
CHART_W          = 340
BAR_H            = 60
FOOTER_H         = 46

TOTAL_W = COLS * THUMB_W + CHART_W
TOTAL_H = ROWS_GRID * THUMB_H + BAR_H + FOOTER_H

YEAR_COLS = {
    2018: (40, 160, 60),
    2019: (80, 170, 40),
    2020: (160, 160, 20),
    2021: (190, 100, 15),
    2022: (200, 55, 10),
    2023: (200, 25, 5),
}


def _font(size):
    for name in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/Library/Fonts/Arial.ttf",
    ]:
        if Path(name).exists():
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_bar_chart(draw, stats, x0, y0, w, h):
    max_forest = max(s["forest_km2"] for s in stats)
    bar_w = int((w - 60) / len(stats))
    draw.text((x0 + w // 2, y0 + 14), "Forest Cover km²",
              fill=(200, 220, 200), font=_font(16), anchor="mm")

    for i, s in enumerate(stats):
        bx = x0 + 30 + i * bar_w
        bar_height = int((s["forest_km2"] / max_forest) * (h - 60))
        by = y0 + h - 30 - bar_height
        col = YEAR_COLS[s["year"]]
        draw.rectangle([bx + 4, by, bx + bar_w - 4, y0 + h - 30], fill=col)
        draw.text((bx + bar_w // 2, y0 + h - 16), str(s["year"]),
                  fill=(180, 190, 180), font=_font(13), anchor="mm")
        draw.text((bx + bar_w // 2, by - 10), f"{s['forest_km2']:.0f}",
                  fill=(200, 220, 200), font=_font(11), anchor="mm")


def main():
    stats_path = DATA / "stats.json"
    stats = json.loads(stats_path.read_text()) if stats_path.exists() else []

    canvas = Image.new("RGB", (TOTAL_W, TOTAL_H), (14, 18, 14))
    draw = ImageDraw.Draw(canvas)

    # ── Title bar ─────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, TOTAL_W, BAR_H], fill=(8, 12, 8))
    draw.text((20, BAR_H // 2),
              "ForestWatch — Amazon Deforestation · Rondônia, Brazil · 2018–2023 · NDVI + Blender Cycles",
              fill=(180, 210, 180), font=_font(18), anchor="lm")

    # ── Year renders grid ─────────────────────────────────────────────────────
    gif_frames = []
    for idx, year in enumerate(YEARS):
        col_i = idx % COLS
        row_i = idx // COLS
        px = col_i * THUMB_W
        py = BAR_H + row_i * THUMB_H

        render = OUT / f"render_{year}.png"
        if render.exists():
            img = Image.open(render).resize((THUMB_W, THUMB_H), Image.LANCZOS)
        else:
            img = Image.new("RGB", (THUMB_W, THUMB_H), (30, 40, 30))
            ImageDraw.Draw(img).text((THUMB_W // 2, THUMB_H // 2),
                                     f"{year} — missing", fill=(150, 200, 150),
                                     font=_font(22), anchor="mm")
        canvas.paste(img, (px, py))
        gif_frames.append(img.copy())

        # Year label overlay
        col = YEAR_COLS[year]
        year_draw = ImageDraw.Draw(canvas)
        year_draw.rectangle([px, py, px + 90, py + 32], fill=(10, 14, 10))
        year_draw.text((px + 8, py + 6), str(year),
                       fill=col, font=_font(20))

        # Forest loss annotation
        if stats:
            s = next((x for x in stats if x["year"] == year), None)
            if s:
                label = f"Forest: {s['forest_pct']:.0f}%"
                year_draw.text((px + THUMB_W - 6, py + 6), label,
                               fill=(200, 240, 200), font=_font(14), anchor="ra",
                               stroke_width=2, stroke_fill=(10, 14, 10))

        # Grid lines
        draw.rectangle([px, py, px + THUMB_W - 1, py + THUMB_H - 1],
                       outline=(40, 60, 40), width=1)

    # ── Bar chart panel ────────────────────────────────────────────────────────
    chart_x = COLS * THUMB_W
    chart_y = BAR_H
    draw.rectangle([chart_x, chart_y, TOTAL_W, chart_y + ROWS_GRID * THUMB_H],
                   fill=(18, 24, 18))
    if stats:
        draw_bar_chart(draw, stats, chart_x + 10, chart_y + 20,
                       CHART_W - 20, ROWS_GRID * THUMB_H - 40)

        # Net loss summary
        lost = stats[0]["forest_km2"] - stats[-1]["forest_km2"]
        pct  = 100 * lost / stats[0]["forest_km2"]
        draw.text((chart_x + CHART_W // 2, chart_y + ROWS_GRID * THUMB_H - 55),
                  f"Net loss: {lost:.0f} km² ({pct:.1f}%)",
                  fill=(220, 80, 60), font=_font(15), anchor="mm")

    # ── Footer ────────────────────────────────────────────────────────────────
    fy = BAR_H + ROWS_GRID * THUMB_H
    draw.rectangle([0, fy, TOTAL_W, TOTAL_H], fill=(8, 12, 8))
    draw.text((TOTAL_W // 2, fy + FOOTER_H // 2),
              "Synthetic NDVI modelled on Rondônia fishbone deforestation pattern  ·  "
              "github.com/obichimav/blender-workspace",
              fill=(100, 130, 100), font=_font(13), anchor="mm")

    canvas.save(OUT / "showcase.png")
    print(f"Showcase saved → {OUT / 'showcase.png'}")

    # ── Animated GIF ──────────────────────────────────────────────────────────
    if gif_frames:
        gif_path = OUT / "deforestation_timelapse.gif"
        # Scale down for GIF file size
        gif_small = [f.resize((THUMB_W, THUMB_H), Image.LANCZOS) for f in gif_frames]
        gif_small[0].save(
            gif_path,
            save_all=True,
            append_images=gif_small[1:],
            duration=1200,    # ms per frame
            loop=0,
        )
        print(f"Animated GIF → {gif_path}")


if __name__ == "__main__":
    main()
