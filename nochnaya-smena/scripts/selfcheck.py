#!/usr/bin/env python3
"""Самопроверка «Ночной смены» на ИИшность: статический скан + визуал + звук одним запуском.

  python3 selfcheck.py игра.html [--out selfcheck] [--state "level=1&paused=1"] [--size 1920x1080]
                                 [--scenario default,startup] [--no-visual] [--no-audio]

Пишет REPORT.md, скриншоты и спектрограммы в --out. Код выхода 1, если есть ✗ (сдавать нельзя).
Чего нет в окружении (playwright, chromium, numpy), то пропускается с пометкой в отчёте.
"""
import sys

sys.dont_write_bytecode = True  # папка скилла бывает только для чтения

import argparse  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import static_scan  # noqa: E402

SLOP, CHECK = "✗", "?"


def _count(findings):
    return sum(f["sev"] == SLOP for f in findings), sum(f["sev"] == CHECK for f in findings)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--out", default="selfcheck")
    ap.add_argument("--state", action="append", help="состояние экрана — параметры адреса без '?'; можно несколько")
    ap.add_argument("--size", action="append", help="размер окна, например 1920x1080; можно несколько")
    ap.add_argument("--scenario", default="default,startup", help="звуковые сценарии через запятую или путь к JSON")
    ap.add_argument("--no-visual", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    a = ap.parse_args()

    game = Path(a.file)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sections, look, listen = [], [], []

    st = static_scan.scan(game)
    slop, check, sup = static_scan.counts(st)
    sections.append(static_scan.to_markdown(st, game.name))

    if not a.no_visual:
        try:
            import visual_check
            v = visual_check.run(game, out, a.state, a.size)
            sections.append(visual_check.to_markdown(v))
            s, c = _count(v["findings"])
            slop, check = slop + s, check + c
            for shot in v["shots"]:          # одинаковые состояния смотреть дважды незачем
                if not shot["dup_of"]:
                    look += [shot["png"], shot["sheet"]]
        except ImportError as e:
            sections.append(f"## Визуал\nПропущено ({e}). Без скриншотов пройди CSS по чеклисту visual.md "
                            "и прямо скажи автору, что картинку не видел.")
        except Exception as e:  # браузер не поднялся и т.п.
            sections.append(f"## Визуал\nСкриншоты не получились: {e}")

    if not a.no_audio:
        try:
            import audio_check
            parts = ["## Звук (оффлайн-рендер в Chromium)"]
            for name in [x.strip() for x in a.scenario.split(",") if x.strip()]:
                r = audio_check.run(game, out, name)
                parts.append(audio_check.to_markdown(r))
                s, c = _count(r["findings"])
                slop, check = slop + s, check + c
                if r.get("spectrogram"):
                    look.append(r["spectrogram"])
                if r.get("wav"):
                    listen.append(r["wav"])
                if r.get("skipped"):
                    break
            sections.append("\n\n".join(parts))
        except ImportError as e:
            sections.append(f"## Звук\nПропущено ({e}). Пройди код звука по чеклисту sound.md; замеров нет — так и скажи автору.")
        except Exception as e:
            sections.append(f"## Звук\nРендер не получился: {e}")

    head = [f"# Самопроверка «Ночной смены»: {game.name}",
            f"Итог: ✗ {slop} · ? {check} · помечено ns-ok: {sup}",
            "✗ есть — сдавать нельзя: убери найденное и перезапусти." if slop else
            "✗ нет. Каждое «?» исправь или оставь осознанно с комментарием ns-ok: <причина>.", ""]
    if look:
        head.append("Посмотреть глазами (view): " + ", ".join(look))
    if listen:
        head.append("Дать послушать автору: " + ", ".join(listen))
    head.append("Чеклисты для глаз: references/visual.md («Проверка глазами»), references/sound.md («Признаки ИИшного звука»).")
    report = "\n".join(head) + "\n\n" + "\n\n".join(sections) + "\n"
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    sys.exit(1 if slop else 0)


if __name__ == "__main__":
    main()
