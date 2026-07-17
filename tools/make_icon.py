"""Рисует иконку приложения: гарнитура инженера на радио.

Векторим в большом размере и уменьшаем - так края остаются гладкими.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]

S = 1024                      # рабочий размер, потом уменьшаем
BG_DARK = (24, 26, 30, 255)
BG_EDGE = (38, 41, 47, 255)
RED = (225, 6, 0, 255)
WHITE = (240, 242, 245, 255)
GREY = (120, 126, 136, 255)


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def build() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = 24
    # Подложка: тёмный круг с красным ободом.
    d.ellipse([pad, pad, S - pad, S - pad], fill=BG_EDGE)
    d.ellipse([pad, pad, S - pad, S - pad], outline=RED, width=26)
    inner = pad + 34
    d.ellipse([inner, inner, S - inner, S - inner], fill=BG_DARK)

    cx = S // 2

    # Дуга оголовья.
    d.arc([258, 268, S - 258, S - 296], start=180, end=360, fill=WHITE,
          width=58)

    # Чашки наушников.
    cup_w, cup_h = 158, 262
    cup_y = 470
    left_x, right_x = 246, S - 246 - cup_w
    rounded(d, [left_x, cup_y, left_x + cup_w, cup_y + cup_h], 66, WHITE)
    rounded(d, [right_x, cup_y, right_x + cup_w, cup_y + cup_h], 66, WHITE)
    # Амбушюры.
    ear_pad = 46
    rounded(d, [left_x + 50, cup_y + ear_pad, left_x + 50 + 62,
                cup_y + cup_h - ear_pad], 28, RED)
    rounded(d, [right_x + 46, cup_y + ear_pad, right_x + 46 + 62,
                cup_y + cup_h - ear_pad], 28, RED)

    # Штанга микрофона: дуга от низа правой чашки вниз-влево ко рту.
    # Для arc(0..90) правая точка рамки - начало, нижняя - конец, поэтому
    # рамку считаем от этих двух точек, а не подбираем на глаз.
    start_x, start_y = right_x + cup_w // 2, cup_y + cup_h   # низ чашки
    cap_x, cap_y = 556, 872                                  # капсюль у рта
    box = [cap_x - (start_x - cap_x), start_y - (cap_y - start_y),
           start_x, cap_y]
    d.arc(box, start=0, end=90, fill=WHITE, width=30)

    r_cap = 54
    d.ellipse([cap_x - r_cap, cap_y - r_cap, cap_x + r_cap, cap_y + r_cap],
              fill=RED)

    return img


def main() -> None:
    img = build()

    out_png = ROOT / "tools" / "icon.png"
    img.resize((256, 256), Image.LANCZOS).save(out_png)

    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    out_ico = ROOT / "tools" / "icon.ico"
    img.save(out_ico, format="ICO", sizes=sizes)

    print(f"иконка: {out_ico}")
    print(f"превью: {out_png}")


if __name__ == "__main__":
    main()
