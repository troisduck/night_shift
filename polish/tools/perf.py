#!/usr/bin/env python3
"""Плавность: интервалы кадров при замедленном процессоре (CDP Emulation.setCPUThrottlingRate).

  python polish/tools/perf.py [игра.html] [--rate 4] [--states play9,alarm,?moment=explosion] [--size 1920x1080] [--sec 6]
Состояние с «?» — сырой адрес (большие моменты).
Пишет медиану, 95-й и 99-й перцентили интервала кадра и долю кадров длиннее 33 мс.
"""
import argparse, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent))
from shots import STATES, ROOT

JS = """(sec) => new Promise(res => { const d = []; let last = 0; const t0 = performance.now();
  function f(t) { if (last) d.push(t - last); last = t; if (t - t0 < sec * 1000) requestAnimationFrame(f); else res(d); }
  requestAnimationFrame(f); })"""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("file", nargs="?", default=str(ROOT / "night-shift-4.html"))
    ap.add_argument("--rate", type=float, default=4); ap.add_argument("--states", default="play9,alarm,rods-hold")
    ap.add_argument("--size", default="1920x1080"); ap.add_argument("--sec", type=float, default=6)
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    W, H = map(int, a.size.split("x")); out = []
    with sync_playwright() as p:
        br = p.chromium.launch(); ctx = br.new_context(viewport={"width": W, "height": H})
        for name in a.states.split(","):
            q, js, wait = (name[1:], '', 0) if name.startswith('?') else STATES[name]; page = ctx.new_page()   # «?moment=explosion» — сырой адрес
            cdp = ctx.new_cdp_session(page); cdp.send("Emulation.setCPUThrottlingRate", {"rate": a.rate})
            page.goto(Path(a.file).resolve().as_uri() + ("?" + q if q else "")); page.wait_for_timeout(400)
            if js: page.evaluate(js)
            if name == "alarm": page.evaluate("UI.paused = false; updatePauseUI()")
            page.wait_for_timeout(800)
            d = sorted(page.evaluate(JS, a.sec)); n = len(d)
            pc = lambda k: round(d[min(n - 1, int(n * k))], 1)
            r = {"state": name, "rate": a.rate, "frames": n, "median_ms": pc(.5), "p95_ms": pc(.95), "p99_ms": pc(.99), "over33": round(sum(x > 33.4 for x in d) / n, 3)}
            out.append(r); print(json.dumps(r, ensure_ascii=False)); page.close()
        br.close()

if __name__ == "__main__":
    main()
