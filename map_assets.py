"""Optional runtime updater for Pro Lab map images.

The app bundles Dota-like fallback diagrams. If internet is available, this module
can download a cleaner current map image and redraw the same route overlays over
that base. Pillow is used only for this optional updater.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable
import math

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from app_paths import asset_cache_dir, asset_cache_path, resource_path
from config import REQUEST_TIMEOUT

# A clean map image used in a public guide and credited there to Valve Corporation.
# If this URL ever changes, the app simply keeps using the bundled fallback maps.
MAP_SOURCE_URLS = [
    "https://hawk.live/storage/post-images/dota-2-map-guide-15100.jpg",
]

GUIDE_NAMES = [
    "carry_farm_pattern.png",
    "mid_rune_rotation.png",
    "support_vision_pattern.png",
    "offlane_pressure_pattern.png",
]

W = H = 820


def guide_image_path(name: str) -> Path:
    cached = asset_cache_path("guides", name)
    if cached.exists() and cached.stat().st_size > 2000:
        return cached
    return resource_path("ui", "assets", "guides", name)


def _font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

FONT_TITLE = _font(26, True)
FONT_BOLD = _font(17, True)


def _download_base() -> Image.Image | None:
    for url in MAP_SOURCE_URLS:
        try:
            response = requests.get(url, timeout=max(REQUEST_TIMEOUT, 15), headers={"User-Agent": "DotaCoachAI/0.9"})
            if not response.ok or len(response.content) < 10_000:
                continue
            raw = asset_cache_path("guides", "downloaded_map_source.jpg")
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(response.content)
            img = Image.open(raw).convert("RGB")
            return _square_resize(img)
        except Exception:
            continue
    return None


def _square_resize(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((W, H), Image.Resampling.LANCZOS)
    return img.convert("RGBA")


def _overlay(img: Image.Image, func: Callable[[ImageDraw.ImageDraw], None]) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    func(draw)
    return Image.alpha_composite(img, layer)


def _arrow(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], color: tuple[int, int, int, int], width: int = 8) -> None:
    draw.line(pts, fill=color, width=width, joint="curve")
    if len(pts) >= 2:
        x1, y1 = pts[-2]
        x2, y2 = pts[-1]
        ang = math.atan2(y2 - y1, x2 - x1)
        length = 22
        spread = 0.55
        left = (x2 - length * math.cos(ang - spread), y2 - length * math.sin(ang - spread))
        right = (x2 - length * math.cos(ang + spread), y2 - length * math.sin(ang + spread))
        draw.polygon([(x2, y2), left, right], fill=color)


def _label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str) -> None:
    x, y = xy
    bbox = draw.textbbox((x, y), text, font=FONT_BOLD, anchor="mm")
    pad = 7
    draw.rounded_rectangle([bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad], radius=8, fill=(10, 14, 22, 225), outline=(95, 120, 155, 200))
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=FONT_BOLD, anchor="mm")


def _title(img: Image.Image, title: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([22, 22, 798, 64], radius=15, fill=(9, 14, 22, 220), outline=(90, 112, 145, 150))
    draw.text((38, 43), title, fill=(255, 255, 255, 255), font=FONT_TITLE, anchor="lm", stroke_width=2, stroke_fill=(0, 0, 0, 210))
    return img


def _carry(base: Image.Image) -> Image.Image:
    img = base.copy().filter(ImageFilter.UnsharpMask(radius=1, percent=105, threshold=3))
    def draw(d: ImageDraw.ImageDraw) -> None:
        for rect in ([55, 500, 265, 760], [290, 435, 570, 650]):
            d.rounded_rectangle(rect, radius=32, outline=(255, 212, 49, 230), width=5, fill=(255, 210, 40, 38))
        _arrow(d, [(110, 675), (170, 604), (260, 557), (365, 518), (485, 548), (560, 498), (520, 430), (438, 470), (350, 532)], (255, 201, 44, 245), 10)
        _label(d, (156, 610), "волна")
        _label(d, (332, 518), "лес")
        _label(d, (504, 455), "треугольник")
    return _title(_overlay(img, draw), "Керри: линия → лес → треугольник")


def _mid(base: Image.Image) -> Image.Image:
    img = base.copy()
    def draw(d: ImageDraw.ImageDraw) -> None:
        _arrow(d, [(410, 430), (372, 370), (318, 308), (270, 238), (214, 195)], (85, 213, 255, 245), 8)
        _arrow(d, [(410, 430), (482, 398), (570, 350), (645, 286), (718, 238)], (184, 120, 255, 230), 8)
        d.ellipse([355, 410, 395, 450], outline=(85, 213, 255, 245), width=5)
        d.ellipse([460, 390, 500, 430], outline=(184, 120, 255, 245), width=5)
        _label(d, (380, 405), "руна")
        _label(d, (515, 348), "ганг")
        _label(d, (356, 512), "возврат")
    return _title(_overlay(img, draw), "Мид: руна → сайд → возврат в центр")


def _support(base: Image.Image) -> Image.Image:
    img = base.copy()
    def draw(d: ImageDraw.ImageDraw) -> None:
        for x, y in [(245, 455), (335, 405), (535, 440), (602, 300), (152, 570), (484, 600), (682, 520)]:
            d.ellipse([x - 54, y - 54, x + 54, y + 54], fill=(61, 142, 255, 35), outline=(111, 185, 255, 175), width=3)
            d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(255, 236, 96, 255), outline=(20, 24, 32, 255), width=2)
        _arrow(d, [(140, 650), (245, 455), (335, 405), (535, 440), (602, 300)], (91, 212, 255, 230), 7)
        _label(d, (262, 430), "вижен")
        _label(d, (530, 410), "смок")
        _label(d, (626, 285), "объект")
    return _title(_overlay(img, draw), "Саппорт: вижен до смока и объекта")


def _offlane(base: Image.Image) -> Image.Image:
    img = base.copy()
    def draw(d: ImageDraw.ImageDraw) -> None:
        for rect in ([610, 110, 770, 320], [530, 230, 725, 455]):
            d.rounded_rectangle(rect, radius=30, outline=(255, 112, 56, 220), width=5, fill=(255, 92, 50, 35))
        _arrow(d, [(690, 330), (615, 288), (555, 320), (500, 380), (535, 455), (620, 482), (700, 445)], (255, 130, 52, 245), 9)
        _label(d, (646, 292), "опасная линия")
        _label(d, (535, 385), "отход")
        _label(d, (670, 455), "TP/портал")
    return _title(_overlay(img, draw), "Оффлейн: отпушить опасную линию и выйти живым")


def update_real_map_guides() -> dict[str, str | int | bool]:
    base = _download_base()
    if base is None:
        return {"ok": False, "message": "Не удалось скачать чистую карту. Оставлены встроенные схемы.", "updated": 0}
    folder = asset_cache_dir("guides")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "base_dota_map.png").write_bytes(_to_bytes(base))
    generated = {
        "carry_farm_pattern.png": _carry(base),
        "mid_rune_rotation.png": _mid(base),
        "support_vision_pattern.png": _support(base),
        "offlane_pressure_pattern.png": _offlane(base),
    }
    for name, image in generated.items():
        image.convert("RGB").save(folder / name, quality=94)
    return {"ok": True, "message": "Карта обновлена: маршруты Pro Lab перерисованы поверх скачанной карты.", "updated": len(generated)}


def _to_bytes(img: Image.Image) -> bytes:
    import io
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
