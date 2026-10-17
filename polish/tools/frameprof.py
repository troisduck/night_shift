#!/usr/bin/env python3
"""Где тратится время кадра: JS по частям цикла (отрисовка щита, моменты, окно, звук, физика) и всё остальное
(стиль, раскладка, рисование, композиция) — разность до полного интервала кадра.

  python polish/tools/frameprof.py "level=9" [--rate 4] [--sec 6] [--size 1366x768]
"""
import argparse, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]

WRAP = """(() => {
  const acc = window.__acc = {}; const wrap = (obj, name, key) => { const f = obj[name]; obj[name] = function (...a) { const t = performance.now(); try { return f.apply(this, a); } finally { acc[key] = (acc[key] || 0) + performance.now() - t; } }; };
  wrap(window, 'renderAll', 'щит (renderAll)'); wrap(Moments, 'frame', 'моменты'); wrap(Win, 'update', 'окно'); wrap(Snd, 'update', 'звук');
  wrap(UI.game.constructor.prototype, 'update', 'физика');
  wrap(window, 'renderMimic', 'мнемосхема'); wrap(window, 'drawTrend', 'самописцы'); wrap(window, 'renderDesk', 'приборы'); wrap(window, 'renderLamps', 'табло');
  wrap(FX, 'update', 'частицы'); wrap(Shake, 'update', 'тряска');
})()"""

JS = """(sec) => new Promise(res => { const d = []; let last = 0; const t0 = performance.now(); for (const k in __acc) __acc[k] = 0;
  function f(t) { if (last) d.push(t - last); last = t; if (t - t0 < sec * 1000) requestAnimationFrame(f); else res({ d, acc: __acc, total: t - t0 }); }
  requestAnimationFrame(f); })"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('query'); ap.add_argument('--rate', type=float, default=4); ap.add_argument('--sec', type=float, default=6)
    ap.add_argument('--size', default='1366x768'); ap.add_argument('--wait', type=float, default=1.2)
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    W, H = map(int, a.size.split('x'))
    with sync_playwright() as p:
        br = p.chromium.launch(); ctx = br.new_context(viewport={'width': W, 'height': H}); page = ctx.new_page()
        cdp = ctx.new_cdp_session(page); cdp.send('Emulation.setCPUThrottlingRate', {'rate': a.rate})
        page.goto((ROOT / 'night-shift-4.html').resolve().as_uri() + '?' + a.query); page.wait_for_timeout(int(a.wait * 1000))
        page.evaluate(WRAP)
        r = page.evaluate(JS, a.sec); d = sorted(r['d']); n = len(d)
        print(f"{a.query} ×{a.rate}: кадров {n}, медиана {d[n // 2]:.1f} мс, p95 {d[int(n * .95)]:.1f} мс")
        tot = r['total']; js = 0
        for k, v in sorted(r['acc'].items(), key=lambda kv: -kv[1]):
            print(f"  {k:<18} {v / n:6.1f} мс/кадр  ({100 * v / tot:4.1f} % времени)")
        br.close()


if __name__ == '__main__':
    main()
