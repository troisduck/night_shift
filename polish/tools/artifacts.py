#!/usr/bin/env python3
"""Охота на артефакты (задание 5, раздел 2.2): одинаковое состояние разными путями должно давать одинаковый кадр.

  python polish/tools/artifacts.py [игра.html] [--out polish/shots/P7/art] [--states play1,play5,play9]
                                   [--sizes 1920x1080,1366x768,1024x768] [--dprs 1,1.25,1.5,2] [--checks static,resize,dpr]

Проверки (кадры на паузе, с prefers-reduced-motion — без пыли и мерцания, чтобы живое не мешало сравнению):
  static — два кадра с разницей 1 с: всё, что изменилось без причины (перепечка, прыжок тени);
  resize — свежая загрузка в размере B против загрузки в размере A и смены окна на B посреди смены:
           разница — запечённое не перепеклось (класс «а» и «д»);
  dpr    — свежая загрузка с масштабом устройства D против загрузки с 1 и смены масштаба на D через CDP
           (Emulation.setDeviceMetricsOverride), как масштаб страницы или перенос на другой монитор (класс «г»).
Порог: пиксель «другой», если яркость отличается больше чем на 10 из 255. Итог — доля таких пикселей и
карта разницы <проверка>-<состояние>-<размер>@<dpr>-diff.png (красным — где отличается) в --out, сводка — REPORT.md.
Секундомер, часы, мигание табло и ленты самописцев живут сами — их область вырезается из сравнения (MASK).
"""
import argparse, json, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]

STATES = {
    'play1': 'level=1&paused=1',
    'play3': 'level=3&paused=1',
    'play5': 'level=5&paused=1',
    'play9': 'level=9&paused=1',
    'alarm': 'unlockall=1&event=alarm_test',
}
# живые места, которые меняются сами: часы, ленты самописцев, окно в город (огни мачт), табло (мигание неквитированных)
MASK = ['#clock', '.clock', '#charts', '#window', '#ann', '.ann', '#gl-pz', '.pz-hint', '#m-text']   # #m-text: лист Палыча выходит на свет, пока он говорит, — живое
THR = 10


def diff(a, b):
    import numpy as np
    from PIL import Image
    ia, ib = Image.open(a).convert('L'), Image.open(b).convert('L')
    if ia.size != ib.size:   # снимок после CDP-подмены масштаба бывает в CSS-пикселях — сравниваем в меньшем размере
        sz = min(ia.size, ib.size); ia, ib = ia.resize(sz, Image.LANCZOS), ib.resize(sz, Image.LANCZOS)
        # пересэмплирование даёт разницу по кромкам текста и рамок — её гасит лёгкое размытие; сдвинутая тень или фактура (площадь) остаётся
        from PIL import ImageFilter
        ia, ib = ia.filter(ImageFilter.GaussianBlur(2)), ib.filter(ImageFilter.GaussianBlur(2))
    A = np.asarray(ia, dtype=np.int16); B = np.asarray(ib, dtype=np.int16)
    m = np.abs(A - B) > THR
    return m, float(m.mean() * 100)


