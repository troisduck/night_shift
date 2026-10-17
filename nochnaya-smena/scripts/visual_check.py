#!/usr/bin/env python3
"""Визуальная самопроверка «Ночной смены»: скриншоты в Chromium, аудит DOM, палитра.

  python3 visual_check.py игра.html --out selfcheck [--state "" --state "level=1&paused=1"] [--size 1920x1080]

Пишет: vis_N.png (скриншот), vis_N_sheet.png (слева серый, справа «прищур»), visual_report.json.
Картинки обязательно посмотреть глазами (инструмент view): скрипт ловит формальные признаки, вкус — нет.
Состояния задаются отладочными параметрами адреса (SKILL.md, «Архитектура»).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SLOP, CHECK = "✗", "?"
DEFAULT_STATES = ["", "level=1&paused=1", "unlockall=1&event=alarm_test&paused=1"]
SCIFI_FONTS = re.compile(r"orbitron|exo|rajdhani|audiowide|share tech|michroma|oxanium|tektur|chakra petch|"
                         r"electrolize|aldrich|press start|vt323|major mono", re.I)
SAAS_FONTS = re.compile(r"^(inter|poppins|montserrat|space grotesk|dm sans|manrope|plus jakarta sans|sora|outfit|urbanist)$", re.I)
SUSPECT_ANIM = re.compile(r"pulse|glow|shimmer|float|bounce|breath|glitch|flicker|scan|neon|wave|gradient|shine|sparkle|orbit", re.I)

DOM_AUDIT_JS = r"""
() => {
  const R = {glass: [], glow: [], lampGlow: [], textGlow: [], gradients: [], lowContrast: [], tiny: [],
             fonts: {}, anims: [], emoji: [], latin: [], precise: [], radii: {}, capsEls: 0, textEls: 0, svgText: 0};
  const LAMP = /lamp|led|light|indic|annun|tile|alarm|\blit\b|signal|bulb|ламп|сигн|табло|tablo/i;
  const cls = (el) => (el.getAttribute && el.getAttribute('class')) || '';
  const desc = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    const c = cls(el).trim().split(/\s+/).filter(Boolean).slice(0, 2);
    if (c.length) s += '.' + c.join('.');
    const t = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 32);
    return t ? s + ' «' + t + '»' : s;
  };
  const rgb = (s) => {
    const m = /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)/.exec(s || '');
    if (!m) return null;
    const a = m[4] === undefined ? 1 : (m[4].endsWith('%') ? parseFloat(m[4]) / 100 : parseFloat(m[4]));
    return {r: +m[1], g: +m[2], b: +m[3], a};
  };
  const allRgb = (s) => (String(s || '').match(/rgba?\([^)]*\)/g) || []).map(rgb).filter(Boolean);
  const hsl = (c) => {
    const r = c.r / 255, g = c.g / 255, b = c.b / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    const l = (mx + mn) / 2; let h = 0, s = 0;
    if (mx !== mn) {
      const d = mx - mn; s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
      h = mx === r ? ((g - b) / d + (g < b ? 6 : 0)) : mx === g ? ((b - r) / d + 2) : ((r - g) / d + 4); h *= 60;
    }
    return {h, s, l};
  };
  const lin = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const over = (t, b) => ({r: t.r * t.a + b.r * (1 - t.a), g: t.g * t.a + b.g * (1 - t.a), b: t.b * t.a + b.b * (1 - t.a), a: 1});
  const spread = (hs) => {
    if (hs.length < 2) return 0;
    hs = hs.slice().sort((a, b) => a - b);
    let gap = 360 - hs[hs.length - 1] + hs[0];
    for (let i = 1; i < hs.length; i++) gap = Math.max(gap, hs[i] - hs[i - 1]);
    return 360 - gap;
  };
  const backdrop = (el) => {
    const layers = []; let e = el, approx = false;
    while (e && e.nodeType === 1) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        const cols = allRgb(cs.backgroundImage).filter((c) => c.a > 0.3);
        if (cols.length) return {cands: cols.map((c) => layers.reduceRight((acc, l) => over(l, acc), {r: c.r, g: c.g, b: c.b, a: 1})), approx: true};
        approx = true;
      }
      const c = rgb(cs.backgroundColor);
      if (c && c.a > 0) {
        if (c.a >= 0.99) return {cands: [layers.reduceRight((acc, l) => over(l, acc), c)], approx};
        layers.push(c);
      }
      e = e.parentElement;
    }
    return {cands: [layers.reduceRight((acc, l) => over(l, acc), {r: 255, g: 255, b: 255, a: 1})], approx: true};
  };
  const shadows = (s) => {
    if (!s || s === 'none') return [];
    const parts = []; let depth = 0, cur = '';
    for (const ch of s) {
      if (ch === '(') depth++;
      if (ch === ')') depth--;
      if (ch === ',' && depth === 0) { parts.push(cur); cur = ''; } else cur += ch;
    }
    if (cur.trim()) parts.push(cur);
    return parts.map((p) => {
      const nums = (p.replace(/rgba?\([^)]*\)/g, '').match(/-?[\d.]+px/g) || []).map(parseFloat);
      return {c: rgb(p), x: nums[0] || 0, y: nums[1] || 0, blur: nums[2] || 0, inset: /inset/.test(p)};
    });
  };
  const glowy = (sh) => !sh.inset && Math.abs(sh.x) <= 1 && Math.abs(sh.y) <= 1 && sh.blur >= 8 && sh.c && sh.c.a >= 0.2 && hsl(sh.c).s >= 0.3;
  const drops = (f) => (String(f || '').match(/drop-shadow\((?:[^()]|\([^()]*\))*\)/g) || []).map((d) => shadows(d.slice(12, -1))[0]).filter(Boolean);

  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('script,style,noscript,template')) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.05) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const par = el.parentElement;
    const lampish = LAMP.test(cls(el) + ' ' + el.id) || (par && LAMP.test(cls(par) + ' ' + par.id));
    const bf = cs.backdropFilter || cs.webkitBackdropFilter;
    if (bf && bf !== 'none') R.glass.push(desc(el));
    if (shadows(cs.boxShadow).concat(drops(cs.filter)).some(glowy)) (lampish ? R.lampGlow : R.glow).push(desc(el));
    if (shadows(cs.textShadow).some(glowy)) R.textGlow.push(desc(el));
    if ((cs.backgroundImage || '').includes('gradient(')) {
      const sp = spread(allRgb(cs.backgroundImage).map(hsl).filter((h) => h.s > 0.3 && h.l > 0.15 && h.l < 0.85).map((h) => h.h));
      if (sp > 50) R.gradients.push(desc(el) + ' — разброс тонов ' + Math.round(sp) + '°');
    }
    if (r.width * r.height >= 3000) {
      const br = Math.round(parseFloat(cs.borderTopLeftRadius) || 0);
      if (br > 0) R.radii[br] = (R.radii[br] || 0) + 1;
    }
    let own = '';
    for (const n of el.childNodes) if (n.nodeType === 3) own += n.textContent;
    own = own.replace(/\s+/g, ' ').trim();
    if (!own) continue;
    const isSvg = el instanceof SVGElement;
    if (isSvg) R.svgText++; else R.textEls++;
    const fam = cs.fontFamily.split(',')[0].replace(/["']/g, '').trim();
    R.fonts[fam] = (R.fonts[fam] || 0) + 1;
    const fs = parseFloat(cs.fontSize);
    if (!isSvg && fs < 12) R.tiny.push(desc(el) + ' — ' + fs + 'px');
    const letters = own.replace(/[^A-Za-zА-Яа-яЁё]/g, '');
    if (letters.length >= 4 && (cs.textTransform === 'uppercase' || letters === letters.toUpperCase())) R.capsEls++;
    if (/\p{Emoji_Presentation}|\p{Extended_Pictographic}\uFE0F/u.test(own)) R.emoji.push(desc(el));
    const lat = own.match(/[A-Za-z]{3,}/g);
    if (lat) R.latin.push(desc(el) + ' → ' + [...new Set(lat)].slice(0, 4).join(', '));
    if (/\d[.,]\d{3,}/.test(own)) R.precise.push(desc(el));
    if (!isSvg) {
      const fg = rgb(cs.color);
      if (fg) {
        const bg = backdrop(el);
        const fgc = fg.a < 1 ? over(fg, bg.cands[0]) : fg;
        const worst = Math.min(...bg.cands.map((b) => ratio(fgc, b)));
        const need = (fs >= 24 || (fs >= 18.66 && parseInt(cs.fontWeight, 10) >= 700)) ? 3 : 4.5;
        if (worst < need) R.lowContrast.push({el: desc(el), ratio: Math.round(worst * 100) / 100, need, approx: bg.approx});
      }
    }
  }
  for (const a of document.getAnimations()) {
    let it = 1;
    try { it = a.effect.getComputedTiming().iterations; } catch (e) { /* не CSS-анимация */ }
    if (a.playState === 'running' && it === Infinity) R.anims.push((a.animationName || 'анимация') + ' → ' + (a.effect && a.effect.target ? desc(a.effect.target) : '?'));
  }
  R.lowContrast.sort((x, y) => x.ratio - y.ratio);
  return R;
}
"""


def _font_path():
    try:
        import matplotlib
        p = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"
        return str(p) if p.exists() else None
    except Exception:
        return None


def make_sheet(png, out_png):
    """Слева — серый (различимо ли без цвета), справа — «прищур» (видно ли главное издалека)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
    im = Image.open(png).convert("RGB")
    w, h = im.size
    gray = ImageOps.grayscale(im).convert("RGB")
    squint = im.filter(ImageFilter.GaussianBlur(radius=max(6, w // 160)))
    hw, hh, top = w // 2, h // 2, 34
    sheet = Image.new("RGB", (w, hh + top), (245, 245, 240))
    sheet.paste(gray.resize((hw, hh)), (0, top))
    sheet.paste(squint.resize((hw, hh)), (hw, top))
    d = ImageDraw.Draw(sheet)
    fp = _font_path()
    font = ImageFont.truetype(fp, 20) if fp else ImageFont.load_default()
    d.text((10, 6), "Серый: вкл/выкл и норма/авария различимы без цвета?" if fp else "GRAY", fill=(20, 20, 20), font=font)
    d.text((hw + 10, 6), "Прищур: ключевые показания и тревоги видны издалека?" if fp else "SQUINT", fill=(20, 20, 20), font=font)
    sheet.save(out_png)


def pixel_stats(png):
    import numpy as np
    from PIL import Image
    im = Image.open(png).convert("RGB")
    a = np.asarray(im)[::2, ::2].astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    l, d = (mx + mn) / 2, mx - mn
    s = np.where(d < 1e-6, 0, d / (1 - np.abs(2 * l - 1) + 1e-6))
    dd = d + 1e-9
    hue = np.where(mx == r, ((g - b) / dd) % 6, np.where(mx == g, (b - r) / dd + 2, (r - g) / dd + 4)) * 60
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    Y = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    Lstar = np.where(Y > 0.008856, 116 * np.cbrt(Y) - 16, 903.3 * Y)
    satm = (s > 0.45) & (l > 0.25) & (l < 0.8)
    q = im.quantize(colors=10, method=Image.Quantize.MEDIANCUT)
    pal, cnt = q.getpalette(), sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in cnt)
    return {
        "pastel": round(float(((l > 0.70) & (l < 0.93) & (s > 0.06) & (s < 0.40)).mean()), 3),
        "light_gray_fog": round(float(((s < 0.08) & (l > 0.55) & (l < 0.88)).mean()), 3),
        "lightness_spread": round(float(Lstar.std() / 100), 3),
        "violet": round(float((satm & (hue >= 250) & (hue <= 300)).mean()), 3),
        "neon_cyan": round(float(((s > 0.7) & (l > 0.45) & (hue >= 165) & (hue <= 200)).mean()), 3),
        "top_colors": [("#%02X%02X%02X" % tuple(pal[i * 3:i * 3 + 3]), round(c / total * 100, 1)) for c, i in cnt[:8]],
    }


def _thumb(png):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(png).convert("L").resize((192, 108), Image.BILINEAR), dtype=np.float32)


def _same(a, b):
    """То же состояние, другая фаза анимации: почти нет заметно изменившихся пикселей.
    Калибровка: разные состояния щита ≈ 0,4–0,5 % пикселей, фазы анимации одного ≈ 0–0,01 %."""
    d = abs(a - b)
    return float((d > 24).mean()) < 0.0012 and float(d.mean()) < 0.35


def run(game, out, states=None, sizes=None, wait_ms=1200):
    from playwright.sync_api import sync_playwright
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    states = DEFAULT_STATES if states is None else states
    sizes = sizes or ["1920x1080"]
    shots, audits, errors, thumbs = [], [], [], {}
    url0 = Path(game).resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        k = 0
        for size in sizes:
            w, h = (int(v) for v in size.lower().split("x"))
            for st in states:
                k += 1
                page = browser.new_page(viewport={"width": w, "height": h})
                errs = []
                page.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
                page.on("console", lambda m, errs=errs: errs.append(m.text) if m.type == "error" else None)
                page.goto(url0 + (("?" + st) if st else ""))
                page.wait_for_timeout(wait_ms)
                png = out / f"vis_{k}.png"
                page.screenshot(path=str(png))
                audit = page.evaluate(DOM_AUDIT_JS)
                page.close()
                sheet = out / f"vis_{k}_sheet.png"
                make_sheet(png, sheet)
                stats = pixel_stats(png)
                thumbs[k] = _thumb(png)
                dup = next((s["n"] for s in shots if s["size"] == size and s["dup_of"] is None
                            and _same(thumbs[s["n"]], thumbs[k])), None)
                shots.append({"n": k, "size": size, "state": st or "(по умолчанию)", "png": str(png), "sheet": str(sheet),
                              "md5": hashlib.md5(png.read_bytes()).hexdigest(), "dup_of": dup, "pixels": stats})
                audits.append(audit)
                errors += [f"[{st or 'по умолчанию'}] {e}" for e in errs]
        browser.close()
    rep = {"shots": shots, "audits": audits, "console_errors": list(dict.fromkeys(errors))}
    rep["findings"] = findings_from(rep)
    (out / "visual_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def _uniq(lists, cap=6):
    seen = list(dict.fromkeys(x for lst in lists for x in lst))
    more = f" …и ещё {len(seen) - cap}" if len(seen) > cap else ""
    return seen, "; ".join(seen[:cap]) + more


def findings_from(rep):
    F = []

    def add(sev, rule, msg, hint):
        F.append({"sev": sev, "rule": rule, "msg": msg, "hint": hint})

    A = rep["audits"]
    for key, sev, rule, msg, hint in [
        ("glass", SLOP, "V-glass", "Стекло (backdrop-filter)", "Непрозрачная крашеная панель."),
        ("textGlow", SLOP, "V-text-glow", "Светящийся текст", "Текст не светится; светится только горящая лампа."),
        ("gradients", SLOP, "V-gradient", "Разноцветные градиенты", "Ровная эмаль; градиент — только светотень одного тона."),
        ("emoji", SLOP, "V-emoji", "Эмодзи на экране", "Гравированная подпись или условное обозначение."),
        ("latin", SLOP, "T-latin", "Латиница на экране", "Интерфейс по-русски, единицы — МВт, МПа, °C, об/мин."),
        ("precise", SLOP, "V-precision", "Лишняя точность чисел", "МВт и °C целыми, МПа до 0,1."),
        ("glow", CHECK, "V-glow", "Свечение у элементов, не похожих на лампы", "Свечение только у горящей лампы; если это лампа — дай ей класс lamp/led/tile."),
        ("tiny", CHECK, "V-tiny", "Мелкий текст < 12 px", "Шильды и подписи — от 12 px, ключевые показания — крупно."),
    ]:
        items, text = _uniq([a[key] for a in A])
        if items:
            add(sev, rule, f"{msg} ({len(items)}): {text}", hint)
    lows = {}
    for a in A:
        for c in a["lowContrast"]:
            lows.setdefault(c["el"], c)
    hard = [c for c in lows.values() if c["ratio"] < 3 and not c["approx"]]
    soft = [c for c in lows.values() if c not in hard]
    if hard:
        add(SLOP, "V-contrast", "Нечитаемый контраст текста: " + "; ".join(f"{c['el']} {c['ratio']}:1" for c in hard[:6]),
            "Текст ≥ 4,5:1, крупный ≥ 3:1; ключевые показания — максимальный контраст.")
    if soft:
        add(CHECK, "V-contrast-soft", "Слабый контраст (или фон сложный — проверь глазами): "
            + "; ".join(f"{c['el']} {c['ratio']}:1 (нужно {c['need']})" for c in soft[:6]),
            "Текст ≥ 4,5:1, крупный ≥ 3:1.")
    fams = {}
    for a in A:
        for f, n in a["fonts"].items():
            fams[f] = fams.get(f, 0) + n
    sci = [f for f in fams if SCIFI_FONTS.search(f)]
    saas = [f for f in fams if SAAS_FONTS.match(f)]
    if sci:
        add(SLOP, "V-scifi-font", "Sci-fi-шрифт в интерфейсе: " + ", ".join(sci), "Системные шрифты по ролям (visual.md).")
    if saas:
        add(CHECK, "V-saas-font", "Шрифт SaaS-набора: " + ", ".join(saas), "Системные шрифты по ролям (visual.md).")
    if len(fams) > 3:
        add(CHECK, "V-fonts-many", f"Шрифтов {len(fams)}: " + ", ".join(fams), "Две-три роли: шильды, показания, текст.")
    anims = list(dict.fromkeys(x for a in A[:1] for x in a["anims"]))   # покой — первое состояние
    sus = [x for x in anims if SUSPECT_ANIM.search(x.split(" → ")[0])]
    if len(anims) > 4 or sus:
        add(CHECK, "V-anim", f"Бесконечных анимаций в покое: {len(anims)}" + (f"; подозрительные: {'; '.join(sus[:4])}" if sus else ""),
            "В покое движутся только стрелки, поток при расходе и мигание неквитированной тревоги.")
    radii = {}
    for a in A:
        for k, n in a["radii"].items():
            radii[int(k)] = radii.get(int(k), 0) + n
    tot = sum(radii.values())
    if tot >= 10:
        top, n = max(radii.items(), key=lambda kv: kv[1])
        if top >= 10 and n / tot >= 0.6:
            add(CHECK, "V-radius", f"Один радиус {top}px у {n} из {tot} крупных блоков — SaaS-карточки.", "Форма по смыслу: панели, шильды, кнопки, лампы — разные.")
    caps, txt = sum(a["capsEls"] for a in A), sum(a["textEls"] for a in A)
    if txt >= 8 and caps / txt > 0.6:
        add(CHECK, "V-caps", f"Капс у {caps} из {txt} текстов.", "Капс — только на шильдах и табло; подсказки и реплики — обычным регистром.")
    if rep["console_errors"]:
        add(SLOP, "V-console", "Ошибки в консоли: " + "; ".join(rep["console_errors"][:4]), "Починить: игра ломается у автора так же.")
    sh = rep["shots"]
    if len(sh) > 1 and all(s["dup_of"] for s in sh[1:]):
        add(CHECK, "V-debug-params", "Все состояния выглядят одинаково — отладочные параметры адреса, похоже, не поддерживаются.",
            "Добавь ?level=, ?event=, ?unlockall=, ?paused= (SKILL.md, «Архитектура»).")
    px = sh[0]["pixels"] if sh else None
    if px:
        if px["pastel"] > 0.25:
            add(CHECK, "V-pastel", f"Бледные пастельные площади: {px['pastel'] * 100:.0f} % экрана.", "Тёмная эмаль и насыщенные индикаторы; бледное автор не принимает.")
        if px["light_gray_fog"] > 0.35:
            add(CHECK, "V-fog", f"Светло-серая муть: {px['light_gray_fog'] * 100:.0f} % экрана.", "Контрастная панель: тёмная эмаль, светлые шкалы, яркие лампы.")
        if px["lightness_spread"] < 0.12:
            add(CHECK, "V-flat", f"Низкий общий контраст (разброс светлоты {px['lightness_spread']}).", "Нужны тёмные и светлые зоны: эмаль, шкалы, лампы.")
        if px["violet"] > 0.03:
            add(CHECK, "V-violet", f"Фиолетового {px['violet'] * 100:.0f} % экрана.", "Палитра щита из visual.md.")
        if px["neon_cyan"] > 0.02:
            add(CHECK, "V-neon-color", f"Неонового циана {px['neon_cyan'] * 100:.0f} % экрана.", "Сигнальные цвета ламп: зелёный, жёлтый, красный, белый.")
    return F


def to_markdown(rep) -> str:
    L = ["## Визуал (Chromium)"]
    for s in rep["shots"]:
        px = s["pixels"]
        if s["dup_of"]:
            L.append(f"vis_{s['n']}: {s['size']}, «{s['state']}» — то же, что vis_{s['dup_of']}")
            continue
        L.append(f"vis_{s['n']}: {s['size']}, состояние «{s['state']}» → {s['png']} и {s['sheet']}")
        L.append(f"    палитра: " + ", ".join(f"{c} {p}%" for c, p in px["top_colors"][:6])
                 + f" · пастель {px['pastel'] * 100:.0f} % · разброс светлоты {px['lightness_spread']}")
    lamp = list(dict.fromkeys(x for a in rep["audits"] for x in a["lampGlow"]))
    if lamp:
        L.append(f"Свечение у ламп ({len(lamp)}) — нормально, если лампа горит: " + "; ".join(lamp[:4]))
    for f in rep["findings"]:
        L.append(f"{f['sev']} [{f['rule']}] {f['msg']}\n    → {f['hint']}")
    if not rep["findings"]:
        L.append("Формальных признаков не найдено — теперь посмотри скриншоты и листы глазами.")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--out", default="selfcheck")
    ap.add_argument("--state", action="append", help="параметры адреса без '?'; можно несколько; '' — по умолчанию")
    ap.add_argument("--size", action="append", help="например 1920x1080; можно несколько")
    a = ap.parse_args()
    rep = run(a.file, a.out, a.state, a.size)
    print(to_markdown(rep))
    sys.exit(1 if any(f["sev"] == SLOP for f in rep["findings"]) else 0)


if __name__ == "__main__":
    main()
