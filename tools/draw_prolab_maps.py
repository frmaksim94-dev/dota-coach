from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import math
import random

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ui" / "assets" / "guides"
OUT.mkdir(parents=True, exist_ok=True)
W = H = 980
random.seed(7)

try:
    FONT_BIG = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    FONT_MED = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    FONT_SMALL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
except Exception:
    FONT_BIG = FONT_MED = FONT_SMALL = ImageFont.load_default()


def poly_blur(draw, pts, fill):
    draw.polygon(pts, fill=fill)


def draw_path(draw, pts, color, width, glow=True, arrows=True):
    if glow:
        for w, alpha in [(width+16, 55), (width+8, 90)]:
            draw.line(pts, fill=color[:3] + (alpha,), width=w, joint="curve")
    draw.line(pts, fill=color, width=width, joint="curve")
    if arrows:
        for a, b in zip(pts[:-1], pts[1:]):
            dx, dy = b[0]-a[0], b[1]-a[1]
            dist = (dx*dx+dy*dy)**0.5
            if dist < 85:
                continue
            t = 0.62
            x, y = a[0]+dx*t, a[1]+dy*t
            ang = math.atan2(dy, dx)
            size = width + 10
            tri = [
                (x + math.cos(ang)*size, y + math.sin(ang)*size),
                (x + math.cos(ang+2.45)*size*0.75, y + math.sin(ang+2.45)*size*0.75),
                (x + math.cos(ang-2.45)*size*0.75, y + math.sin(ang-2.45)*size*0.75),
            ]
            draw.polygon(tri, fill=color)


def label(draw, xy, text, fill=(235,245,255,255), bg=(12,18,28,220)):
    x, y = xy
    bbox = draw.textbbox((0,0), text, font=FONT_SMALL)
    pad = 8
    rect = (x, y, x + (bbox[2]-bbox[0]) + pad*2, y + (bbox[3]-bbox[1]) + pad*2)
    draw.rounded_rectangle(rect, radius=10, fill=bg, outline=(130,170,210,120), width=1)
    draw.text((x+pad, y+pad-2), text, fill=fill, font=FONT_SMALL)


def tower(draw, x, y, side="radiant", size=24):
    col = (50, 235, 95, 255) if side == "radiant" else (245, 55, 55, 255)
    outline = (5, 28, 10, 255) if side == "radiant" else (50, 5, 5, 255)
    draw.rounded_rectangle((x-size/2, y-size/2, x+size/2, y+size/2), radius=2, fill=col, outline=outline, width=3)


def camp(draw, x, y, strong=False):
    col = (220, 148, 35, 255) if not strong else (245, 186, 54, 255)
    pts = [(x, y-14), (x-13, y+13), (x+13, y+13)]
    draw.polygon(pts, fill=col, outline=(35, 22, 7, 255))
    draw.line((x, y-8, x, y+8), fill=(40,30,10,255), width=2)


def ward(draw, x, y, kind="obs"):
    col = (80, 195, 255, 255) if kind == "obs" else (255, 150, 190, 255)
    draw.ellipse((x-13,y-13,x+13,y+13), outline=(230,245,255,255), width=4)
    draw.ellipse((x-6,y-6,x+6,y+6), fill=col)


