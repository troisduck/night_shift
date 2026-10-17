#!/usr/bin/env python3
"""Громкость смеси по экранам игры (П5, сведение: «одинаковая громкость на всех экранах»).

  python polish/tools/mixlevels.py [--sec 4] [--md polish/sound/P5-mix-levels.md]

Живой звук в Chromium: всё, что идёт в AudioDestinationNode, ответвляется на измеритель (срез 100 Гц — грубая
замена K-взвешивания, потом RMS). Для каждого экрана — средняя громкость за --sec секунд и самый громкий блок 100 мс,
в дБFS. Это не LUFS: сравнивать экраны между собой, а не с внешними нормами.
"""
import argparse, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'night-shift-4.html'

TAP = r"""
(() => {
  const orig = AudioNode.prototype.connect;
  window.__lv = { sq: 0, n: 0, blocks: [], reset() { this.sq = 0; this.n = 0; this.blocks = []; } };
  AudioNode.prototype.connect = function (dest, ...a) {
    const r = orig.call(this, dest, ...a);
    if (typeof AudioDestinationNode !== 'undefined' && dest instanceof AudioDestinationNode && !this.__tap) {
      this.__tap = true; const ctx = this.context;
      const hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 100;
      const sp = ctx.createScriptProcessor(4096, 2, 1), mute = ctx.createGain(); mute.gain.value = 0;
      orig.call(this, hp); orig.call(hp, sp); orig.call(sp, mute); orig.call(mute, ctx.destination);
      sp.onaudioprocess = e => {
        const L = e.inputBuffer.getChannelData(0), R = e.inputBuffer.numberOfChannels > 1 ? e.inputBuffer.getChannelData(1) : L;
        let s = 0; for (let i = 0; i < L.length; i++) s += (L[i] * L[i] + R[i] * R[i]) / 2;
        window.__lv.sq += s; window.__lv.n += L.length; window.__lv.blocks.push(s / L.length);
      };
    }
    return r;
  };
})();
"""

# экран: (подпись, параметры адреса, JS после первого жеста)
SCREENS = [
    ('Заставки', 'screen=splash', ''),
    ('Дверь (до звонка)', 'screen=door', ''),
    ('Дверь открыта', 'screen=door', "Snd.forceMode='doorOpen'"),
    ('Вступление', 'screen=intro', ''),
    ('Подпись', 'screen=sign', ''),
    ('График смен', 'screen=shifts', ''),
    ('Настройки', 'screen=settings', ''),
    ('Задание на смену (бланк)', 'level=1', 'startLevel(0,false)'),
    ('Смена 1, покой', 'level=1', ''),
    ('Смена 6, 90 %', 'level=6', ''),
    ('Смена 9, 80 %', 'level=9', ''),
    ('Пауза', 'level=9', 'togglePause()'),
    ('Журнал смены', 'screen=result&level=2', ''),
    ('Сдача смены (момент)', 'moment=dawn', ''),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sec', type=float, default=4); ap.add_argument('--md', default=str(ROOT / 'polish' / 'sound' / 'P5-mix-levels.md'))
    a = ap.parse_args()
    import math
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as p:
        br = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for name, q, js in SCREENS:
            ctx = br.new_context(viewport={'width': 1366, 'height': 768}); ctx.add_init_script(TAP); pg = ctx.new_page()
            pg.goto(GAME.as_uri() + '?' + q, wait_until='load'); pg.wait_for_timeout(300)
            pg.evaluate("Snd.init()")                 # жест не нужен: автозапуск разрешён флагом
            pg.wait_for_timeout(3000)                 # «мир» поднимается после первого касания (SOUND.intro)
            if js: pg.evaluate(js); pg.wait_for_timeout(1200)
            pg.evaluate('window.__lv.reset()'); pg.wait_for_timeout(int(a.sec * 1000))
            lv = pg.evaluate('({sq: __lv.sq, n: __lv.n, blocks: __lv.blocks})')
            mean = 10 * math.log10(lv['sq'] / lv['n']) if lv['n'] and lv['sq'] > 0 else -120
            top = 10 * math.log10(max(lv['blocks'])) if lv['blocks'] and max(lv['blocks']) > 0 else -120
            rows.append((name, round(mean, 1), round(top, 1))); ctx.close()
        br.close()
    md = ['| Экран | Средняя, дБFS | Самый громкий блок ~85 мс, дБFS |', '|---|---|---|'] + [f'| {r[0]} | {r[1]} | {r[2]} |' for r in rows]
    out = '\n'.join(md); print(out)
    Path(a.md).write_text('# Громкость смеси по экранам (П5)\n\n' + out + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
