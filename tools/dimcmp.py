#!/usr/bin/env python3
"""Сравнение силы фокус-света: смена 1, первый шаг показа при трёх значениях FEEL.focus.dim (?dim=…).

  python polish/tools/dimcmp.py   → polish/shots/P2/focus-dim-compare.jpg (запускать из корня проекта)
"""
from playwright.sync_api import sync_playwright
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io
game = Path('night-shift-4.html').resolve().as_uri()
shots = []
with sync_playwright() as p:
    br = p.chromium.launch(); pg = br.new_page(viewport={"width": 1366, "height": 768})
    for d in ['0.45', '0.6', '0.75']:
        pg.goto(game + f'?moment=guide&dim={d}'); pg.wait_for_timeout(1400)
        shots.append((d, Image.open(io.BytesIO(pg.screenshot()))))
    br.close()
W, H = 1366, 768; sc = 0.62; w, h = int(W * sc), int(H * sc)
out = Image.new('RGB', (w, (h + 46) * 3), '#111412'); dr = ImageDraw.Draw(out)
try: f = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 26)
except Exception: f = ImageFont.load_default()
names = {'0.45': 'тень 45 %, слабее', '0.6': 'тень 60 %, как сейчас', '0.75': 'тень 75 %, сильнее'}
for i, (d, im) in enumerate(shots):
    y = i * (h + 46)
    dr.text((14, y + 8), f'?dim={d} — {names[d]}', fill='#EDE8DA', font=f)
    out.paste(im.resize((w, h)), (0, y + 46))
out.save('polish/shots/P2/focus-dim-compare.jpg', quality=88)
print('ok')
