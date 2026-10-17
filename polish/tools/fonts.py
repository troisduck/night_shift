#!/usr/bin/env python3
"""Встроенные шрифты «Ночной смены»: подмножества OFL-шрифтов → base64 @font-face внутри игры.

  python polish/tools/fonts.py --src <папка с исходными ttf> [--game night-shift-4.html]

Что делает:
  1. Режет каждый шрифт до нужных знаков (латиница, кириллица, знаки щита), сохраняет woff2 в polish/fonts/.
  2. Переименовывает семейство: по OFL подмножество — изменённая версия, а у PT и OpenGOST есть
     зарезервированные имена (Reserved Font Name). Поэтому в игре они называются NS Gost, NS Narrow и т. д.
  3. Вписывает @font-face между маркерами «ВСТРОЕННЫЕ ШРИФТЫ» в игре. Внешних запросов нет.
Исходники: google/fonts (ofl/robotocondensed — начертание 700 из переменного, ptsans, ptsansnarrow, ptmono, badscript).
"""
import argparse, base64, io, re, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]

# семейство в игре, начертание, файл-исходник, роль (для комментария)
FACES = [
    ("NS Plate",  700, "RobotoCondensed-Bold.ttf",           "краска и гравировка по металлу: шильды, кнопки, заглушки, дверь (Roboto Condensed Bold, как в HighFleet)"),
    ("NS Narrow", 400, "ptsansnarrow_PT_Sans-Narrow-Web-Regular.ttf", "табло, шкалы, мелкие подписи на щите (PT Sans Narrow)"),
    ("NS Narrow", 700, "ptsansnarrow_PT_Sans-Narrow-Web-Bold.ttf",    "то же, жирное"),
    ("NS Sans",   400, "ptsans_PT_Sans-Web-Regular.ttf",     "слой игры и текст для чтения (PT Sans)"),
    ("NS Sans",   700, "ptsans_PT_Sans-Web-Bold.ttf",        "то же, жирное"),
    ("NS Mono",   400, "ptmono_PTM55FT.ttf",                 "машинопись: бланки, журнал (PT Mono)"),
    ("NS Serif",  700, "ptserif_PT_Serif-Web-Bold.ttf",      "типография: заголовки бланков и приказов (PT Serif Bold)"),
    ("NS Hand",   400, "badscript_BadScript-Regular.ttf",    "рукопись: пометки, записки, подписи (Bad Script)"),
]
COPYRIGHT = {
    "NS Plate":  "Roboto Condensed © 2011 The Roboto Project Authors",
    "NS Narrow": "PT Sans Narrow © 2010 ParaType Ltd.; Reserved Font Names «PT Sans», «ParaType»",
    "NS Sans":   "PT Sans © 2010 ParaType Ltd.; Reserved Font Names «PT Sans», «ParaType»",
    "NS Mono":   "PT Mono © 2011 ParaType Ltd.; Reserved Font Names «PT Sans», «PT Serif», «PT Mono», «ParaType»",
    "NS Serif":  "PT Serif © 2010 ParaType Ltd.; Reserved Font Names «PT Sans», «PT Serif», «ParaType»",
    "NS Hand":   "Bad Script © 2011 The Bad Script Project Authors",
}
# знаки: печатная латиница, кириллица с Ё, типографика, единицы и стрелки щита
UNICODES = (
    list(range(0x20, 0x7F)) + [0xA0, 0xAB, 0xB0, 0xB1, 0xB7, 0xBB, 0xD7] +
    [0x401, 0x451] + list(range(0x410, 0x450)) +
    [0x2009, 0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2018, 0x2019, 0x201A, 0x201C, 0x201D, 0x201E, 0x2022, 0x2026, 0x202F,
     0x2030, 0x2032, 0x2033, 0x2116, 0x2190, 0x2191, 0x2192, 0x2193, 0x2212, 0x2248, 0x2264, 0x2265, 0x25B2, 0x25BC]
)
BEGIN = "/* ===== ВСТРОЕННЫЕ ШРИФТЫ"
END = "/* ===== /ВСТРОЕННЫЕ ШРИФТЫ ===== */"


def build(src, out):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    out.mkdir(parents=True, exist_ok=True)
    faces = []
    for fam, wt, fn, role in FACES:
        f = TTFont(str(src / fn))
        opts = subset.Options(); opts.flavor = "woff2"; opts.layout_features = ["kern", "liga", "tnum", "lnum", "pnum"]
        opts.name_IDs = [0, 1, 2, 3, 4, 5, 6]; opts.notdef_outline = True; opts.hinting = False; opts.desubroutinize = True
        sub = subset.Subsetter(opts); sub.populate(unicodes=UNICODES); sub.subset(f)
        style = "Bold" if wt == 700 else "Regular"
        ps = fam.replace(" ", "") + "-" + style
        for rec in f["name"].names:   # переименование: без зарезервированных имён
            if rec.nameID in (1, 16): rec.string = fam
            elif rec.nameID in (4,): rec.string = f"{fam} {style}"
            elif rec.nameID in (6,): rec.string = ps
            elif rec.nameID in (3,): rec.string = f"{ps}; subset for Night Shift"
            elif rec.nameID in (17,): rec.string = style
        buf = io.BytesIO(); f.flavor = "woff2"; f.save(buf)
        data = buf.getvalue()
        (out / f"{ps}.woff2").write_bytes(data)
        faces.append((fam, wt, role, data))
        print(f"{ps}: {len(data) / 1024:.1f} КБ")
    return faces


def css(faces):
    lines = [BEGIN + ": подмножества OFL-шрифтов, собирает polish/tools/fonts.py — руками не править =====",
             "   Лицензия всех семейств — SIL Open Font License 1.1 (https://openfontlicense.org). Семейства переименованы:",
             "   подмножество по OFL — изменённая версия, а у исходников есть зарезервированные имена."]
    for fam, c in COPYRIGHT.items():
        lines.append(f"   {fam} — {c}.")
    lines.append("*/")
    for fam, wt, role, data in faces:
        b64 = base64.b64encode(data).decode()
        lines.append(f"/* {fam} {wt} — {role} */")
        lines.append(f'@font-face {{ font-family: "{fam}"; font-weight: {wt}; font-style: normal; font-display: block; src: url(data:font/woff2;base64,{b64}) format("woff2"); }}')
    lines.append(END)
    return "\n".join(lines)


def inject(game, block):
    t = game.read_text(encoding="utf-8")
    if BEGIN in t:
        a = t.index(BEGIN); b = t.index(END) + len(END)
        t = t[:a] + block + t[b:]
    else:
        t = t.replace("<style>\n", "<style>\n" + block + "\n", 1)
    game.write_text(t, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True)
    ap.add_argument("--game", default=str(ROOT / "night-shift-4.html"))
    ap.add_argument("--out", default=str(ROOT / "polish" / "fonts"))
    a = ap.parse_args()
    faces = build(Path(a.src), Path(a.out))
    block = css(faces)
    inject(Path(a.game), block)
    print(f"Вписано в {a.game}: {len(block) / 1024:.0f} КБ")


if __name__ == "__main__":
    main()
