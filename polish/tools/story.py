#!/usr/bin/env python3
"""Раскадровки больших моментов (задание 4, раздел 12): кадр в заданную секунду от начала момента.

  python polish/tools/story.py [--moments sync,pump,scram,blackout,explosion,dawn] [--size 1366x768] [--repeat] [--out polish/storyboards]

Каждый кадр — отдельная загрузка `?moment=<имя>&at=<секунда>`: игра замораживает момент ровно в эту секунду
(часы моментов, CSS-анимации — на паузе), поэтому кадр повторяем. На выходе:
  <имя>.jpg            — лист 6–12 кадров с подписями;
  <имя>/<секунда>.jpg  — отдельные кадры;
  ошибки консоли — в выводе.
--repeat — короткая версия, как при повторном показе (лист <имя>-repeat.jpg).
"""
import argparse, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'night-shift-4.html'

# секунды кадров от начала момента; подписи — что должно быть видно
FRAMES = {
    'sync': [(0, 'щелчок выключателя, лампа «В сети»'), (0.4, 'волна пошла от станции'), (0.9, ''), (1.5, ''), (2.1, 'волна дошла до домов'), (2.7, 'посёлок горит'), (3.4, 'Палыч после паузы'), (5, '')],
    'pump': [(0, 'дуга, удар выключателя'), (0.06, 'провал света'), (0.15, 'искры у насоса'), (0.3, ''), (0.55, 'дым'), (0.9, 'лампа погасла, ключ во «ВКЛ»'), (1.4, ''), (2.5, 'табло, реплика')],
    'scram': [(0, 'гриб АЗ, каскад реле'), (0.3, 'стержни падают'), (0.8, 'удар внизу'), (1.3, 'мощность падает'), (2.0, 'кварталы гаснут'), (3.0, 'хвост тепла'), (4.2, 'зал затихает'), (5.9, 'журнал')],
    'blackout': [(0, 'выключатели'), (0.04, 'миг темноты'), (0.25, ''), (0.5, 'аварийный свет'), (0.8, ''), (1.5, 'насосы выбегают'), (3, 'посёлок тёмный'), (6, 'Палыч: пуск ДГ')],
    'explosion': [(0, 'начало повреждения'), (1.5, 'толчки, пыль'), (3.0, 'всё табло красное'), (4.15, 'вдох'), (4.8, 'разрез: крышку срывает'), (5.6, 'пар бьёт в кровлю'), (6.6, 'кровля пробита'), (7.25, 'удар в зале, вспышка'), (7.6, 'аварийный свет, трещины'), (8.8, 'зарево в окне'), (10.2, 'тишина'), (11.4, 'акт')],
    'dawn': [(0, 'смена сдана'), (0.6, 'замирает'), (1.2, ''), (2.0, 'рассвет'), (2.8, ''), (3.5, ''), (4.0, 'журнал')],
}
# концы смены по причине (П6) и варианты разреза: имя → запрос
CAUSE = [(0, 'АЗ по причине'), (0.3, ''), (0.7, ''), (1.2, ''), (1.8, ''), (2.6, 'затихает')]
QUERY = {}
for why in ['overpower', 'tout', 'subcool', 'pHigh', 'pLow', 'pumpLimit', 'backup', 'schedule']:
    FRAMES['end-' + why] = CAUSE if why != 'schedule' else [(0, 'звонок диспетчера'), (0.7, 'кварталы гаснут'), (1.4, ''), (2.2, ''), (3.0, ''), (3.8, 'журнал')]
    QUERY['end-' + why] = f'moment=end&why={why}'
for v in ['rupture', 'melt']:
    FRAMES['explosion-' + v] = [(4.15, 'вдох'), (4.6, ''), (5.1, ''), (5.6, ''), (6.0, ''), (6.4, ''), (6.8, ''), (7.25, 'удар')]
    QUERY['explosion-' + v] = f'moment=explosion&cut={v}'
REPEAT = {
    'scram': [(0, ''), (0.5, ''), (1.0, ''), (1.8, ''), (2.4, ''), (2.8, 'журнал')],
    'explosion': [(3.0, ''), (4.15, 'вдох'), (4.6, 'разрез'), (5.4, ''), (5.95, 'удар'), (6.6, ''), (7.3, ''), (8.0, 'акт')],
    'dawn': [(0, ''), (0.6, ''), (1.2, ''), (1.8, 'журнал')],
    'sync': [(0, ''), (0.4, ''), (0.8, ''), (1.3, ''), (2, '')],
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--moments', default=','.join(k for k in FRAMES if k not in QUERY)); ap.add_argument('--size', default='1366x768')
    ap.add_argument('--repeat', action='store_true'); ap.add_argument('--out', default=str(ROOT / 'polish' / 'storyboards'))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    from PIL import Image, ImageDraw, ImageFont
    w, h = map(int, a.size.split('x')); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    font = None
    for nm in ('arial.ttf', 'DejaVuSans.ttf'):   # Windows / Linux; у шрифта по умолчанию нет кириллицы
        try: font = ImageFont.truetype(nm, 15); break
        except Exception: pass
    font = font or ImageFont.load_default()
    table = REPEAT if a.repeat else FRAMES
    with sync_playwright() as p:
        br = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for m in a.moments.split(','):
            if m not in table: continue
            fdir = out / (m + ('-repeat' if a.repeat else '')); fdir.mkdir(exist_ok=True)
            shots = []
            for sec, note in table[m]:
                page = br.new_context(viewport={'width': w, 'height': h}).new_page(); errs = []
                page.on('pageerror', lambda e: errs.append(str(e)))
                page.on('console', lambda msg: errs.append(msg.text) if msg.type == 'error' else None)
                page.goto(GAME.as_uri() + '?' + QUERY.get(m, f'moment={m}') + f'&at={sec}' + ('&repeat=1' if a.repeat else ''), wait_until='load')
                try: page.wait_for_function('Moments.frozen === true', timeout=30000)
                except Exception: errs.append('момент не дошёл до этой секунды за 30 с')
                page.wait_for_timeout(120)
                f = fdir / f'{sec:05.2f}.jpg'; page.screenshot(path=str(f), type='jpeg', quality=86)
                page.context.close(); shots.append((f, sec, note))
                for e in errs: print(f'  {m} {sec} с: {e}')
            cols = 4 if len(shots) > 6 else 3; rows = (len(shots) + cols - 1) // cols
            tw, th = w // 2, h // 2
            sheet = Image.new('RGB', (cols * tw + (cols + 1) * 8, rows * (th + 26) + 8), (18, 20, 19)); dr = ImageDraw.Draw(sheet)
            for k, (f, sec, note) in enumerate(shots):
                im = Image.open(f).resize((tw, th)); x0 = 8 + (k % cols) * (tw + 8); y0 = 8 + (k // cols) * (th + 26)
                sheet.paste(im, (x0, y0)); dr.text((x0 + 2, y0 + th + 4), f'{sec:g} с  {note}', fill=(220, 214, 196), font=font)
            sp = out / f"{m}{'-repeat' if a.repeat else ''}.jpg"; sheet.save(sp, quality=86); print(sp)
        br.close()


if __name__ == '__main__':
    main()
