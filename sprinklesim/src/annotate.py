"""
SprinkleSim Mini — Annotation overlay.
Takes raw_render.png and adds title, metrics panel, and legend.

Usage (from project root):
    python src/annotate.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from PIL import Image, ImageDraw, ImageFont
from config import (
    DATA_JSON_PATH, RAW_RENDER_PATH, FINAL_OUTPUT_PATH,
    FIELD_WIDTH_FT, FIELD_HEIGHT_FT,
    SPRINKLER_THROW_FT, SPACING_FT,
)

ROOT = HERE.parent


def get_font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def draw_legend_swatch(draw, x, y, color_hex, label, font):
    """Draw a colored rectangle + label."""
    r = int(color_hex[1:3], 16)
    g = int(color_hex[3:5], 16)
    b = int(color_hex[5:7], 16)
    draw.rectangle([x, y, x + 28, y + 28], fill=(r, g, b))
    draw.rectangle([x, y, x + 28, y + 28], outline=(80, 80, 80), width=1)
    draw.text((x + 38, y + 4), label, fill=(40, 40, 40), font=font)


def main():
    data_path = ROOT / DATA_JSON_PATH
    raw_path  = ROOT / RAW_RENDER_PATH
    out_path  = ROOT / FINAL_OUTPUT_PATH

    with open(data_path) as f:
        data = json.load(f)

    metrics = data['metrics']
    render  = Image.open(raw_path).convert("RGB")
    rw, rh  = render.size

    HEADER_H = 110
    FOOTER_H = 90
    MARGIN   = 30

    canvas = Image.new("RGB", (rw, rh + HEADER_H + FOOTER_H), (255, 255, 255))
    canvas.paste(render, (0, HEADER_H))

    draw = ImageDraw.Draw(canvas)

    # ── Thin separator lines ──────────────────────────────────────────────────
    draw.line([(0, HEADER_H - 1), (rw, HEADER_H - 1)], fill=(200, 200, 200), width=1)
    draw.line([(0, HEADER_H + rh), (rw, HEADER_H + rh)], fill=(200, 200, 200), width=1)

    # ── Header ────────────────────────────────────────────────────────────────
    title_font    = get_font(38, bold=True)
    subtitle_font = get_font(20)
    metric_font   = get_font(22, bold=True)
    label_font    = get_font(18)
    legend_font   = get_font(17)

    draw.text((MARGIN, 18), "SprinkleSim Mini — Irrigation Coverage Analysis",
              fill=(20, 20, 20), font=title_font)

    subtitle = (
        f"Field: {FIELD_WIDTH_FT} × {FIELD_HEIGHT_FT} ft "
        f"({data['field']['area_acres']:.2f} acres)   ·   "
        f"Throw: {SPRINKLER_THROW_FT} ft   ·   "
        f"Spacing: {SPACING_FT:.0f} ft   ·   "
        f"Flow: {data['sprinkler_specs']['flow_gpm']:.1f} gpm/sprinkler"
    )
    draw.text((MARGIN, 70), subtitle, fill=(80, 80, 80), font=subtitle_font)

    # Metrics right-aligned in header
    du  = metrics['du']
    cu  = metrics['cu']
    cnt = metrics['sprinkler_count']
    du_color = (34, 139, 34) if du >= 0.75 else (200, 60, 60)
    cu_color = (34, 139, 34) if cu >= 0.85 else (200, 60, 60)

    # Right side: key numbers
    mx = rw - MARGIN
    draw.text((mx - 340, 18), f"Sprinklers: {cnt}", fill=(20, 20, 20), font=metric_font)
    draw.text((mx - 220, 18), f"DU: {du:.3f}", fill=du_color, font=metric_font)
    draw.text((mx - 110, 18), f"CU: {cu:.3f}", fill=cu_color, font=metric_font)

    du_note = "DU ≥ 0.75 target"
    cu_note = "CU ≥ 0.85 target"
    draw.text((mx - 220, 52), du_note, fill=(120, 120, 120), font=label_font)
    draw.text((mx - 110, 52), cu_note, fill=(120, 120, 120), font=label_font)

    # ── Footer ────────────────────────────────────────────────────────────────
    fy = HEADER_H + rh + 14

    # Zone percentages
    zone_text = (
        f"Under-watered: {metrics['pct_dry']:.1f}%   "
        f"Optimal: {metrics['pct_optimal']:.1f}%   "
        f"Over-watered: {metrics['pct_over']:.1f}%   "
        f"App. rate: {metrics['application_rate_min_gpm']:.0f}–"
        f"{metrics['application_rate_max_gpm']:.0f} gpm"
    )
    draw.text((MARGIN, fy), zone_text, fill=(60, 60, 60), font=label_font)

    # Legend swatches
    lx = MARGIN
    ly = fy + 36
    swatches = [
        ('#d64545', 'Under-watered (0–1 sprinklers)'),
        ('#4caf50', 'Optimal (2 sprinklers)'),
        ('#ffc107', 'Over-watered (3+ sprinklers)'),
    ]
    for color, label in swatches:
        draw_legend_swatch(draw, lx, ly, color, label, legend_font)
        lx += 330

    canvas.save(out_path)
    print(f"Final output → {out_path}")


if __name__ == "__main__":
    main()
