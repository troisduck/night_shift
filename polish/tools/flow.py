#!/usr/bin/env python3
"""Сквозной проход «первых десяти минут» настоящими кликами: счёт кликов до пульта, время, кадры по ходу, ошибки консоли.

  python polish/tools/flow.py [--size 1366x768] [--out polish/shots/P2/flow] [--reduced]

Первый запуск (чистое сохранение): заставки → дверь (звонок) → вступление (3 карточки) → подпись (росчерк + «Сдать»)
→ свет в зале → «Принять смену» → показ фокус-светом на смене 1 → журнал смены → смена 2: раскрытие приборов.
Повторный запуск (то же сохранение): заставки → дверь → «График смен» → свет коротко → «Принять смену».
Клик — это нажатие мыши или клавиши игроком; росчерк подписи кликом не считается (как в задании 4, 6.1).
"""
import argparse, json, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", default=str(ROOT / "night-shift-4.html"))
    ap.add_argument("--size", default="1366x768")
    ap.add_argument("--out", default=str(ROOT / "polish" / "shots" / "P2" / "flow"))
    ap.add_argument("--reduced", action="store_true")
    a = ap.parse_args()
    W, H = map(int, a.size.split("x"))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    log, errors, clicks = [], [], {"first": 0, "repeat": 0}
    t0 = [0.0]

    def note(msg):
        line = f"{time.time() - t0[0]:6.1f} с  {msg}"; log.append(line); print(line)

    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": W, "height": H}, reduced_motion="reduce" if a.reduced else "no-preference")
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        url = Path(a.game).resolve().as_uri()

        def shot(name):
            pg.screenshot(path=str(out / f"{name}-{a.size}.jpg"), type="jpeg", quality=82); note(f"кадр {name}")

        def click(sel, run, hold=0):
            box = pg.locator(sel).first.bounding_box()
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            pg.mouse.move(x, y); pg.mouse.down(); pg.wait_for_timeout(hold or 60); pg.mouse.up()
            clicks[run] += 1; note(f"клик {clicks[run]}: {sel}")

        # ---------- первый запуск ----------
        t0[0] = time.time()
        pg.goto(url); note("загрузка")
        pg.wait_for_timeout(900); shot("01-splash")
        pg.wait_for_selector(".sc-door .door-bell", timeout=9000); pg.wait_for_timeout(500); shot("02-door")
        click(".door-bell", "first", hold=320)
        pg.wait_for_timeout(500); click(".door-bell", "first", hold=320)   # открывают со второго звонка (П6)
        pg.wait_for_selector(".sc-intro", timeout=6000); pg.wait_for_timeout(1300); shot("03-intro")
        for i in range(3):
            pg.wait_for_timeout(500); click("#scene", "first")
        pg.wait_for_selector(".sc-sign .sg-sig", timeout=6000); pg.wait_for_timeout(700)
        b = pg.locator(".sg-sig").bounding_box()
        pts = [(.08, .7), (.18, .3), (.26, .75), (.36, .35), (.48, .7), (.6, .4), (.75, .62), (.92, .45)]
        pg.mouse.move(b["x"] + b["width"] * pts[0][0], b["y"] + b["height"] * pts[0][1]); pg.mouse.down()
        for px, py in pts[1:]:
            pg.mouse.move(b["x"] + b["width"] * px, b["y"] + b["height"] * py, steps=6); pg.wait_for_timeout(16)
        pg.mouse.up(); note("росчерк подписи"); shot("04-sign")
        click(".sg-ok", "first")
        pg.wait_for_timeout(500); shot("05-stamp")
        pg.wait_for_selector("#hall-dark", timeout=5000); pg.wait_for_timeout(700); shot("06-hall")
        pg.wait_for_selector("#mb-go", state="visible", timeout=8000); pg.wait_for_timeout(400); shot("07-brief")
        click("#mb-go", "first")
        t_panel = time.time() - t0[0]; at_panel = {"first": clicks["first"]}
        note(f"ДО ПУЛЬТА (первый запуск): {clicks['first']} кликов, {t_panel:.0f} с")
        pg.wait_for_selector(".fc-note.on", timeout=4000); pg.wait_for_timeout(450); shot("08-focus-power")
        pg.keyboard.press("Enter")   # П7: записку срывают (Enter — то же, что рывок рукой); клик по залу её не убирает
        pg.wait_for_timeout(700); shot("08b-focus-goal")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(700); shot("09-focus-rods")
        click("#btn-up", "first", hold=220)
        pg.wait_for_timeout(1300); shot("10-focus-rate")
        pg.wait_for_timeout(2000)
        # смена: досрочно сдаём (звёзды по журналу игры) — проверяем журнал
        pg.evaluate("UI.game.finish(true)")
        pg.wait_for_selector("#punch.on", timeout=8000); pg.wait_for_timeout(500); shot("10b-punch")   # П7: табельные часы — карточку пробивают
        pg.keyboard.press("Enter")
        pg.wait_for_selector("#m-result.show", timeout=8000); pg.wait_for_timeout(500); shot("11-journal-open")
        pg.wait_for_timeout(2600); shot("12-journal-done")
        click("#mr-next", "first")
        pg.wait_for_selector("#mb-go", state="visible", timeout=4000); pg.wait_for_timeout(300); shot("13-brief2")
        click("#mb-go", "first")
        for ms, nm in [(350, "14-unscrew"), (650, "15-fall"), (500, "16-selftest"), (1400, "17-focus-pumps")]:
            pg.wait_for_timeout(ms); shot(nm)
        # ---------- повторный запуск ----------
        t0[0] = time.time()
        pg.goto(url); note("повторная загрузка")
        pg.wait_for_selector(".sc-door .door-bell", timeout=9000); pg.wait_for_timeout(400)
        click(".door-bell", "repeat", hold=260)
        pg.wait_for_timeout(400); click(".door-bell", "repeat", hold=260)
        pg.wait_for_selector(".sc-shifts .gs-b.next", timeout=6000); pg.wait_for_timeout(500); shot("20-shifts")
        click(".gs-b.next", "repeat")
        pg.wait_for_timeout(250); shot("21-hall-short")
        pg.wait_for_selector("#mb-go", state="visible", timeout=6000); pg.wait_for_timeout(300)
        click("#mb-go", "repeat")
        at_panel["repeat"] = clicks["repeat"]
        note(f"ДО ПУЛЬТА (повторный запуск): {clicks['repeat']} кликов, {time.time() - t0[0]:.0f} с")
        br.close()
    rep = {"size": a.size, "clicks_first": at_panel["first"], "clicks_repeat": at_panel["repeat"], "sec_first": round(t_panel), "log": log, "errors": errors}
    (out / f"flow-{a.size}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ошибки консоли:", errors or "нет")


if __name__ == "__main__":
    main()
