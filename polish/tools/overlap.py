#!/usr/bin/env python3
"""Наслоения и вылезающий текст (задание 5, АРТ-ж; плейтест автора: «наслаивающиеся кнопки»).

  python polish/tools/overlap.py [игра.html] [--levels 1-10] [--sizes 1920x1080,1366x768,1024x768] [--dprs 1,1.25,1.5]
                                 [--out polish/shots/P7/overlap]

На каждую смену (все панели открыты — ?unlockall=1 — и как в самой смене), размер и масштаб устройства ищет:
  1. пересечения деталей щита, которые не вложены друг в друга (кнопки, тумблеры, окна индикаторов, шкалы, шильды, лампы);
  2. текст, который вылезает за свою рамку (окно индикатора, кнопка, шильда, табличка) — по прямоугольникам строк текста.
Итог — REPORT.md: что с чем и на сколько пикселей. 0 строк — артефактов этого класса нет.
"""
import argparse, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]

JS = r"""() => {
  const BOX = 'button, #topbar .tb-btns > *, .btn, .tog, .pkey, .ann, .read, .scale, .p-name, .p-st, .az-wrap, .rodviz, canvas.sched, .rate-txt, #r-allow, .gen-row .lmp, .goal-slip, .goal-lamps, .goal-ok, .lvl-name, .clock, .tag-plate, .sub, .prot-lens';
  const FRAME = '.read, .btn, .ann, .p-name, .p-st, .rate-txt, .lvl-name, .goal-slip, .tag-plate, .prot-lens, .sub, .goal-count';
  const vis = e => { const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return null; const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || +cs.opacity === 0) return null;
    for (let p = e; p; p = p.parentElement) { const c = getComputedStyle(p); if (c.display === 'none' || c.visibility === 'hidden' || +c.opacity < .05) return null;
      if (p.classList && p.classList.contains('locked') && p !== e) return null; if (p.classList && p.classList.contains('cover') && !p.parentElement.classList.contains('locked')) return null; } return r; };
  const name = e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (e.classList.length ? '.' + [...e.classList].slice(0, 2).join('.') : '')) + (e.closest('[id^="b-"]') ? ' в ' + e.closest('[id^="b-"]').id : '');
  const out = [];
  const els = [...document.querySelectorAll('#app ' + BOX.split(', ').join(', #app '))].map(e => [e, vis(e)]).filter(x => x[1]);
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    const [a, ra] = els[i], [b, rb] = els[j]; if (a.contains(b) || b.contains(a)) continue;
    if ([a.id, b.id].includes('az-cover')) continue;   // гриб АЗ под откидной крышкой — так задумано
    const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left), h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
    if (w > 1 && h > 1) out.push({ kind: 'наслоение', a: name(a), b: name(b), px: Math.round(Math.min(w, h) * 10) / 10 });
  }
  // текст за рамкой: строки текста (Range) против внутренней области ближайшей рамки
  const walker = document.createTreeWalker(document.getElementById('app'), NodeFilter.SHOW_TEXT);
  const seen = new Set();
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.textContent.trim()) continue; const host = n.parentElement && n.parentElement.closest(FRAME); if (!host || !vis(host) || !vis(n.parentElement)) continue;
    const hr = host.getBoundingClientRect(), cs = getComputedStyle(host), bl = parseFloat(cs.borderLeftWidth) || 0, br = parseFloat(cs.borderRightWidth) || 0, bt = parseFloat(cs.borderTopWidth) || 0, bb = parseFloat(cs.borderBottomWidth) || 0;
    const rg = document.createRange(); rg.selectNodeContents(n);
    for (const r of rg.getClientRects()) {
      const over = Math.max(hr.left + bl - r.left, r.right - (hr.right - br), (hr.top + bt - r.top) * .5, (r.bottom - (hr.bottom - bb)) * .5);   // по вертикали — половина: у строки есть интерлиньяж
      if (over > 1 && !seen.has(host)) { seen.add(host); out.push({ kind: 'текст за рамкой', a: name(host), b: JSON.stringify(n.textContent.trim().slice(0, 24)), px: Math.round(over * 10) / 10 }); }
    }
  }
  return out;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?', default=str(ROOT / 'night-shift-4.html'))
    ap.add_argument('--levels', default='1-10')
    ap.add_argument('--sizes', default='1920x1080,1366x768,1024x768')
    ap.add_argument('--dprs', default='1,1.25,1.5')
    ap.add_argument('--out', default=str(ROOT / 'polish' / 'shots' / 'P7' / 'overlap'))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    lo, hi = (int(x) for x in a.levels.split('-')) if '-' in a.levels else (int(a.levels),) * 2
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    url = Path(a.file).resolve().as_uri()
    rows, errors = [], []
    with sync_playwright() as p:
        br = p.chromium.launch()
        for d in [float(x) for x in a.dprs.split(',')]:
            for s in a.sizes.split(','):
                W, H = map(int, s.split('x'))
                ctx = br.new_context(viewport={'width': W, 'height': H}, device_scale_factor=d)
                pg = ctx.new_page(); pg.on('pageerror', lambda e: errors.append(str(e)))
                for lv in range(lo, hi + 1):
                    for q in (f'level={lv}&paused=1', f'level={lv}&paused=1&unlockall=1'):
                        pg.goto(url + '?' + q); pg.wait_for_timeout(900)
                        for r in pg.evaluate(JS):
                            rows.append(dict(r, where=f'смена {lv}{" (всё открыто)" if "unlockall" in q else ""} · {s} @{d}'))
                ctx.close()
                print(f'{s} @{d}: найдено {len(rows)} всего', flush=True)
        br.close()
    # свёртка: одно и то же место — одна строка, где встречается
    agg = {}
    for r in rows:
        k = (r['kind'], r['a'], r['b']); e = agg.setdefault(k, {'px': 0, 'where': []}); e['px'] = max(e['px'], r['px']); e['where'].append(r['where'])
    md = ['# Наслоения и текст за рамкой', '', f'Всего мест: {len(agg)} (строк до свёртки: {len(rows)}).', '', '| Что | Элемент | С чем / текст | Макс., px | Где (первые 3 из N) |', '|---|---|---|---|---|']
    for (kind, A, B), e in sorted(agg.items(), key=lambda kv: -kv[1]['px']):
        md.append(f"| {kind} | `{A}` | `{B}` | {e['px']} | {'; '.join(e['where'][:3])} (N={len(e['where'])}) |")
    md += ['', 'Ошибки консоли: ' + ('нет' if not errors else '; '.join(sorted(set(errors))[:5]))]
    (out / 'REPORT.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    (out / 'report.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    print('\n'.join(md[:40]))


if __name__ == '__main__':
    main()
