"""
Сервер приложения «0-90 календарь».

Что делает:
  GET /              — страница: форма, превью, ссылка, инструкция для «Команд»
  GET /api/cal?birth=2000-01-01
                     — PNG-обои 1170x2532 (iPhone 13) на ТЕКУЩИЙ день.
                       Именно эту ссылку вставляют в приложение «Команды»:
                       автоматизация скачивает её каждый день, а сервер
                       каждый раз считает недели заново, поэтому раз в неделю
                       маркер-логотип сдвигается на следующую точку.
  GET /api/health    — проверка, что сервер жив

Параметры совместимы с форматом оригинального сервиса
(type, theme, lang, lifespan, w, h, fs принимаются, но игнорируются:
 фон всегда светло-голубой, размер всегда под iPhone 13).

Запуск:  python app.py           (порт из переменной PORT, по умолчанию 8000)
Часовой пояс для подсчёта «сегодня»: переменная TZ_NAME, по умолчанию Europe/Moscow.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from wallpaper import parse_date, wallpaper_bytes

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "static" / "index.html"
LOGO_PATH = BASE_DIR / "assets" / "logo.png"

# --- «Сегодня» в нужном часовом поясе (важно: сервер может стоять в UTC) ---
def today_local() -> date:
    tz_name = os.environ.get("TZ_NAME", "Europe/Moscow")
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(tz_name)).date()
    except Exception:
        return date.today()


# --- Кэш готовых обоев: ключ (дата рождения, дата расчёта) ------------------
_cache: dict[tuple[str, str], bytes] = {}
_cache_lock = threading.Lock()


def get_wallpaper(birth: date, today: date) -> bytes:
    key = (birth.isoformat(), today.isoformat())
    with _cache_lock:
        if key in _cache:
            return _cache[key]
    png = wallpaper_bytes(birth, today)
    with _cache_lock:
        _cache.clear()  # даты расчёта старые больше не нужны — держим только свежие
        _cache[key] = png
    return png


class Handler(BaseHTTPRequestHandler):
    server_version = "LifeCal090/1.0"

    # ---------- вспомогательное ----------
    def _send(self, code: int, body: bytes, content_type: str,
              extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - сигнатура родителя
        print(f"{self.address_string()} {format % args}")

    # ---------- маршруты ----------
    def do_GET(self) -> None:  # noqa: N802 - API http.server
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in ("/", "/index.html"):
            body = INDEX_PATH.read_bytes()
            self._send(200, body, "text/html; charset=utf-8",
                       {"Cache-Control": "no-cache"})
            return

        if path == "/assets/logo.png":
            self._send(200, LOGO_PATH.read_bytes(), "image/png",
                       {"Cache-Control": "public, max-age=86400"})
            return

        if path == "/api/health":
            self._json(200, {"ok": True, "today": today_local().isoformat()})
            return

        if path == "/api/cal":
            self._wallpaper_route(parse_qs(parsed.query))
            return

        self._json(404, {"error": "not found"})

    do_HEAD = do_GET

    def _wallpaper_route(self, query: dict[str, list[str]]) -> None:
        birth_raw = (query.get("birth") or [""])[0]
        if not birth_raw:
            self._json(400, {"error": "Нужен параметр birth=YYYY-MM-DD, "
                                      "например /api/cal?birth=2000-01-01"})
            return
        try:
            birth = parse_date(birth_raw)
            if birth.year < 1900:
                raise ValueError("Слишком ранняя дата рождения")
        except ValueError as exc:
            self._json(400, {"error": f"Некорректная дата рождения: {exc}"})
            return

        # ?date=YYYY-MM-DD — только для ручной проверки (неделя в прошлом/будущем).
        # Приложение «Команды» этот параметр не передаёт — берётся сегодняшний день.
        date_raw = (query.get("date") or [""])[0]
        try:
            today = parse_date(date_raw) if date_raw else today_local()
        except ValueError:
            self._json(400, {"error": "Некорректный параметр date"})
            return

        try:
            png = get_wallpaper(birth, today)
        except ValueError as exc:  # дата рождения в будущем и т.п.
            self._json(400, {"error": str(exc)})
            return

        headers = {
            # Без кэша: «Командам» и iOS всегда нужна свежая картинка,
            # иначе обои перестанут сдвигаться по неделям.
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        }
        if (query.get("download") or [""])[0] == "1":
            headers["Content-Disposition"] = \
                f'attachment; filename="life-0-90_{birth.isoformat()}.png"'
        self._send(200, png, "image/png", headers)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"«0-90 календарь» запущен: http://0.0.0.0:{port}/  (сегодня: {today_local()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановка сервера")


if __name__ == "__main__":
    main()
