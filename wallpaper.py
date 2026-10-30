"""
Генератор обоев «0-90 календарь» для iPhone 13 (1170x2532).

Каждая точка — одна неделя жизни.
Сетка: 52 недели (колонки) x 90 лет (строки) = 4680 недель.
Тёмные точки — прожитые недели, белые — оставшиеся,
текущая неделя отмечена вашим логотипом (assets/logo.png).

Использование из командной строки:
    python wallpaper.py --birth 2000-01-01 --out wallpaper.png
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo.png"
FONT_REGULAR = BASE_DIR / "assets" / "fonts" / "DejaVuSans.ttf"
FONT_BOLD = BASE_DIR / "assets" / "fonts" / "DejaVuSans-Bold.ttf"

# ---------- Фиксированные настройки (без кастомизации, как в ТЗ) ----------
WIDTH, HEIGHT = 1170, 2532          # iPhone 13 / 13 Pro
LIFESPAN_YEARS = 90
WEEKS_PER_YEAR = 52
TOTAL_WEEKS = LIFESPAN_YEARS * WEEKS_PER_YEAR  # 4680

BG_COLOR = (174, 225, 249)           # светло-голубой фон  #AEE1F9
PAST_COLOR = (30, 74, 102)           # прожитые недели    #1E4A66
FUTURE_COLOR = (255, 255, 255)       # оставшиеся недели  #FFFFFF
TEXT_COLOR = (20, 58, 82)            # подписи            #143A52

# Размер логотипа-маркера текущей недели в пикселях готовых обоев.
# Одна точка сетки ~12 px — в таком размере текст логотипа не читается,
# поэтому логотип рисуется укрупнённо и накрывает несколько соседних точек.
# Если нужен маркер поменьше/побольше — меняйте только эту цифру.
MARKER_SIZE = 12

# Геометрия сетки: сверху оставляем место под часы/дату экрана блокировки,
# снизу — под процент, фразу и кнопки фонарика/камеры.
GRID_LEFT = 145
GRID_RIGHT = WIDTH - 145
GRID_TOP = 640

SUPERSAMPLE = 2  # рисуем в 2 раза крупнее и уменьшаем — гладкие точки и текст


@dataclass
class LifeStats:
    birth: date
    today: date
    end: date               # birth + 90 лет
    days_lived: int
    weeks_lived: int        # сколько полных недель прожито
    current_index: int      # индекс текущей недели в сетке (0..4679)
    total_weeks: int
    percent: float          # точный процент по дням (для подписи)


def add_years(d: date, years: int) -> date:
    """Дата + N лет; 29 февраля -> 28 февраля, если целевой год не високосный."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def parse_date(value: str) -> date:
    return date.fromisoformat(value.strip())


