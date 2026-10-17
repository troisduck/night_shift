#!/usr/bin/env python3
"""Снимки «Ночной смены» для полишинга: состояния × размеры экрана, серый и «прищур», самые заметные пятна.

  python polish/tools/shots.py [игра.html] --out polish/shots/P0 [--states menu,play1] [--sizes 1920x1080,1366x768]
                               [--offline] [--list]

На каждое состояние и размер:
  <состояние>-<размер>.jpg        — кадр;
  <состояние>-<размер>-sheet.jpg  — слева серый, справа «прищур» с номерами самых заметных пятен;
  report.json / REPORT.md         — пятна (элемент страницы под пятном), ошибки консоли, шрифты.

Заметность пятна = светлота L* + 0,6 × насыщенность (C*) на размытом кадре: так меряется, куда идёт глаз,
когда детали не видно. Пять пятен ищутся с подавлением соседей (не ближе 13 % ширины друг к другу).
"""
import argparse, json, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]

# Состояния: параметры адреса, JS после загрузки, ожидание (мс). JS выполняется в странице игры.
STATES = {
    "menu":        ("level=1&paused=1", "showMenu()", 900),
    "splash":      ("", None, 900),
    "splash2":     ("", None, 3200),
    "door":        ("screen=door", None, 900),
    "door-hover":  ("screen=door", "document.querySelector('.door-bell').dispatchEvent(new PointerEvent('pointerover', {bubbles: true}))", 600),
    "door-open":   ("screen=door", "SCENES.door.open()", 1500),
    "door-enter":  ("screen=door", "SCENES.door.open()", 2050),
    "intro":       ("screen=intro", None, 1200),
    "sign":        ("screen=sign", None, 1200),
    "shifts":      ("screen=shifts", None, 1200),
    "settings":    ("screen=settings", None, 900),
    "hall":        ("moment=hall", None, 700),
    "brief1":      ("level=1&paused=1", "startLevel(0)", 900),
    "goal":        ("level=1&paused=1", "UI.game.s.Pth = 0.2; UI.game.s.P = 0.2; UI.game.prog = 14; UI.game.status = null; renderAll(UI.game, 0)", 700),
    "goal-cond":   ("level=2&paused=1", "UI.game.s.Pth = 0.5; UI.game.s.P = 0.5; UI.game.s.Tout = 330; UI.game.prog = 6; UI.game.status = null; renderAll(UI.game, 0)", 700),
    "guide1":      ("moment=guide", None, 1300),
    "guide1-rods": ("moment=guide", "Guide.click()", 1700),
    "unlock-a":    ("moment=unlock", None, 450),
    "unlock-b":    ("moment=unlock", None, 1250),
    "unlock-c":    ("moment=unlock", None, 1750),
    "unlock-d":    ("moment=unlock", None, 3700),
    "reveal3":     ("level=3&paused=1", "startLevel(2, false); beginPlay(true)", 3600),
    "reveal5":     ("level=5&paused=1", "startLevel(4, false); beginPlay(true)", 3300),
    "reveal7":     ("level=7&paused=1", "startLevel(6, false); beginPlay(true)", 2600),
    "reveal7-mid": ("level=7&paused=1", "startLevel(6, false); beginPlay(true)", 420),
    "reveal8":     ("level=8&paused=1", "startLevel(7, false); beginPlay(true)", 2600),
    "play1":       ("level=1", None, 2600),
    "play1-pause": ("level=1&paused=1", None, 1200),
    "play2":       ("level=2", None, 2600),
    "play3":       ("level=3", None, 2600),
    "play4":       ("level=4", None, 2600),
    "play5":       ("level=5", None, 2600),
    "play6":       ("level=6", None, 2600),
    "play7":       ("level=7", None, 2600),
    "play8":       ("level=8", None, 2600),
    "play9":       ("level=9", None, 2600),
    "play9-mmb":   ("level=9", "document.getElementById('b-mimic').classList.add('mm-b')", 2600),
    "play2-mmb":   ("level=2", "document.getElementById('b-mimic').classList.add('mm-b')", 2600),
    "alarm-mmb":   ("unlockall=1&event=alarm_test", "document.getElementById('b-mimic').classList.add('mm-b')", 1200),
    "play10":      ("level=10", None, 2600),
    "alarm":       ("unlockall=1&event=alarm_test", None, 1200),
    "pump":        ("level=6&event=pump_trip", None, 1500),
    "blackout":    ("level=7", None, 4500),
    "rods-hold":   ("level=1", "UI.game.rodPress(1); document.getElementById('btn-up').classList.add('pressed')", 3200),
    "tooltip":     ("level=1&paused=1", "showTip(document.getElementById('btn-up'))", 900),
    "result-ok":   ("level=1", "UI.game.finish(true); showResult(UI.game)", 3800),
    "result-fail": ("level=1", "UI.game.pressScram()", 3800),
    "unlock4":     ("level=4&paused=1", "startLevel(3, false); beginPlay(true)", 2200),   # П6: был пустой адрес — снималась заставка
}
SIZES = ["1920x1080", "1366x768", "1024x768", "390x844"]

