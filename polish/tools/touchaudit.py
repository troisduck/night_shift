#!/usr/bin/env python3
"""Аудит звука по карте касаний (задание 4, раздел 13): каждое касание и событие — со звуком, наведение — без.

  python polish/tools/touchaudit.py [--md polish/sound/P5-touch-audit.md]

Настоящая мышь и клавиатура Playwright; разовые звуки ловятся обёрткой Snd.cue (имя и время), поэтому аудит
не зависит от того, разрешил ли браузер звук. Слои станции (привод стержней, дизели, выбег) — не разовые звуки:
их наличие видно по полю «слой» (изменение состояния, которое ведёт слой). Пусто там, где звук должен быть, — ✗.
"""
import argparse, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'night-shift-4.html'

HOOK = """
window.__cues = [];
const o = Snd.cue.bind(Snd); Snd.cue = (n, op) => { window.__cues.push(n); return o(n, op); };
"""

# (подпись, параметры адреса, подготовка JS, действие, ожидаемо ли молчание)
# действие: ('click', css) | ('hold', css, мс) | ('key', code) | ('hover', css) | ('js', code)
CASES = [
    ('Наведение на кнопку ВВЕРХ', 'level=9&unlockall=1', '', ('hover', '#btn-up'), True),
    ('ВВЕРХ (удержание)', 'level=9&unlockall=1', '', ('hold', '#btn-up', 500), False),
    ('ВНИЗ (удержание)', 'level=9&unlockall=1', '', ('hold', '#btn-down', 500), False),
    ('ОТКРЫТЬ клапан', 'level=9&unlockall=1', '', ('hold', '#btn-vplus', 200), False),
    ('ПРИКРЫТЬ клапан', 'level=9&unlockall=1', '', ('hold', '#btn-vminus', 200), False),
    ('ДОБАВИТЬ бор', 'level=9&unlockall=1', '', ('hold', '#btn-bplus', 200), False),
    ('РАЗБАВИТЬ', 'level=9&unlockall=1', '', ('hold', '#btn-bminus', 200), False),
    ('НАГРЕВ (ручное давление)', 'level=9&unlockall=1', 'UI.game.s.flags.autoPressure=false', ('click', '#btn-heat'), False),
    ('ВПРЫСК (ручное давление)', 'level=9&unlockall=1', 'UI.game.s.flags.autoPressure=false', ('click', '#btn-spray'), False),
    ('НАГРЕВ под автоматикой', 'level=9&unlockall=1', 'UI.game.s.flags.autoPressure=true', ('click', '#btn-heat'), False),
    ('Тумблер ГЦН', 'level=9&unlockall=1', '', ('click', '#pt-1'), False),
    ('ПУСК ДГ, когда дизели уже работают', 'level=9&unlockall=1', "UI.game.s.dg='on'", ('click', '#btn-dg'), False),
    ('Подпись: «Сдать» без росчерка', 'screen=sign', '', ('click', '.sg-ok'), False),
    ('Подпись: «Стереть» без росчерка', 'screen=sign', '', ('click', '.sg-erase'), False),
    ('ПУСК ДГ', 'level=9&unlockall=1', '', ('click', '#btn-dg'), False),
    ('Крышка АЗ', 'level=9&unlockall=1', '', ('click', '#az-cover'), False),
    ('Гриб АЗ', 'level=9&unlockall=1', 'openAZ()', ('click', '#btn-az'), False),
    ('Пломба ключа защит', 'level=1', '', ('click', '#btn-prot'), False),
    ('Ключ вывода защит', 'level=1', 'UI.game.breakSeal()', ('click', '#btn-prot'), False),
    ('Ключ защит в «Без страховки» (ключа нет)', 'level=10', '', ('click', '#btn-prot'), False),
    ('КВИТИРОВАНИЕ', 'level=9&unlockall=1', '', ('click', '#btn-ack'), False),
    ('ВЫЗОВ', 'level=9&unlockall=1', '', ('click', '#btn-what'), False),
    ('Пауза (кнопка)', 'level=9&unlockall=1', '', ('click', '#btn-pause'), False),
    ('Скорость ×2', 'level=9&unlockall=1', '', ('click', '.spd[data-spd="2"]'), False),
    ('Громкость (панель)', 'level=9&unlockall=1', '', ('click', '#btn-vol'), False),
    ('Звук вкл/выкл', 'level=9&unlockall=1', '', ('click', '#btn-sound'), False),
    ('Заново', 'level=9&unlockall=1', '', ('click', '#btn-restart'), False),
    ('Смены (выход)', 'level=9&unlockall=1', '', ('click', '#btn-menu'), False),
    ('Заглушка (смена 1)', 'level=1', '', ('click', '.blk.locked > .cover'), False),
    ('Орган на паузе', 'level=9&unlockall=1', 'togglePause()', ('hold', '#btn-vplus', 200), False),
    ('Клавиша ↑', 'level=9&unlockall=1', '', ('key', 'ArrowUp'), False),
    ('Клавиша →', 'level=9&unlockall=1', '', ('key', 'ArrowRight'), False),
    ('Клавиша Пробел', 'level=9&unlockall=1', '', ('key', 'Space'), False),
    ('Клавиша Q', 'level=9&unlockall=1', '', ('key', 'KeyQ'), False),
    ('Клавиша ? (наложение)', 'level=9&unlockall=1', '', ('key', 'Slash'), False),
    ('Бланк: «Принять смену»', 'level=1', 'UI.game=null; startLevel(1,false)', ('click', '#mb-go'), False),
    ('Журнал: «Ещё раз»', 'screen=result&level=2', '', ('click', '#mr-retry'), False),
    ('Журнал: «К сменам»', 'screen=result&level=2', '', ('click', '#mr-menu'), False),
    ('График смен: смена', 'screen=shifts', '', ('click', '.gs-b.next, .gs-b.lit'), False),
    ('График смен: закрытая смена', 'screen=shifts', '', ('click', '.gs-b.dead'), False),
    ('График смен: пломба «Без страховки»', 'screen=shifts', '', ('click', '.gs-cov'), False),
    ('Событие: отказ насоса', 'level=6', "UI.game.events.push({t:UI.game.t+0.1,type:'pumpTrip',pump:1})", ('wait', 900), False),
    ('Событие: блэкаут', 'level=6', "UI.game.events.push({t:UI.game.t+0.1,type:'blackout'})", ('wait', 900), False),
    ('Событие: АЗ автоматикой', 'level=9', "UI.game.s.h=0", ('wait', 3500), False),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--md', default=str(ROOT / 'polish' / 'sound' / 'P5-touch-audit.md'))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    rows, bad = [], 0
    with sync_playwright() as p:
        br = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for name, q, prep, act, silent in CASES:
            pg = br.new_context(viewport={'width': 1366, 'height': 768}).new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(GAME.as_uri() + '?' + q, wait_until='load'); pg.wait_for_timeout(900)
            pg.evaluate(HOOK)
            if prep: pg.evaluate(prep)
            if act[0] != 'wait': pg.wait_for_timeout(250); pg.evaluate('window.__cues = []')   # события ловим с начала подготовки
            try:
                k = act[0]
                if k == 'hover': pg.hover(act[1]); pg.wait_for_timeout(700)
                elif k == 'click': pg.locator(act[1]).first.click(timeout=3000, force=True); pg.wait_for_timeout(400)
                elif k == 'hold':
                    box = pg.locator(act[1]).first.bounding_box(); pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                    pg.mouse.down(); pg.wait_for_timeout(act[2]); pg.mouse.up(); pg.wait_for_timeout(300)
                elif k == 'key': pg.keyboard.down(act[1]); pg.wait_for_timeout(250); pg.keyboard.up(act[1]); pg.wait_for_timeout(300)
                elif k == 'wait': pg.wait_for_timeout(act[1])
            except Exception as e:
                errs.append('действие: ' + str(e).splitlines()[0])
            cues = [c for c in pg.evaluate('window.__cues') if c]   # первый null — артефакт установки перехвата, не игры
            ok = (not cues) if silent else bool(cues)
            if not ok: bad += 1
            rows.append((name, ', '.join(dict.fromkeys(str(c) for c in cues)) or '—', '✓' if ok else '✗', '; '.join(errs)))
            pg.context.close()
        br.close()
    md = ['| Касание или событие | Разовые звуки | Итог | Заметки |', '|---|---|---|---|'] + [f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} |' for r in rows]
    out = '\n'.join(md); print(out); print(f'\n✗ {bad}')
    Path(a.md).write_text('# Аудит звука по карте касаний (П5)\n\n' + out + f'\n\n✗ {bad}\n', encoding='utf-8')


if __name__ == '__main__':
    main()
