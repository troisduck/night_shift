#!/usr/bin/env python3
"""Сводка теста прищура по report.json из shots.py: что занимает три самых заметных места в каждом состоянии.

  python polish/tools/squint.py polish/shots/P3/after [--md out.md]

Классы пятен (по элементу страницы под пятном):
  тревога — окно табло; цель — прибор текущей цели смены; Палыч — лист и портрет;
  бумага — ленты самописцев; схема — мнемосхема; заглушка — неустановленная аппаратура; прочее — остальное.
Цель прищура (задание 4, раздел 2): неквитированная тревога → прибор цели → Палыч, когда говорит;
неустановленное — вне пятёрки.
"""
import argparse, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
# прибор цели по смене (как DUTY_EL в игре): смены 1, 2, 8 — мощность; 3–6, 9, 10 — генератор; 7 — вода
DUTY = {1: '#b-power', 2: '#b-power', 3: '#b-grid', 4: '#b-grid', 5: '#b-grid', 6: '#b-power', 7: '#b-temp', 8: '#b-power', 9: '#b-grid', 10: '#b-grid'}


def kind(el, duty):
    if 'annunciator' in el: return 'тревога'
    if duty and duty in el: return 'цель'
    if 'm-text' in el or 'mentor' in el: return 'Палыч'
    if 'az-cover' in el or 'az-' in el: return 'АЗ'
    if 'cover' in el: return 'заглушка'
    if 'charts' in el or 'ch-' in el: return 'бумага'
    if 'mimic' in el: return 'схема'
    if 'window' in el or 'win-' in el: return 'окно'
    return 'прочее'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('dir'); ap.add_argument('--md')
    a = ap.parse_args()
    rep = json.loads((Path(a.dir) / 'report.json').read_text(encoding='utf-8'))
    rows = ['| Состояние | Размер | 1 | 2 | 3 | Заглушка в пятёрке |', '|---|---|---|---|---|---|']
    for r in rep:
        st, sz = r['state'], r['size']
        lvl = int(st[4:]) if st.startswith('play') and st[4:].isdigit() else (1 if st in ('alarm', 'tooltip', 'rods-hold') else 6 if st == 'pump' else 7 if st == 'blackout' else None)
        duty = DUTY.get(lvl)
        ks = [kind(s['el'], duty) for s in r['spots']]
        rows.append(f"| {st} | {sz} | {' | '.join(ks[:3])} | {'да' if 'заглушка' in ks[:5] else 'нет'} |")
    out = '\n'.join(rows)
    print(out)
    if a.md: Path(a.md).write_text(out + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
