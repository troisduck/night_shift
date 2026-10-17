#!/usr/bin/env python3
"""Конец смены (задание 5, раздел 6): раскадровка и замер — от выполнения цели до готового планшета, первый раз и повторно.

  python polish/tools/endshift.py [игра.html] [--size 1366x768] [--gesture 1.0] [--out polish/storyboards]

Смена 1 сдаётся досрочно (UI.game.finish(true)), дальше всё идёт само в реальном времени: рассвет → табельные часы →
через --gesture с игрок «пробивает» карточку (настоящее перетаскивание мышью в щель) → планшет заполняется.
Кадры — end-shift-<NN>.jpg и лист end-shift.jpg; замер — в выводе:
  до часов, жест, до планшета, до готового планшета (кнопки видны сразу), паузы без движения.
Второй прогон — «Ещё раз» и снова сдать: повторная короткая версия (цель ≤ 4 с до кнопки «Следующая смена»).
"""
import argparse, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?', default=str(ROOT / 'night-shift-4.html'))
    ap.add_argument('--size', default='1366x768'); ap.add_argument('--gesture', type=float, default=1.0)
    ap.add_argument('--out', default=str(ROOT / 'polish' / 'storyboards'))
    ap.add_argument('--measure', action='store_true', help='только замер, без кадров (снимки посреди анимации её тормозят)')
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    from PIL import Image, ImageDraw
    W, H = map(int, a.size.split('x')); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    frames, errs = [], []
    with sync_playwright() as p:
        br = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        pg = br.new_page(viewport={'width': W, 'height': H}); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(Path(a.file).resolve().as_uri() + '?level=1'); pg.wait_for_timeout(2500)

        def run(tag, shots):
            t0 = time.time(); pg.evaluate('UI.game.finish(true)')
            at = lambda: time.time() - t0
            pg.wait_for_selector('#punch.on', timeout=15000); t_punch = at()
            if shots: pg.wait_for_timeout(250); frames.append((f'{tag} {at():.1f} с — стена с часами', pg.screenshot()))
            pg.wait_for_timeout(int(a.gesture * 1000))
            c = pg.locator('#pc-card').bounding_box(); s = pg.locator('#pc-slot').bounding_box()
            t_g = at(); pg.mouse.move(c['x'] + c['width'] / 2, c['y'] + c['height'] * .3); pg.mouse.down()
            for k in range(1, 9):
                pg.mouse.move(c['x'] + c['width'] / 2 + (s['x'] + s['width'] / 2 - c['x'] - c['width'] / 2) * k / 8,
                              c['y'] + c['height'] * .3 + (s['y'] - c['height'] * .55 - c['y']) * k / 8, steps=2)
                if shots and k == 5: frames.append((f'{tag} {at():.1f} с — карточку тянут к щели', pg.screenshot()))
            pg.mouse.up()
            if shots:
                for ms, cap in [(260, 'в щели'), (300, 'удар, оттиск времени'), (500, 'карточку подносят к глазам')]:
                    pg.wait_for_timeout(ms); frames.append((f'{tag} {at():.1f} с — {cap}', pg.screenshot()))
            pg.wait_for_selector('#m-result.show', timeout=8000); t_plank = at()
            if shots: pg.wait_for_timeout(500); frames.append((f'{tag} {at():.1f} с — планшет заполняется', pg.screenshot()))
            pg.wait_for_function("!document.getElementById('m-result').classList.contains('filling')", timeout=15000); t_ready = at()
            if shots: frames.append((f'{tag} {at():.1f} с — планшет готов', pg.screenshot()))
            print(f'{tag}: до часов {t_punch:.1f} с · жест через {a.gesture:.1f} с (отпустил на {t_g + .4:.1f} с) · '
                  f'планшет на {t_plank:.1f} с (кнопки видны) · готов на {t_ready:.1f} с', flush=True)

        frames.append(('0 с — цель выполнена', pg.screenshot()))
        run('первый раз', not a.measure)
        pg.locator('#mr-retry').click(); pg.wait_for_timeout(2500)
        run('повтор', False)
        br.close()
    if a.measure: print('ошибки консоли:', 'нет' if not errs else errs[:3]); return
    for i, (cap, png) in enumerate(frames):
        (out / f'end-shift-{i:02d}.png').write_bytes(png)
    # лист
    import io
    ims = [Image.open(io.BytesIO(png)).convert('RGB').resize((480, int(480 * H / W))) for _, png in frames]
    cols = 3; rows = (len(ims) + cols - 1) // cols; ch = ims[0].height + 26
    sheet = Image.new('RGB', (cols * 480 + (cols + 1) * 8, rows * ch + 8), (18, 20, 18)); d = ImageDraw.Draw(sheet)
    from PIL import ImageFont
    try: font = ImageFont.truetype('DejaVuSans.ttf', 13)   # подписи кириллицей
    except OSError: font = None
    for i, im in enumerate(ims):
        x, y = 8 + (i % cols) * 488, 8 + (i // cols) * ch; sheet.paste(im, (x, y)); d.text((x + 4, y + im.height + 5), frames[i][0], fill=(230, 224, 206), font=font)
    sheet.save(out / 'end-shift.jpg', quality=86)
    for f in out.glob('end-shift-*.png'):
        Image.open(f).convert('RGB').save(f.with_suffix('.jpg'), quality=84); f.unlink()
    print('лист:', out / 'end-shift.jpg', '· ошибки консоли:', 'нет' if not errs else errs[:3])


if __name__ == '__main__':
    main()