DESCRIBE_JS = """([x, y]) => {
  const el = document.elementFromPoint(x, y); if (!el) return '—';
  const parts = []; let e = el;
  while (e && e !== document.body && parts.length < 4) {
    let n = e.tagName.toLowerCase();
    if (e.id) n += '#' + e.id; else if (e.classList.length) n += '.' + [...e.classList].slice(0, 2).join('.');
    parts.push(n); if (e.id && /^(b-|m-|mr-|colL|colC|colR|annunciator|topbar|mentor|charts|overlay|bottom)/.test(e.id)) break;
    e = e.parentElement;
  }
  const txt = (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 40);
  return parts.reverse().join(' > ') + (txt ? '  «' + txt + '»' : '');
}"""


def salience_spots(img, n=5):
    import numpy as np
    from PIL import ImageFilter
    w, h = img.size
    small = img.resize((w // 4, h // 4))
    blur = small.filter(ImageFilter.GaussianBlur(radius=max(3, w // 4 // 90)))
    a = np.asarray(blur).astype(np.float32) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    X = 0.4124 * lin[..., 0] + 0.3576 * lin[..., 1] + 0.1805 * lin[..., 2]
    Y = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    Z = 0.0193 * lin[..., 0] + 0.1192 * lin[..., 1] + 0.9505 * lin[..., 2]
    f = lambda t: np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16 / 116)
    L = 116 * f(Y) - 16
    A = 500 * (f(X / 0.9505) - f(Y)); B = 200 * (f(Y) - f(Z / 1.089))
    C = np.sqrt(A * A + B * B)
    S = L + 0.6 * C
    # локальный контраст: пятно заметно, если ярче окрестности
    big = blur.filter(ImageFilter.GaussianBlur(radius=max(8, w // 4 // 25)))
    b = np.asarray(big).astype(np.float32) / 255.0
    bl = np.where(b <= 0.04045, b / 12.92, ((b + 0.055) / 1.055) ** 2.4)
    Lb = 116 * f(0.2126 * bl[..., 0] + 0.7152 * bl[..., 1] + 0.0722 * bl[..., 2]) - 16
    sal = S + 0.5 * np.maximum(0, L - Lb)
    hs, ws = sal.shape
    rad = int(ws * 0.13)
    spots, m = [], sal.copy()
    for _ in range(n):
        i = int(m.argmax()); y, x = divmod(i, ws)
        spots.append({"x": x * 4 + 2, "y": y * 4 + 2, "score": round(float(m[y, x]), 1), "L": round(float(L[y, x]), 1), "C": round(float(C[y, x]), 1)})
        y0, y1, x0, x1 = max(0, y - rad), min(hs, y + rad), max(0, x - rad), min(ws, x + rad)
        m[y0:y1, x0:x1] = -1e9
    return spots


def make_sheet(png, out, spots):
    from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageFont
    im = Image.open(png).convert("RGB")
    w, h = im.size
    gray = ImageOps.grayscale(im).convert("RGB")
    squint = im.filter(ImageFilter.GaussianBlur(radius=max(6, w // 160)))
    d = ImageDraw.Draw(squint)
    try:
        font = ImageFont.truetype("arialbd.ttf", max(18, w // 60))
    except Exception:
        font = ImageFont.load_default()
    for k, s in enumerate(spots, 1):
        r = max(14, w // 70)
        d.ellipse((s["x"] - r, s["y"] - r, s["x"] + r, s["y"] + r), outline=(255, 0, 255), width=max(3, w // 400))
        d.text((s["x"] + r + 4, s["y"] - r), str(k), fill=(255, 0, 255), font=font)
    hw, hh = w // 2, h // 2
    sheet = Image.new("RGB", (w, hh), (0, 0, 0))
    sheet.paste(gray.resize((hw, hh)), (0, 0))
    sheet.paste(squint.resize((hw, hh)), (hw, 0))
    sheet.save(out, quality=86)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", default=str(ROOT / "night-shift-4.html"))
    ap.add_argument("--out", default=str(ROOT / "polish" / "shots" / "P0"))
    ap.add_argument("--states", default=",".join(STATES))
    ap.add_argument("--sizes", default=",".join(SIZES))
    ap.add_argument("--offline", action="store_true", help="без сети: проверить запасные шрифты")
    ap.add_argument("--reduced", action="store_true", help="prefers-reduced-motion")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        print("\n".join(STATES)); return
    from playwright.sync_api import sync_playwright
    from PIL import Image
    game = Path(a.file).resolve()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rep = []
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        for size in a.sizes.split(","):
            W, H = map(int, size.split("x"))
            ctx = br.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                                 reduced_motion="reduce" if a.reduced else "no-preference", offline=a.offline)
            for name in a.states.split(","):
                q, js, wait = STATES[name]
                page = ctx.new_page()
                errs = []
                page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errs.append(str(e)))
                page.goto(game.as_uri() + ("?" + q if q else ""), wait_until="load")
                page.wait_for_timeout(300)
                if js:
                    page.evaluate(js)
                page.wait_for_timeout(wait)
                stem = f"{name}-{size}" + ("-offline" if a.offline else "") + ("-reduced" if a.reduced else "")
                png = out / f"{stem}.png"
                page.screenshot(path=str(png))
                img = Image.open(png).convert("RGB")
                spots = salience_spots(img)
                for s in spots:
                    s["el"] = page.evaluate(DESCRIBE_JS, [s["x"], s["y"]])
                fonts = page.evaluate("[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight)")
                scroll = page.evaluate("[document.documentElement.scrollWidth > innerWidth, document.documentElement.scrollHeight > innerHeight]")
                img.save(out / f"{stem}.jpg", quality=88)
                make_sheet(png, out / f"{stem}-sheet.jpg", spots)
                png.unlink()
                rep.append({"state": name + ("-offline" if a.offline else "") + ("-reduced" if a.reduced else ""), "size": size, "spots": spots, "errors": errs, "fonts": sorted(set(fonts)),
                            "scroll": {"x": scroll[0], "y": scroll[1]}})
                print(f"{stem}: " + " | ".join(f"{i+1}. {s['el'][:60]}" for i, s in enumerate(spots[:3])) + (f"  ОШИБКИ: {len(errs)}" if errs else ""))
                page.close()
            ctx.close()
        br.close()
    old = []
    rp = out / "report.json"
    if rp.exists():
        keep = {(r["state"], r["size"]) for r in rep}  # кадры без сети и с reduced-motion — отдельные состояния
        old = [r for r in json.loads(rp.read_text(encoding="utf-8")) if (r["state"], r["size"]) not in keep]
    allr = old + rep
    rp.write_text(json.dumps(allr, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Снимки и тест прищура", "", "Пятна — пять самых заметных мест на размытом кадре (L* + 0,6·C* + локальный контраст).", ""]
    for r in allr:
        md.append(f"## {r['state']} — {r['size']}")
        for i, s in enumerate(r["spots"], 1):
            md.append(f"{i}. ({s['x']}, {s['y']}) заметность {s['score']} — `{s['el']}`")
        if r["errors"]:
            md.append(f"- Ошибки консоли: {r['errors'][:3]}")
        if r["scroll"]["x"] or r["scroll"]["y"]:
            md.append(f"- Прокрутка: {r['scroll']}")
        md.append("")
    (out / "REPORT.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