def base_map(title: str | None = None) -> Image.Image:
    img = Image.new("RGBA", (W,H), (20,24,26,255))
    d = ImageDraw.Draw(img, "RGBA")
    # Terrain blocks, closer to Dota minimap than previous black/white scheme.
    poly_blur(d, [(0,0),(670,0),(570,350),(255,365),(0,435)], (63,72,78,255))  # dire grey jungle
    poly_blur(d, [(590,0),(980,0),(980,515),(640,450),(560,350)], (92,102,112,255))  # dire snowy base
    poly_blur(d, [(0,410),(290,340),(380,610),(0,770)], (62,132,73,255))  # radiant green jungle
    poly_blur(d, [(0,725),(520,690),(980,560),(980,980),(0,980)], (36,96,48,255))  # radiant lower
    poly_blur(d, [(250,360),(575,350),(640,450),(380,610)], (52,92,110,255))  # river/center
    # River
    d.line([(0,560),(220,470),(390,455),(565,530),(760,610),(980,575)], fill=(43,129,160,210), width=82, joint="curve")
    d.line([(0,560),(220,470),(390,455),(565,530),(760,610),(980,575)], fill=(69,170,198,170), width=30, joint="curve")
    # Main lanes
    lane = (184,184,157,255)
    lane_dark = (76,74,60,255)
    lanes = [
        [(110,870),(145,650),(165,430),(210,300),(390,110),(610,92),(760,110),(860,165)],
        [(80,780),(300,650),(455,512),(604,355),(742,230),(900,87)],
        [(160,875),(360,818),(620,715),(790,620),(885,525),(920,365),(885,140)],
    ]
    for pts in lanes:
        d.line(pts, fill=lane_dark, width=42, joint="curve")
        d.line(pts, fill=lane, width=26, joint="curve")
        d.line(pts, fill=(225,222,190,160), width=7, joint="curve")
    # Jungle paths
    for pts in [[(260,275),(405,240),(545,300),(675,230),(805,245)],[(120,600),(250,520),(380,645),(520,620)],[(650,720),(760,780),(910,812)],[(690,160),(775,260),(845,360)]]:
        d.line(pts, fill=(140,138,118,185), width=15, joint="curve")
        d.line(pts, fill=(210,205,168,90), width=4, joint="curve")
    # Trees/rocks
    for i in range(170):
        # biome weighted points
        if random.random() < 0.52:
            x=random.randint(0,980); y=random.choice([random.randint(0,330), random.randint(650,980)])
        else:
            x=random.randint(0,980); y=random.randint(0,980)
        green = y > 430 or x < 310
        if green:
            col=random.choice([(20,82,42,210),(28,110,48,200),(70,138,68,190),(22,61,37,220)])
        else:
            col=random.choice([(88,32,26,210),(112,35,32,205),(64,70,72,190),(45,52,54,210)])
        r=random.randint(13,34)
        d.ellipse((x-r,y-r,x+r,y+r), fill=col)
    # bases
    d.rounded_rectangle((35,790,165,940), radius=24, fill=(28,148,70,225), outline=(132,245,158,255), width=4)
    d.rounded_rectangle((790,35,945,185), radius=24, fill=(133,27,44,225), outline=(255,158,158,255), width=4)
    label(d,(52,910),"Radiant")
    label(d,(835,42),"Dire")
    # Roshan pit
    d.ellipse((66,96,126,156), outline=(210,235,245,255), width=5)
    d.arc((52,82,140,170), 15, 340, fill=(110,145,175,255), width=4)
    label(d,(42,160),"Рошан")
    # Towers
    for x,y in [(165,490),(300,620),(505,738),(730,650),(830,525),(875,365),(775,220),(610,145),(385,140),(288,260),(455,300),(610,375),(210,770),(332,745)]:
        side = "radiant" if (x+y>980 or x<360 and y>390) else "dire"
        tower(d,x,y,side)
    # Camps
    camps = [(110,315),(170,590),(260,510),(320,470),(435,405),(495,485),(610,500),(690,565),(770,410),(820,315),(690,160),(575,95),(260,135),(130,740),(340,820),(625,790),(750,805),(880,760)]
    for i,(x,y) in enumerate(camps):
        camp(d,x,y, strong=i%5==0)
    # rune/lotus/portals
    for x,y in [(450,500),(600,480),(105,845),(880,135),(870,850),(120,125)]:
        ward(d,x,y,"obs")
    # soft vignette and border
    overlay = Image.new("RGBA", (W,H), (0,0,0,0))
    od = ImageDraw.Draw(overlay, "RGBA")
    od.rectangle((0,0,W,H), outline=(112,154,205,255), width=6)
    od.rounded_rectangle((12,12,W-12,H-12), radius=24, outline=(50,72,105,220), width=4)
    img.alpha_composite(overlay)
    if title:
        d.rounded_rectangle((22,20,740,70), radius=14, fill=(8,13,22,230), outline=(88,122,170,180))
        d.text((38,27), title, font=FONT_BIG, fill=(255,255,255,255), stroke_width=2, stroke_fill=(0,0,0,180))
    return img