def masked(page, path):
    page.evaluate("""(sel) => { for (const s of sel) document.querySelectorAll(s).forEach(e => e.style.visibility = 'hidden'); }""", MASK)
    page.screenshot(path=str(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?', default=str(ROOT / 'night-shift-4.html'))
    ap.add_argument('--out', default=str(ROOT / 'polish' / 'shots' / 'P7' / 'art'))
    ap.add_argument('--states', default='play1,play5,play9')
    ap.add_argument('--sizes', default='1920x1080,1366x768,1024x768')
    ap.add_argument('--dprs', default='1,1.25,1.5,2')
    ap.add_argument('--checks', default='static,resize,dpr')
    ap.add_argument('--settle', type=int, default=1800, help='мс после смены размера или масштаба до кадра')
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    import numpy as np
    from PIL import Image
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); tmp = out / '_tmp'; tmp.mkdir(exist_ok=True)
    url = Path(a.file).resolve().as_uri()
    sizes = [tuple(map(int, s.split('x'))) for s in a.sizes.split(',')]
    dprs = [float(x) for x in a.dprs.split(',')]
    checks = a.checks.split(',')
    rows, errors = [], []

    def save_diff(m, base, name):
        im = Image.open(base).convert('RGB')
        if im.size != (m.shape[1], m.shape[0]): im = im.resize((m.shape[1], m.shape[0]))
        img = np.asarray(im).copy() // 3
        img[m] = [255, 40, 40]
        Image.fromarray(img).save(out / f'{name}-diff.png')

    with sync_playwright() as p:
        br = p.chromium.launch()

        def load(q, W, H, d):
            ctx = br.new_context(viewport={'width': W, 'height': H}, device_scale_factor=d, reduced_motion='reduce')
            pg = ctx.new_page(); pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.goto(url + '?' + q); pg.wait_for_timeout(4000)   # старт: шрифты, первая перепечка
            return ctx, pg

        for st in a.states.split(','):
            q = STATES[st]
            for (W, H) in sizes:
                if 'static' in checks:
                    ctx, pg = load(q, W, H, 1)
                    f1, f2 = tmp / 'a.png', tmp / 'b.png'
                    masked(pg, f1); pg.wait_for_timeout(1000); masked(pg, f2); ctx.close()
                    m, pct = diff(f1, f2); name = f'static-{st}-{W}x{H}@1'
                    rows.append((name, pct)); save_diff(m, f1, name) if pct and pct > .05 else None
                if 'resize' in checks:
                    # другой размер: 1920 ↔ 1366
                    W0, H0 = (1366, 768) if W != 1366 else (1920, 1080)
                    ctx, pg = load(q, W, H, 1); f1 = tmp / 'fresh.png'; masked(pg, f1); ctx.close()
                    ctx, pg = load(q, W0, H0, 1); pg.set_viewport_size({'width': W, 'height': H}); pg.wait_for_timeout(a.settle)
                    f2 = tmp / 'moved.png'; masked(pg, f2); ctx.close()
                    m, pct = diff(f1, f2); name = f'resize-{st}-{W0}to{W}x{H}@1'
                    rows.append((name, pct)); save_diff(m, f1, name) if pct and pct > .05 else None
                if 'dpr' in checks:
                    for d in dprs:
                        if d == 1: continue
                        ctx, pg = load(q, W, H, d); f1 = tmp / 'fresh.png'; masked(pg, f1); ctx.close()
                        ctx, pg = load(q, W, H, 1)
                        cdp = ctx.new_cdp_session(pg)
                        cdp.send('Emulation.setDeviceMetricsOverride', {'width': W, 'height': H, 'deviceScaleFactor': d, 'mobile': False})
                        pg.wait_for_timeout(a.settle); f2 = tmp / 'moved.png'; masked(pg, f2); ctx.close()
                        m, pct = diff(f1, f2); name = f'dpr-{st}-{W}x{H}@{d}'
                        rows.append((name, pct)); save_diff(m, f1, name) if pct and pct > .05 else None
                print(f'{st} {W}x{H}: ' + ', '.join(f'{n} {p:.3f}%' for n, p in rows if p is not None and f'-{st}-' in n and f'{W}x{H}' in n), flush=True)
        br.close()
    for f in tmp.iterdir(): f.unlink()
    tmp.rmdir()
    md = ['# Артефакты — сравнение путей', '', f'Порог: |ΔL| > {THR}. Маска: {", ".join(MASK)}. Карты разницы — `*-diff.png` (если доля > 0,05 %).', '',
          '| Проверка | Отличается, % |', '|---|---|']
    md += [f'| {n} | {"—" if p is None else f"{p:.3f}"} |' for n, p in rows]
    md += ['', 'Ошибки консоли: ' + ('нет' if not errors else '; '.join(sorted(set(errors))))]
    (out / 'REPORT.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    (out / 'report.json').write_text(json.dumps({'rows': rows, 'errors': errors}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('ошибки консоли:', 'нет' if not errors else errors[:5])


if __name__ == '__main__':
    main()
