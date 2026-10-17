#!/usr/bin/env python3
"""Статический скан «Ночной смены» на ИИшные признаки визуала, звука и текста.

  python3 static_scan.py игра.html [--json out.json]

Без зависимостей.  ✗ — почти всегда штамп: убрать или заменить.
?  — проверь глазами; оставляй, только если есть причина, и пометь строку
комментарием  ns-ok: <причина>  (на той же или на предыдущей строке).
Общие проверки без строки гасятся комментарием  ns-ok: <код правила>  в любом месте файла.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import math
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

SLOP, CHECK = "✗", "?"


@dataclass
class Finding:
    sev: str
    rule: str
    msg: str
    hint: str
    line: int = 0
    text: str = ""
    suppressed: bool = False


# ---------------------------------------------------------------- цвета
NAMED = {
    "purple": (128, 0, 128), "violet": (238, 130, 238), "indigo": (75, 0, 130),
    "blueviolet": (138, 43, 226), "darkviolet": (148, 0, 211), "mediumpurple": (147, 112, 219),
    "rebeccapurple": (102, 51, 153), "magenta": (255, 0, 255), "fuchsia": (255, 0, 255),
    "cyan": (0, 255, 255), "aqua": (0, 255, 255),
}
HEX_RE = re.compile(r"(?<![\w&/])#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_-])")
RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})[\s,]+(\d{1,3})[\s,]+(\d{1,3})")
HSL_RE = re.compile(r"hsla?\(\s*(-?\d+(?:\.\d+)?)(?:deg)?[\s,]+(\d+(?:\.\d+)?)%[\s,]+(\d+(?:\.\d+)?)%")
NAMED_RE = re.compile(r"(?<![\w-])(" + "|".join(NAMED) + r")(?![\w-])", re.I)


def _hsl(rgb):
    r, g, b = (c / 255 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s, l


def colors_in(s: str):
    out = []
    for m in HEX_RE.finditer(s):
        hx = m.group(1)
        if len(hx) == 3:
            hx = "".join(c * 2 for c in hx)
        out.append(_hsl(tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))))
    for m in RGB_RE.finditer(s):
        out.append(_hsl(tuple(min(255, int(m.group(i))) for i in (1, 2, 3))))
    for m in HSL_RE.finditer(s):
        out.append((float(m.group(1)) % 360, float(m.group(2)) / 100, float(m.group(3)) / 100))
    for m in NAMED_RE.finditer(s):
        out.append(_hsl(NAMED[m.group(1).lower()]))
    return out


def is_violet(h, s, l):
    return 250 <= h <= 300 and s >= 0.35 and 0.18 <= l <= 0.85


def is_neon(h, s, l):
    return s >= 0.7 and l >= 0.45 and (165 <= h <= 200 or 300 < h <= 335)


def hue_spread(hues):
    if len(hues) < 2:
        return 0.0
    hs = sorted(hues)
    gap = max([hs[i + 1] - hs[i] for i in range(len(hs) - 1)] + [360 - hs[-1] + hs[0]])
    return 360 - gap


# ---------------------------------------------------------------- правила по строкам
# (код, важность, шаблон, что не так, чем заменить, строка должна ещё содержать)
LINE_RULES = [
    ("V-glass", SLOP, r"backdrop-filter\s*:", "Стекло (backdrop-filter) — штамп glassmorphism.",
     "Непрозрачная крашеная панель щита.", None),
    ("V-grad-text", SLOP, r"background-clip\s*:\s*text", "Градиентный текст.",
     "Ровный цвет; акцент — размером и местом.", None),
    ("V-ext-font", SLOP, r"fonts\.(?:googleapis|gstatic)\.com|@font-face[^}]*url\(\s*['\"]?https?:",
     "Внешние шрифты — нарушают «один файл без зависимостей».", "Системные шрифты по ролям (visual.md).", None),
    ("V-ext-dep", SLOP,
     r"<script[^>]+src\s*=\s*['\"]https?:|<link[^>]+href\s*=\s*['\"]https?:|url\(\s*['\"]?https?:"
     r"|\bfrom\s+['\"]https?:|<img[^>]+src\s*=\s*['\"]https?:",
     "Внешняя зависимость (CDN, картинка или стиль по ссылке).", "Всё внутри файла: SVG/CSS/Canvas, звук — синтезом.", None),
    ("V-scifi-font", SLOP,
     r"font-family[^;{}]*\b(?:Orbitron|Exo|Rajdhani|Audiowide|Share Tech|Michroma|Oxanium|Tektur|Chakra Petch"
     r"|Electrolize|Aldrich|Press Start 2P|VT323|Major Mono)\b",
     "Sci-fi/ретро-шрифт.", "Шильды — узкий гротеск, показания — табличные цифры (visual.md).", None),
    ("V-saas-font", CHECK,
     r"font-family[^;{}]*\b(?:Inter|Poppins|Montserrat|Space Grotesk|DM Sans|Manrope|Plus Jakarta Sans|Sora|Outfit|Urbanist)\b",
     "Дефолтный шрифт SaaS-набора.", "Системный стек по ролям (visual.md).", None),
    ("V-scifi-words", CHECK, r"\b(?:hud|holo\w*|cyber\w*|neon\w*|glitch\w*|scanlines?|hologram\w*)\b",
     "Sci-fi-лексика в классах и коде — признак «кибер»-стиля.", "Советский щит: металл, бумага, лампы.", None),
    ("V-precision", SLOP, r"toFixed\(\s*[3-9]\s*\)", "Лишняя точность на экране.",
     "МВт и °C целыми, МПа до 0,1, % целыми или до 0,1.", None),
    ("V-precision-2", CHECK, r"toFixed\(\s*2\s*\)", "Два знака после запятой — нужна ли такая точность?",
     "Обычно хватает 0,1.", None),
    ("T-eng-caps", SLOP, r"['\"`>]\s*[A-Z]{3,}(?:[ :]+[A-Z]{2,})+\s*['\"`<]",
     "Английский/псевдотехнический текст в интерфейсе.",
     "По-русски и простыми словами; аббревиатура — с расшифровкой в подсказке.", None),
    ("T-eng-text", CHECK, r">\s*[A-Z][a-z]{2,}(?:\s+[A-Za-z]{2,})*\s*<", "Английский текст в разметке.",
     "Интерфейс на русском.", None),
    ("A-tts", SLOP, r"speechSynthesis|SpeechSynthesisUtterance", "Роботизированный голос браузера.",
     "Текст наставника + щелчок селектора (cue 'mentor').", None),
    ("A-files", SLOP, r"new\s+Audio\s*\(|<audio\b|['\"][^'\"\s]+\.(?:mp3|wav|ogg|m4a|flac)['\"]",
     "Звуковые файлы вместо синтеза.", "Синтез в Web Audio (sound.md): один файл без зависимостей.", None),
    ("A-data-audio", CHECK, r"data:audio/", "Вшитый аудиофайл: раздувает игру и звучит одинаково каждый раз.",
     "Синтез с вариациями.", None),
    ("A-raw-wave", CHECK, r"['\"](?:square|sawtooth)['\"]", "Голый квадрат/пила — аркадный писк.",
     "Механика — шумовые всплески + удар; квадрат/пила только внутри сложного звука через фильтры (тогда ns-ok).",
     r"type|osc|Osc|wave|tone|beep"),
    ("A-value-jump", CHECK, r"\.(?:gain|frequency|detune|Q|playbackRate|pan)\.value\s*=(?!=)",
     "Присваивание .value на ходу — щелчок или «молния».",
     "setTargetAtTime / linearRampToValueAtTime; при создании узла — setValueAtTime.", None),
    ("A-music", CHECK, r"\b(?:music|melody|arpeggio|chord|bgm|soundtrack)\b", "Музыка поверх станции?",
     "В игре музыки нет: станция и есть саундтрек.", None),
]
LINE_RULES = [(i, s, re.compile(p), m, h, re.compile(n) if n else None) for i, s, p, m, h, n in LINE_RULES]

TEXT_RULES = [  # только для строк с кириллицей: реплики и подписи
    ("T-praise", CHECK, r"(?i)(?:отлично|превосходно|великолепно|потрясающе|супер|молодец|умница|поздравля\w*)\s*!",
     "Дежурная похвала.", "Сухо и по делу: что получилось и почему."),
    ("T-filler", CHECK,
     r"(?i)(?:давайте|важно отметить|стоит отметить|не забывайте|погрузи\w*|увлекательн\w*|захватывающ\w*"
     r"|добро пожаловать|в мир\b|играет (?:важную|ключевую) роль|невероятн\w*|не волнуйтесь)",
     "ИИ-копирайтинг.", "Короткая реплика начальника смены: причина → следствие."),
    ("T-bang", CHECK, r"!{2,}|!\s+!", "Восклицания подряд.", "Наставник не кричит."),
]
TEXT_RULES = [(i, s, re.compile(p), m, h) for i, s, p, m, h in TEXT_RULES]

CYR = re.compile(r"[А-Яа-яЁё]")
COMMENT_ONLY = re.compile(r"^\s*(?://|/\*|\*|<!--)")
EMOJI_HARD = re.compile("[\U0001F000-\U0001FAFF]|\uFE0F")
EMOJI_SOFT = re.compile("[\u2600-\u26FF\u2700-\u27BF\u2B50\u2B55\u23E9-\u23FA]")
SOFT_OK = set("✓✔✕✖✗✘")
SHADOW_RE = re.compile(r"(box-shadow|text-shadow)\s*:\s*([^;}{]+)", re.I)
DROP_RE = re.compile(r"drop-shadow\(((?:[^()]|\([^()]*\))*)\)", re.I)
LEN_RE = re.compile(r"(-?\d*\.?\d+)(px|rem|em)?")
KEYFRAMES_RE = re.compile(r"@keyframes\s+([\w-]+)")
SUSPECT_ANIM = re.compile(r"pulse|glow|shimmer|float|bounce|breath|glitch|flicker|scan|neon|wave|gradient|shine"
                          r"|sparkle|orbit|levitat", re.I)
INFINITE_RE = re.compile(r"animation(?:-iteration-count)?\s*:[^;{}]*\binfinite\b")
RADIUS_RE = re.compile(r"border-radius\s*:\s*(\d+(?:\.\d+)?)px")
SOFTSHADOW_RE = re.compile(r"box-shadow\s*:[^;{}]*rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0?\.(?:0[5-9]|1\d?|2)\s*\)")

AUDIO_ANY = re.compile(r"AudioContext|createOscillator|createBufferSource")
RAMP_RE = re.compile(r"linearRampToValueAtTime|exponentialRampToValueAtTime|setTargetAtTime|setValueCurveAtTime")
START_RE = re.compile(r"\.start\(")
COMP_RE = re.compile(r"createDynamicsCompressor|DynamicsCompressorNode")
NEWCTX_RE = re.compile(r"new\s+(?:window\.)?(?:webkit)?AudioContext\b")
RESUME_RE = re.compile(r"\.resume\(")
VIS_RE = re.compile(r"visibilitychange")
MUTE_RE = re.compile(r"mute|setVolume|volume|громкост|звук\s*выкл", re.I)
RAWNOISE_RE = re.compile(r"Math\.random\(\)\s*\*\s*2\s*-\s*1")
FILTER_RE = re.compile(r"createBiquadFilter|BiquadFilterNode")
ARRAY_RE = re.compile(r"\[([^\[\]]{5,240})\]")
NUM_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
RM_RE = re.compile(r"prefers-reduced-motion")
ANIM_ANY = re.compile(r"@keyframes|animation\s*:")


def _split_top(s):
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _glow(part):
    if "inset" in part:
        return False
    cols = colors_in(part)
    rest = re.sub(r"rgba?\([^)]*\)|hsla?\([^)]*\)|#[0-9a-fA-F]{3,8}", " ", part)
    nums = [float(m.group(1)) * (16 if m.group(2) in ("rem", "em") else 1) for m in LEN_RE.finditer(rest)]
    if len(nums) < 3:
        return False
    x, y, blur = nums[0], nums[1], nums[2]
    if abs(x) > 1 or abs(y) > 1 or blur < 8:
        return False
    return any(s >= 0.3 for _, s, _ in cols)


def _is_note(f):
    if f < 60 or f > 4200:
        return False
    n = 12 * math.log2(f / 440.0)
    return abs(n - round(n)) * 100 < 9          # ближе 9 центов к темперированной ноте


def _melody(nums):
    notes = sorted({x for x in nums if _is_note(x)})
    if len(notes) < 3:
        return False
    lo = notes[0]
    return not all(abs(x / lo - round(x / lo)) < 0.01 for x in notes)   # гармоники одного тона — не мелодия


# ---------------------------------------------------------------- скан
def scan(path) -> list[Finding]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    out: list[Finding] = []

    def add(sev, rule, msg, hint, ln=0, snippet=""):
        sup = False
        if ln:
            near = lines[ln - 1] + (lines[ln - 2] if ln >= 2 else "")
            sup = "ns-ok" in near
        else:
            sup = re.search(r"ns-ok\s*:\s*" + re.escape(rule) + r"\b", text) is not None
        out.append(Finding(sev, rule, msg, hint, ln, snippet.strip()[:140], sup))

    for ln, line in enumerate(lines, 1):
        if COMMENT_ONLY.match(line) or not line.strip():
            continue
        for rid, sev, rx, msg, hint, need in LINE_RULES:
            if rx.search(line) and (need is None or need.search(line)):
                add(sev, rid, msg, hint, ln, line)
        if CYR.search(line):
            for rid, sev, rx, msg, hint in TEXT_RULES:
                if rx.search(line):
                    add(sev, rid, msg, hint, ln, line)
        if EMOJI_HARD.search(line):
            add(SLOP, "V-emoji", "Эмодзи.", "Гравированная подпись или условное обозначение в стиле мнемосхемы.", ln, line)
        elif any(ch not in SOFT_OK for ch in EMOJI_SOFT.findall(line)):
            add(CHECK, "V-pictogram", "Пиктограмма-символ вместо подписи (☢ ⚡ ⚠ ⏸ …).",
                "Подпись словами или условное обозначение, нарисованное в SVG.", ln, line)
        if "gradient(" in line:
            hues = [h for h, s, l in colors_in(line) if s >= 0.3 and 0.15 <= l <= 0.85]
            if hue_spread(hues) > 50:
                add(SLOP, "V-gradient", f"Разноцветный градиент (разброс тонов {hue_spread(hues):.0f}°).",
                    "Ровная эмаль; градиент — только светотень одного тона.", ln, line)
        cols = colors_in(line)
        if any(is_violet(*c) for c in cols):
            add(CHECK, "V-violet", "Фиолетовый/индиго — частый ИИ-штамп, в палитре щита его нет.",
                "Палитра из visual.md.", ln, line)
        if any(is_neon(*c) for c in cols):
            add(CHECK, "V-neon-color", "Неоновый циан/маджента.", "Сигнальные цвета ламп: зелёный, жёлтый, красный, белый.", ln, line)
        for m in SHADOW_RE.finditer(line):
            if any(_glow(p) for p in _split_top(m.group(2))):
                if m.group(1).lower() == "text-shadow":
                    add(SLOP, "V-text-glow", "Светящийся текст (неон).", "Текст не светится; светится только горящая лампа.", ln, line)
                else:
                    add(CHECK, "V-glow", "Свечение рамки/блока.",
                        "Свечение только у горящей лампы, сила по её яркости (тогда ns-ok).", ln, line)
        for m in DROP_RE.finditer(line):
            if _glow(m.group(1)):
                add(CHECK, "V-glow", "Свечение через drop-shadow.", "Только у горящей лампы (тогда ns-ok).", ln, line)
        for m in KEYFRAMES_RE.finditer(line):
            if SUSPECT_ANIM.search(m.group(1)):
                add(CHECK, "V-anim", f"Анимация «{m.group(1)}» — движение без причины?",
                    "Движется только то, что отражает состояние (visual.md, «Движение»).", ln, line)

    # ---------- общие проверки
    infinite = len(INFINITE_RE.findall(text))
    if infinite >= 4:
        add(CHECK, "V-anim-many", f"Бесконечных анимаций: {infinite}.",
            "В покое щит неподвижен: движутся стрелки, поток при расходе, мигание неквитированной тревоги.")
    radii = Counter(float(x) for x in RADIUS_RE.findall(text))
    if sum(radii.values()) >= 8:
        val, cnt = radii.most_common(1)[0]
        if val >= 10 and cnt / sum(radii.values()) >= 0.6:
            add(CHECK, "V-radius", f"Один радиус {val:g}px почти на всём ({cnt} из {sum(radii.values())}) — SaaS-карточки.",
                "Форма по смыслу: панели, шильды, кнопки, лампы — разные.")
    soft = len(SOFTSHADOW_RE.findall(text))
    if soft >= 6:
        add(CHECK, "V-soft-shadow", f"Одинаковая мягкая серая тень повторяется {soft} раз.",
            "Светотень от одного верхнего источника, неглубокая; у панелей — фаска, а не парение.")
    if ANIM_ANY.search(text) and not RM_RE.search(text):
        add(CHECK, "V-reduced-motion", "Нет учёта prefers-reduced-motion.",
            "Поток — статичной стрелкой, мигание — ровным свечением с рамкой.")

    if AUDIO_ANY.search(text):
        ramps, starts = len(RAMP_RE.findall(text)), len(START_RE.findall(text))
        if ramps == 0:
            add(SLOP, "A-no-envelope", "Нет ни одной огибающей (рамп) — будут щелчки на каждом старте и стопе.",
                "Атака/спад рампами 2–10 мс, параметры — setTargetAtTime.")
        elif ramps < starts * 0.5:
            add(CHECK, "A-few-envelopes", f"Рамп мало ({ramps}) на {starts} запусков — часть звуков без огибающей?",
                "У каждого разового звука атака и спад.")
        if not COMP_RE.search(text):
            add(SLOP, "A-no-limiter", "Нет лимитера (DynamicsCompressor) на мастере.", "Мастер: громкость → срез низа → лимитер → выход.")
        if NEWCTX_RE.search(text) and not RESUME_RE.search(text):
            add(SLOP, "A-no-resume", "AudioContext не возобновляется по жесту — в браузере звука не будет.",
                "ctx.resume() на первом нажатии (NightShiftAudio.live() делает это сам).")
        if len(NEWCTX_RE.findall(text)) > 1:
            add(CHECK, "A-many-ctx", "Создаётся несколько AudioContext.", "Один контекст на игру.")
        if not VIS_RE.search(text):
            add(CHECK, "A-no-visibility", "Звук не глушится при сворачивании вкладки.", "visibilitychange → ctx.suspend()/resume().")
        if not MUTE_RE.search(text):
            add(CHECK, "A-no-mute", "Нет выключателя звука/громкости.", "Кнопка звука по ТЗ.")
        if RAWNOISE_RE.search(text) and not FILTER_RE.search(text):
            add(CHECK, "A-raw-noise", "Голый белый шум без фильтров.", "Цветной шум через фильтры с резонансами.")
        for m in ARRAY_RE.finditer(text):
            nums = [float(x) for x in NUM_RE.findall(m.group(1))]
            if len(nums) >= 3 and _melody(nums):
                ln = text.count("\n", 0, m.start()) + 1
                add(CHECK, "A-melody", "Массив темперированных нот — джингл/мелодия?",
                    "Успех — подтверждение от станции (щелчок, сухая реплика), не мелодия.", ln, lines[ln - 1])
    return out


# ---------------------------------------------------------------- отчёт
def counts(findings):
    live = [f for f in findings if not f.suppressed]
    return (sum(f.sev == SLOP for f in live), sum(f.sev == CHECK for f in live),
            sum(f.suppressed for f in findings))


def to_markdown(findings, name="", cap=5) -> str:
    slop, check, sup = counts(findings)
    lines = [f"## Статический скан{': ' + name if name else ''}",
             f"✗ {slop} · ? {check} · помечено ns-ok: {sup}", ""]
    for sev in (SLOP, CHECK):
        groups: dict[str, list[Finding]] = {}
        for f in findings:
            if f.sev == sev and not f.suppressed:
                groups.setdefault(f.rule, []).append(f)
        for rule, fs in groups.items():
            f0 = fs[0]
            where = ", ".join(f"стр. {f.line}" for f in fs[:cap] if f.line)
            more = f" …и ещё {len(fs) - cap}" if len(fs) > cap else ""
            lines.append(f"{sev} [{rule}] {f0.msg}" + (f" ({where}{more})" if where else ""))
            if f0.text:
                lines.append(f"    `{f0.text}`")
            lines.append(f"    → {f0.hint}")
    if not slop and not check:
        lines.append("Формальных признаков не найдено.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--json")
    a = ap.parse_args()
    fs = scan(a.file)
    print(to_markdown(fs, Path(a.file).name))
    if a.json:
        Path(a.json).write_text(json.dumps([asdict(f) for f in fs], ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if counts(fs)[0] else 0)


if __name__ == "__main__":
    main()
