#!/usr/bin/env python3
"""Ручка (задание 5, раздел 10): кончик и паста расходятся ≤ 1 px; на стыках нет бусин — проверка по пикселям.

  python polish/tools/pen.py [игра.html] [--dprs 1,1.25,1.5,2] [--size 1366x768] [--out polish/shots/P7/pen]

Сцена подписи (?screen=sign). Настоящая мышь рисует дугу и прямую на бланке. В нескольких точках, не отпуская кнопку:
  кончик — центр шарика ручки (circle в SVG) на экране; паста — ближайший закрашенный пиксель холстов .sg-ink и .sg-live
  к точке указателя. Расхождение = max(|кончик − указатель|, |паста − указатель|), в CSS-пикселях.
Бусины: вдоль прямой, проведённой с постоянной скоростью, плотность пасты по средней линии (альфа) не должна проседать
  между точками: разброс альфы < 16 из 255 (бусины при прозрачности .9 дают ≈ 25) и нет провалов ниже 230.
"""
import argparse, json, math, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]

PROBE = r"""([px, py]) => {
  const c = document.querySelector('.sg-pen circle'), b = c.getBoundingClientRect(), tip = [b.left + b.width / 2, b.top + b.height / 2];
  let best = 1e9;
  for (const cv of [document.querySelector('.sg-ink'), document.querySelector('.sg-live')]) {
    const r = cv.getBoundingClientRect(), k = cv.width / r.width, x = cv.getContext('2d');
    const cx = Math.round((px - r.left) * k), cy = Math.round((py - r.top) * k), R = Math.ceil(6 * k);
    const d = x.getImageData(cx - R, cy - R, 2 * R + 1, 2 * R + 1).data;
    for (let j = 0; j <= 2 * R; j++) for (let i = 0; i <= 2 * R; i++) if (d[(j * (2 * R + 1) + i) * 4 + 3] > 128) best = Math.min(best, Math.hypot(i - R, j - R) / k);
  }
  return { tip: Math.hypot(tip[0] - px, tip[1] - py), ink: best };
}"""
LINE = r"""([x0, y0, x1, y1]) => {
  const cv = document.querySelector('.sg-ink'), r = cv.getBoundingClientRect(), k = cv.width / r.width, x = cv.getContext('2d'), out = [];
  // плотность пасты в точке — наибольшая альфа в окне поперёк линии (±2 CSS px): край сглаживания не считается провалом
  const R = Math.ceil(2 * k);
  for (let t = .1; t <= .9; t += .01) { const px = Math.round(((x0 + (x1 - x0) * t) - r.left) * k), py = Math.round(((y0 + (y1 - y0) * t) - r.top) * k);
    const d = x.getImageData(px, py - R, 1, 2 * R + 1).data; let m = 0; for (let i = 3; i < d.length; i += 4) m = Math.max(m, d[i]); out.push(m); }
  return out;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?', default=str(ROOT / 'night-shift-4.html'))
    ap.add_argument('--dprs', default='1,1.25,1.5,2'); ap.add_argument('--size', default='1366x768')
    ap.add_argument('--out', default=str(ROOT / 'polish' / 'shots' / 'P7' / 'pen'))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    W, H = map(int, a.size.split('x')); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows, errs = [], []
    with sync_playwright() as p:
        br = p.chromium.launch()
        for d in [float(x) for x in a.dprs.split(',')]:
            ctx = br.new_context(viewport={'width': W, 'height': H}, device_scale_factor=d); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(Path(a.file).resolve().as_uri() + '?screen=sign'); pg.wait_for_selector('.sc-sign .sg-sig'); pg.wait_for_timeout(900)
            s = pg.locator('.sg-sig').bounding_box(); cx, cy, R = s['x'] + s['width'] * .5, s['y'] - 4, s['width'] * .32
            pg.mouse.move(cx - R, cy); pg.mouse.down(); worst_tip = worst_ink = 0
            for i in range(1, 41):   # дуга: полуокружность
                ang = math.pi * i / 40; x, y = cx - R * math.cos(ang), cy - R * .45 * math.sin(ang)
                pg.mouse.move(x, y, steps=2)
                if i % 5 == 0:
                    pg.wait_for_timeout(30); m = pg.evaluate(PROBE, [x, y]); worst_tip = max(worst_tip, m['tip']); worst_ink = max(worst_ink, m['ink'])
            pg.mouse.up()
            # прямая с постоянной скоростью — для бусин
            x0, y0, x1, y1 = cx - R, cy + 18, cx + R, cy + 30
            pg.mouse.move(x0, y0); pg.mouse.down(); pg.mouse.move(x1, y1, steps=40); pg.mouse.up(); pg.wait_for_timeout(50)
            al = pg.evaluate(LINE, [x0, y0, x1, y1]); spread = max(al) - min(al)
            pg.screenshot(path=str(out / f'pen@{d}.png'), clip={'x': s['x'] - R, 'y': s['y'] - 70, 'width': s['width'] + 2 * R, 'height': 140})
            rows.append((d, worst_tip, worst_ink, min(al), spread))
            print(f'DPR {d}: кончик ↔ указатель {worst_tip:.2f} px · паста ↔ указатель {worst_ink:.2f} px · прямая: альфа мин {min(al)} разброс {spread}', flush=True)
            ctx.close()
        br.close()
    ok = all(t <= 1 and i <= 1 and mn >= 230 and sp < 16 for _, t, i, mn, sp in rows)
    md = ['# Ручка: кончик, паста, бусины', '', '| DPR | кончик ↔ указатель, px | паста ↔ указатель, px | прямая: альфа мин | разброс альфы | ок |', '|---|---|---|---|---|---|']
    md += [f'| {d} | {t:.2f} | {i:.2f} | {mn} | {sp} | {"✓" if t <= 1 and i <= 1 and mn >= 230 and sp < 16 else "✗"} |' for d, t, i, mn, sp in rows]
    md += ['', 'Ошибки консоли: ' + ('нет' if not errs else '; '.join(errs[:3]))]
    (out / 'REPORT.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print('итог:', '✓' if ok else '✗', '· ошибки:', 'нет' if not errs else errs[:3])


if __name__ == '__main__':
    main()