def save_pattern(filename, title, routes, labels, wards=None):
    img = base_map(title)
    d = ImageDraw.Draw(img, "RGBA")
    # route glows over base map
    for pts, color, width in routes:
        draw_path(d, pts, color, width)
    if wards:
        for x,y,kind in wards:
            ward(d,x,y,kind)
    for xy,text,bg in labels:
        label(d, xy, text, bg=bg)
    img = img.convert("RGB")
    img.save(OUT/filename, quality=92)


# base without overlays for future route drawing/replacement
base_map().convert("RGB").save(OUT/"dota_map_base.png", quality=92)
base_map().convert("RGB").save(OUT/"base_dota_like_map.png", quality=92)

save_pattern(
    "carry_farm_pattern.png",
    "Керри: безопасный фарм",
    [([(105,735),(205,650),(315,605),(450,535),(590,560),(695,610),(805,700)], (255,211,58,245), 12),
     ([(295,615),(255,500),(300,390),(430,370)], (255,159,45,230), 8)],
    [((92,720),"волна",(22,72,36,230)),((330,588),"лес",(12,18,28,230)),((612,585),"треугольник",(92,66,10,235)),((690,725),"уход после пуша",(12,18,28,230))],
    wards=[(455,500,"obs"),(235,520,"obs")]
)

save_pattern(
    "mid_rune_rotation.png",
    "Мид: руна → сайд → центр",
    [([(492,495),(360,450),(220,475),(155,565)], (70,190,255,245), 11),
     ([(492,495),(620,455),(740,370),(850,300)], (255,126,70,245), 11),
     ([(850,300),(735,225),(612,190),(510,240),(492,495)], (200,110,255,210), 8)],
    [((455,505),"центр",(12,18,28,230)),((200,420),"руна/сайд",(10,58,86,230)),((745,332),"ганк",(90,35,28,230)),((565,210),"возврат к пачке",(42,28,80,230))],
    wards=[(390,440,"obs"),(600,450,"obs"),(750,310,"obs")]
)

save_pattern(
    "support_vision_pattern.png",
    "Саппорт: вижен под объект",
    [([(170,650),(300,550),(420,505),(585,480),(760,430)], (83,225,142,245), 10),
     ([(250,720),(360,640),(500,600),(680,610),(820,690)], (255,88,105,225), 8)],
    [((120,655),"смок",(22,72,36,230)),((350,482),"вард до драки",(8,47,79,230)),((675,405),"объект",(80,28,28,230)),((650,635),"сентри на подход",(70,35,70,230))],
    wards=[(335,455,"obs"),(545,470,"obs"),(690,425,"obs"),(615,610,"sen"),(770,540,"sen")]
)

save_pattern(
    "offlane_pressure_pattern.png",
    "Оффлейн: давление опасной линии",
    [([(825,250),(760,330),(700,415),(620,500),(535,590),(420,665)], (255,105,58,245), 12),
     ([(700,415),(770,455),(845,520),(880,640)], (255,210,60,225), 9)],
    [((742,295),"давить линию",(80,28,28,230)),((585,515),"выход в лес",(12,18,28,230)),((385,650),"соединиться",(22,72,36,230)),((805,555),"не стой после пуша",(76,54,12,230))],
    wards=[(690,410,"obs"),(775,455,"obs"),(610,525,"sen")]
)
