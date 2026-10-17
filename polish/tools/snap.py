#!/usr/bin/env python3
"""Быстрый кадр игры с отладочными параметрами и, по желанию, JS перед снимком.

  python polish/tools/snap.py "level=7&event=blackout" out.jpg [--size 1366x768] [--wait 2.5] [--js "document.documentElement.dataset.light='emergency'"]

Для проб на глаз во время работы; кадры для журнала — shots.py, раскадровки — story.py.
"""
import argparse, sys
from pathlib import Path

sys.dont_write_bytecode = True
GAME = Path(__file__).resolve().parents[2] / 'night-shift-4.html'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('query'); ap.add_argument('out')
    ap.add_argument('--size', default='1366x768'); ap.add_argument('--wait', type=float, default=1.5)
    ap.add_argument('--js', default=None); ap.add_argument('--after', type=float, default=0.4)
    ap.add_argument('--file', default=str(GAME), help='другая версия игры (например, «до» для сравнения)'); ap.add_argument('--dpr', type=float, default=1)
    a = ap.parse_args()
    w, h = map(int, a.size.split('x'))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        page = br.new_context(viewport={'width': w, 'height': h}, device_scale_factor=a.dpr).new_page()
        errs = []
        page.on('pageerror', lambda e: errs.append(str(e)))
        page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        page.goto(Path(a.file).resolve().as_uri() + '?' + a.query, wait_until='load')
        page.wait_for_timeout(int(a.wait * 1000))
        if a.js:
            page.evaluate(a.js); page.wait_for_timeout(int(a.after * 1000))
        page.screenshot(path=a.out, type='jpeg' if a.out.endswith('.jpg') else 'png', **({'quality': 88} if a.out.endswith('.jpg') else {}))
        br.close()
    for e in errs: print('ошибка:', e)
    print(a.out)


if __name__ == '__main__':
    main()
