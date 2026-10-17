#!/usr/bin/env python3
"""Отклик неработающего (задание 5, раздел 9, п. 4; метрика раздела 12): сетка кликов по щиту — в каждой точке звук в том же обработчике.

  python polish/tools/tapgrid.py [игра.html] [--levels 1,5,9] [--size 1366x768] [--step 40] [--out polish/shots/P7/tapgrid]

Смена на паузе (?level=N&paused=1): органы на паузе отвечают глухим упором — это тоже звук. Перед каждым кликом счётчик вызовов
звукового слоя (Snd.cue, deny, click, ui, cover…) обнуляется; клик настоящей мышью; сразу после — сколько звуков и каких.
Точка без звука — «мёртвая». Сознательные исключения — вне щита: полоса слоя игры (её клавиши звучат сами), края окна браузера.
Итог: REPORT.md — доля мёртвых точек и их список (элемент под точкой), карта dead-<смена>.png (красное — мёртвые).
"""
import argparse, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]

SPY = r"""() => {
  if (window.__spy) return; window.__spy = [];
  for (const k of ['cue', 'cueAt', 'deny', 'click', 'ui', 'cover', 'win', 'lose']) { const f = Snd[k]; if (typeof f !== 'function') continue;
    Snd[k] = function (...a) { window.__spy.push(k + (typeof a[0] === 'string' ? ':' + a[0] : '')); return f.apply(this, a); }; }
}"""
DESC = r"""([x, y]) => { const e = document.elementFromPoint(x, y); if (!e) return '—'; const id = e.id ? '#' + e.id : ''; const c = e.classList && e.classList.length ? '.' + [...e.classList].slice(0, 2).join('.') : '';
  const host = e.closest('[id]'); return e.tagName.toLowerCase() + id + c + (host && host !== e ? ' в #' + host.id : ''); }"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?', default=str(ROOT / 'night-shift-4.html'))
    ap.add_argument('--levels', default='1,5,9'); ap.add_argument('--size', default='1366x768'); ap.add_argument('--step', type=int, default=40)
    ap.add_argument('--out', default=str(ROOT / 'polish' / 'shots' / 'P7' / 'tapgrid'))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    from PIL import Image, ImageDraw
    import io
    W, H = map(int, a.size.split('x')); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    md = ['# Сетка кликов: отклик в каждой точке щита', '', f'Шаг {a.step} px, {a.size}, смена на паузе. Исключения: полоса слоя игры (`.tb-btns`).', '']
    errs = []
    with sync_playwright() as p:
        br = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for lv in [int(x) for x in a.levels.split(',')]:
            pg = br.new_page(viewport={'width': W, 'height': H}); pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(Path(a.file).resolve().as_uri() + f'?level={lv}&paused=1'); pg.wait_for_timeout(2200); pg.evaluate(SPY)
            base = Image.open(io.BytesIO(pg.screenshot())).convert('RGB'); dr = ImageDraw.Draw(base)
            dead, total = [], 0
            for y in range(a.step // 2, H, a.step):
                for x in range(a.step // 2, W, a.step):
                    skip = pg.evaluate("([x, y]) => { const e = document.elementFromPoint(x, y); return !e || !!e.closest('.tb-btns, #keys-ov') }", [x, y])
                    if skip: continue
                    total += 1; pg.wait_for_timeout(140); pg.evaluate('window.__spy.length = 0')   # больше FEEL.touch.gap: иначе соседние точки одного предмета гасит ограничение частоты
                    pg.mouse.click(x, y); calls = pg.evaluate('window.__spy.slice()')
                    if not calls:
                        dead.append((x, y, pg.evaluate(DESC, [x, y]))); dr.rectangle([x - 6, y - 6, x + 6, y + 6], outline=(255, 40, 40), width=3)
                    else: dr.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(80, 220, 120))
                    # клик мог открыть что-то (подсказку, крышку АЗ, громкость) — закрыть: Esc и вернуть паузу
                    pg.keyboard.press('Escape')
                    if pg.evaluate("!!(UI.modal || document.querySelector('.vol-panel:not([hidden])'))"): pg.evaluate("hideModal && UI.modal && hideModal(); document.querySelectorAll('.vol-panel').forEach(v => v.hidden = true)")
                    if not pg.evaluate('UI.paused') and pg.evaluate("UI.mode === 'play'"): pg.evaluate('togglePause()')
            base.save(out / f'dead-{lv}.png')
            md += [f'## Смена {lv}', '', f'Точек: {total}, мёртвых: {len(dead)} ({len(dead) / max(1, total) * 100:.1f} %).', '']
            agg = {}
            for x, y, d in dead: agg.setdefault(d, []).append((x, y))
            md += [f'- `{d}` — {len(v)} т., например ({v[0][0]}, {v[0][1]})' for d, v in sorted(agg.items(), key=lambda kv: -len(kv[1]))[:30]] + ['']
            print(f'смена {lv}: точек {total}, мёртвых {len(dead)}', flush=True)
            pg.close()
        br.close()
    md += ['Ошибки консоли: ' + ('нет' if not errs else '; '.join(sorted(set(errs))[:5]))]
    (out / 'REPORT.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print('\n'.join(md[-40:]))


if __name__ == '__main__':
    main()
