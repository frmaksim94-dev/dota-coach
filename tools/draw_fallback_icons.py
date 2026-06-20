from __future__ import annotations

import hashlib
import math
import random
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dota_catalog import HERO_ROWS, ITEM_GROUPS, slugify  # noqa: E402

hero_dir = ROOT / "ui" / "assets" / "catalog" / "heroes"
item_dir = ROOT / "ui" / "assets" / "catalog" / "items"
hero_dir.mkdir(parents=True, exist_ok=True)
item_dir.mkdir(parents=True, exist_ok=True)

try:
    FONT_SMALL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    FONT_TINY = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)
    FONT_BIG = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
except Exception:
    FONT_SMALL = FONT_TINY = FONT_BIG = ImageFont.load_default()

ATTR_COLORS = {
    "str": ((148, 38, 26), (255, 122, 60), (82, 15, 12)),
    "agi": ((28, 106, 55), (106, 238, 112), (8, 50, 35)),
    "int": ((35, 80, 150), (92, 198, 255), (16, 28, 82)),
    "all": ((90, 54, 145), (255, 170, 74), (30, 20, 70)),
}

def hnum(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest()[:8], 16)

def gradient(w,h,c1,c2):
    img=Image.new('RGB',(w,h),c1)
    pix=img.load()
    for y in range(h):
        for x in range(w):
            t=(x/w*0.65+y/h*0.35)
            pix[x,y]=tuple(int(c1[i]*(1-t)+c2[i]*t) for i in range(3))
    return img.convert('RGBA')

def draw_hero(name, attr):
    w,h=120,68
    c1,c2,c3=ATTR_COLORS.get(attr,ATTR_COLORS['all'])
    img=gradient(w,h,c1,c3)
    d=ImageDraw.Draw(img,'RGBA')
    seed=hnum(name); rng=random.Random(seed)
    # diagonal cinematic light
    for i in range(-30,160,16):
        d.line((i,0,i-50,h), fill=c2+(45,), width=8)
    # shoulders/body
    body_col=tuple(max(0,min(255,int(v*rng.uniform(0.65,1.25)))) for v in c2)
    d.ellipse((w*0.33,h*0.38,w*0.75,h*1.18), fill=body_col+(170,))
    d.polygon([(w*0.48,h*0.18),(w*0.66,h*0.42),(w*0.56,h*0.62),(w*0.36,h*0.58),(w*0.28,h*0.36)], fill=(18,22,31,190))
    # face/glow
    skin=random.choice([(221,176,128),(164,92,68),(130,170,210),(125,225,165),(210,105,105),(195,170,230)])
    d.ellipse((w*0.38,h*0.16,w*0.58,h*0.48), fill=skin+(225,), outline=(255,255,255,75), width=2)
    # eyes/mark
    d.line((w*0.42,h*0.30,w*0.47,h*0.29), fill=(255,255,220,230), width=2)
    d.line((w*0.51,h*0.29,w*0.56,h*0.30), fill=(255,255,220,230), width=2)
    # fantasy silhouette detail
    if seed % 4 == 0:
        d.polygon([(w*0.36,h*0.18),(w*0.22,2),(w*0.42,h*0.24)], fill=(230,230,255,130))
    elif seed % 4 == 1:
        d.arc((w*0.24,0,w*0.67,h*0.54), 200, 350, fill=(255,230,150,150), width=5)
    elif seed % 4 == 2:
        d.line((w*0.62,h*0.18,w*0.90,h*0.02), fill=(255,240,160,160), width=5)
    else:
        d.ellipse((w*0.30,h*0.05,w*0.68,h*0.52), outline=(120,220,255,120), width=4)
    # vignette and border
    d.rounded_rectangle((1,1,w-2,h-2), radius=6, outline=(255,255,255,90), width=2)
    d.rectangle((0,h-18,w,h), fill=(5,8,12,165))
    initials=''.join([part[0] for part in name.replace("'",'').split()[:2]]).upper()
    d.text((6,h-17), initials, font=FONT_TINY, fill=(255,255,255,240))
    return img.convert('RGB')

ITEM_COLORS = {
    'Consumables': ((45,105,55),(110,225,105)),
    'Attributes': ((94,70,150),(205,156,255)),
    'Basic': ((70,83,104),(180,204,230)),
    'Early Game': ((98,70,38),(245,167,72)),
    'Core Damage': ((120,34,30),(255,88,62)),
    'Defense and Utility': ((30,82,125),(82,194,255)),
    'Neutral Items': ((100,68,28),(255,216,90)),
}

def draw_item(name, category):
    w=h=72
    c1,c2=ITEM_COLORS.get(category,((60,65,85),(180,190,220)))
    img=gradient(w,h,c1,tuple(max(0,x-70) for x in c1))
    d=ImageDraw.Draw(img,'RGBA')
    seed=hnum(name); rng=random.Random(seed)
    d.rounded_rectangle((3,3,w-4,h-4), radius=12, outline=c2+(200,), width=3)
    # gem/weapon abstract icon
    cx,cy=w//2,h//2
    shape=seed%5
    if shape==0:
        pts=[(cx,8),(w-12,cy),(cx,h-8),(12,cy)]
        d.polygon(pts, fill=c2+(210,), outline=(255,255,255,160))
    elif shape==1:
        d.line((15,h-15,w-15,15), fill=c2+(220,), width=9)
        d.polygon([(w-20,10),(w-4,4),(w-10,24)], fill=(255,245,190,210))
    elif shape==2:
        d.ellipse((14,12,w-14,h-12), fill=c2+(130,), outline=(255,255,255,180), width=4)
        d.ellipse((27,25,w-27,h-25), fill=(255,255,255,150))
    elif shape==3:
        d.rounded_rectangle((16,14,w-16,h-14), radius=8, fill=c2+(160,), outline=(255,255,255,120), width=3)
        d.line((20,cy,w-20,cy), fill=(255,255,255,130), width=3)
    else:
        for a in range(0,360,60):
            x=cx+math.cos(math.radians(a))*22; y=cy+math.sin(math.radians(a))*22
            d.line((cx,cy,x,y), fill=c2+(180,), width=5)
        d.ellipse((cx-12,cy-12,cx+12,cy+12), fill=(255,255,255,170))
    # category marker
    d.rectangle((0,h-15,w,h), fill=(4,7,12,170))
    initials=''.join(part[0] for part in name.replace("'",'').split()[:2]).upper()
    d.text((5,h-14), initials, font=FONT_TINY, fill=(255,255,255,240))
    return img.convert('RGB')

for name, attr, roles in HERO_ROWS:
    path=hero_dir / f"{slugify(name)}.png"
    # Do not overwrite real downloaded art.
    if not path.with_suffix(path.suffix+'.real').exists():
        draw_hero(name, attr).save(path, quality=88, optimize=True)

for category, names in ITEM_GROUPS.items():
    for name in names:
        path=item_dir / f"{slugify(name)}.png"
        if not path.with_suffix(path.suffix+'.real').exists():
            draw_item(name, category).save(path, quality=88, optimize=True)
print('fallback icons written')