def life_stats(birth: date, today: date, lifespan: int = LIFESPAN_YEARS) -> LifeStats:
    if birth > today:
        raise ValueError("Дата рождения не может быть в будущем")
    end = add_years(birth, lifespan)
    total_weeks = lifespan * WEEKS_PER_YEAR
    days_lived = (today - birth).days
    total_days = max((end - birth).days, 1)
    weeks_lived = min(days_lived // 7, total_weeks)
    # Текущая неделя — первая ещё не завершённая; после 90 лет остаётся последняя.
    current_index = min(weeks_lived, total_weeks - 1)
    percent = min(max(days_lived / total_days * 100, 0.0), 100.0)
    return LifeStats(
        birth=birth,
        today=today,
        end=end,
        days_lived=days_lived,
        weeks_lived=weeks_lived,
        current_index=current_index,
        total_weeks=total_weeks,
        percent=percent,
    )


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def render_wallpaper(birth: date, today: date | None = None,
                       lifespan: int = LIFESPAN_YEARS) -> Image.Image:
    """Собирает обои 1170x2532 для даты рождения на указанный день."""
    today = today or date.today()
    stats = life_stats(birth, today, lifespan)

    s = SUPERSAMPLE
    w, h = WIDTH * s, HEIGHT * s
    img = Image.new("RGBA", (w, h), BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    cols = WEEKS_PER_YEAR
    rows = lifespan
    step_x = (GRID_RIGHT - GRID_LEFT) * s / (cols - 1)
    step_y = step_x  # квадратный шаг — сетка не растянута
    dot_r = 6 * s
    grid_top = GRID_TOP * s
    grid_left = GRID_LEFT * s
    grid_bottom = grid_top + step_y * (rows - 1)

    # ---- Точки-недели -----------------------------------------------------
    # В календарном году 52 недели + 1-2 дня, поэтому реальных недель за 90 лет
    # чуть больше, чем 4680 клеток сетки. Чтобы логотип не исчезал раньше
    # 90-летия, в самом конце он просто остаётся на последней клетке.
    finished = stats.today >= stats.end
    current_xy: tuple[float, float] | None = None
    for idx in range(stats.total_weeks):
        row, col = divmod(idx, cols)
        cx = grid_left + col * step_x
        cy = grid_top + row * step_y
        if idx == stats.current_index and not finished:
            current_xy = (cx, cy)  # вместо точки здесь будет логотип
            continue
        color = PAST_COLOR if (finished or idx < stats.current_index) else FUTURE_COLOR
        draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), fill=color)

    # ---- Текущая неделя: ваш логотип вместо кружка -----------------------
    if current_xy is not None:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        target = MARKER_SIZE * s
        scale = target / max(logo.size)
        logo = logo.resize(
            (max(1, round(logo.width * scale)), max(1, round(logo.height * scale))),
            Image.LANCZOS,
        )
        px = round(current_xy[0] - logo.width / 2)
        py = round(current_xy[1] - logo.height / 2)
        # Не даём логотипу уехать за края обоев (первая/последняя недели, углы).
        px = min(max(px, 0), w - logo.width)
        py = min(max(py, 0), h - logo.height)
        # Никакой подложки: логотип просто занимает место обычной точки.
        img.alpha_composite(logo, (px, py))

    # ---- Подписи под сеткой ----------------------------------------------
    percent_font = _font(FONT_REGULAR, 36 * s)
    phrase_font = _font(FONT_BOLD, 46 * s)

    percent_text = f"{stats.percent:.1f}% to {lifespan}"
    percent_y = grid_bottom + 58 * s
    draw.text((w / 2, percent_y), percent_text, font=percent_font,
              fill=TEXT_COLOR, anchor="mm")

    phrase_y = percent_y + 88 * s
    draw.text((w / 2, phrase_y), "ДЕЙСТВУЙ СЕЙЧАС", font=phrase_font,
              fill=TEXT_COLOR, anchor="mm")
    draw.text((w / 2, phrase_y + 60 * s), "У ТЕБЯ ЕЩЁ ЕСТЬ ВРЕМЯ", font=phrase_font,
              fill=TEXT_COLOR, anchor="mm")

    return img.convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)


def wallpaper_bytes(birth: date, today: date | None = None,
                      lifespan: int = LIFESPAN_YEARS) -> bytes:
    """PNG-байты обоев — то, что отдаёт API приложению «Команды»."""
    import io

    buf = io.BytesIO()
    render_wallpaper(birth, today, lifespan).save(buf, format="PNG", optimize=True)
    return buf.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Обои «0-90 календарь» для iPhone 13")
    parser.add_argument("--birth", required=True, help="Дата рождения, например 2000-01-01")
    parser.add_argument("--out", default="wallpaper.png", help="Куда сохранить PNG")
    parser.add_argument("--date", help="Необязательно: дата, на которую считать (для тестов)")
    args = parser.parse_args()

    birth = parse_date(args.birth)
    today = parse_date(args.date) if args.date else date.today()
    stats = life_stats(birth, today)
    render_wallpaper(birth, today).save(args.out)
    print(f"Готово: {args.out} | неделя {stats.current_index + 1} из {stats.total_weeks}, "
          f"прожито {stats.weeks_lived} недель ({stats.percent:.1f}% to {LIFESPAN_YEARS})")
