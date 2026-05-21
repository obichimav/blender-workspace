"""
AgriKit — annotate.py
Composites the three renders into a showcase image with title/legend overlay.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT   = Path(__file__).resolve().parent.parent
OUT    = ROOT / "output"
HERO   = OUT / "render_hero.png"
AERIAL = OUT / "render_aerial.png"
ASSETS = OUT / "render_assets.png"
FINAL  = OUT / "showcase.png"

ASSETS_LIST = [
    "Grain Silo × 2",
    "Red Gambrel Barn",
    "Water Tower",
    "Greenhouse",
    "Center Pivot Irrigator",
    "Round Hay Bales",
]

W_FULL = 1920
H_FULL = 1080
W_SMALL = 640
H_SMALL = 360
BAR_H = 60
TOTAL_W = W_FULL
TOTAL_H = H_FULL + H_SMALL + BAR_H * 2


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


def main():
    canvas = Image.new("RGB", (TOTAL_W, TOTAL_H), (18, 20, 24))
    draw = ImageDraw.Draw(canvas)

    # ── Hero render (full width, top) ─────────────────────────────────────────
    if HERO.exists():
        hero = Image.open(HERO).resize((W_FULL, H_FULL), Image.LANCZOS)
        canvas.paste(hero, (0, 0))
    else:
        draw.rectangle([0, 0, W_FULL, H_FULL], fill=(40, 40, 50))
        draw.text((W_FULL // 2, H_FULL // 2), "Hero render missing",
                  fill=(200, 200, 200), font=_font(32), anchor="mm")

    # ── Title bar ─────────────────────────────────────────────────────────────
    bar_y = H_FULL
    draw.rectangle([0, bar_y, TOTAL_W, bar_y + BAR_H], fill=(10, 12, 16))
    draw.text((24, bar_y + BAR_H // 2),
              "AgriKit — Modular Agricultural Asset Pack · Blender 5.1 · Polyhaven PBR Textures · Cycles",
              fill=(220, 220, 220), font=_font(20), anchor="lm")

    # ── Bottom row: aerial + assets + legend ──────────────────────────────────
    row_y = bar_y + BAR_H

    for path, x in [(AERIAL, 0), (ASSETS, W_SMALL)]:
        if path.exists():
            img = Image.open(path).resize((W_SMALL, H_SMALL), Image.LANCZOS)
            canvas.paste(img, (x, row_y))
        else:
            draw.rectangle([x, row_y, x + W_SMALL, row_y + H_SMALL], fill=(40, 40, 50))

    # Label overlays on thumbnails
    for label, x in [("Aerial", 8), ("Asset Overview", W_SMALL + 8)]:
        draw.text((x, row_y + 8), label, fill=(255, 255, 255),
                  font=_font(16), stroke_width=2, stroke_fill=(0, 0, 0))

    # Legend panel
    legend_x = W_SMALL * 2
    legend_w = TOTAL_W - legend_x
    draw.rectangle([legend_x, row_y, TOTAL_W, row_y + H_SMALL], fill=(22, 25, 30))

    draw.text((legend_x + 20, row_y + 14), "Included Assets",
              fill=(180, 200, 240), font=_font(18))
    draw.line([legend_x + 20, row_y + 36, TOTAL_W - 20, row_y + 36],
              fill=(60, 70, 90), width=1)

    for i, asset in enumerate(ASSETS_LIST):
        ay = row_y + 50 + i * 46
        # Bullet dot
        draw.ellipse([legend_x + 20, ay + 4, legend_x + 30, ay + 14],
                     fill=(100, 160, 220))
        draw.text((legend_x + 42, ay), asset,
                  fill=(210, 215, 225), font=_font(16))

    # ── Footer bar ────────────────────────────────────────────────────────────
    foot_y = row_y + H_SMALL
    draw.rectangle([0, foot_y, TOTAL_W, foot_y + BAR_H], fill=(10, 12, 16))
    draw.text((TOTAL_W // 2, foot_y + BAR_H // 2),
              "All PBR textures CC0 via Polyhaven  ·  github.com/obichimav/blender-workspace",
              fill=(120, 130, 145), font=_font(14), anchor="mm")

    canvas.save(FINAL)
    print(f"Showcase saved → {FINAL}")


if __name__ == "__main__":
    main()
