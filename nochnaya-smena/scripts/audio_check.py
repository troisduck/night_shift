#!/usr/bin/env python3
"""Самопроверка звука «Ночной смены»: оффлайн-рендер движка в Chromium и замеры.

Я не слышу — поэтому меряю. Страница игры должна отдавать
window.NightShiftAudio.create(ctx) по контракту из references/sound.md.

  python3 audio_check.py игра.html --out selfcheck [--scenario default|startup|путь.json]

Пишет в --out: audio_<сценарий>.wav (дать послушать автору), audio_<сценарий>_spectrogram.png,
audio_<сценарий>.json. Нужны playwright (chromium), numpy, scipy; matplotlib — для спектрограммы.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import math
import sys
from pathlib import Path

SLOP, CHECK = "✗", "?"
SR = 48000

BASE_VIEW = {
    "power": 1.0, "pumps": [1.0, 1.0, 1.0, 1.0], "turbine": 1.0, "steam": 1.0, "rods": 0,
    "heaters": 0.0, "spray": 0.0, "relief": 0.0, "diesels": [0.0, 0.0, 0.0],
    "vent": 1.0, "mains": 1.0, "alarms": [],
}


def _a(id_, level, acked=False):
    return {"id": id_, "level": level, "acked": acked}


def scenario_default():
    """Ровная работа → руки → стержни → отказ ГЦН → квитирование → сброс пара → АЗ → блэкаут → ДГ."""
    S, L = "step", "lerp"
    keys = [
        {"t": 9.0, "mode": S, "set": {"rods": -1, "power": 1.0}},
        {"t": 11.5, "mode": S, "set": {"rods": 0}},
        {"t": 11.5, "mode": L, "set": {"power": 0.92}},
        {"t": 12.0, "mode": S, "set": {"pumps.2": 1.0}},
        {"t": 20.0, "mode": L, "set": {"pumps.2": 0.0}},            # выбег ГЦН-3 на маховике
        {"t": 12.3, "mode": S, "set": {"alarms": [_a("gcn3", 2)]}},
        {"t": 15.5, "mode": S, "set": {"alarms": [_a("gcn3", 2, True)]}},
        {"t": 17.0, "mode": S, "set": {"heaters": 1.0}},
        {"t": 18.5, "mode": S, "set": {"heaters": 0.0}},
        {"t": 19.0, "mode": S, "set": {"relief": 0.0}},
        {"t": 19.4, "mode": L, "set": {"relief": 1.0}},
        {"t": 21.4, "mode": S, "set": {"relief": 1.0}},
        {"t": 22.2, "mode": L, "set": {"relief": 0.0}},
        {"t": 19.1, "mode": S, "set": {"alarms": [_a("gcn3", 2, True), _a("press", 2)]}},
        {"t": 22.6, "mode": S, "set": {"alarms": [_a("gcn3", 2, True), _a("press", 2, True)]}},
        {"t": 24.0, "mode": S, "set": {"alarms": []}},
        {"t": 25.0, "mode": S, "set": {"power": 0.92, "steam": 1.0, "turbine": 1.0, "alarms": [_a("az", 3)]}},
        {"t": 26.0, "mode": L, "set": {"steam": 0.0}},
        {"t": 26.5, "mode": L, "set": {"power": 0.07}},
        {"t": 37.0, "mode": L, "set": {"turbine": 0.0}},
        {"t": 28.0, "mode": S, "set": {"alarms": [_a("az", 3, True)]}},
        {"t": 30.0, "mode": S, "set": {"mains": 0.0, "vent": 1.0, "pumps.0": 1.0, "pumps.1": 1.0, "pumps.3": 1.0}},
        {"t": 30.1, "mode": S, "set": {"alarms": [_a("az", 3, True), _a("bo", 3)]}},
        {"t": 32.5, "mode": L, "set": {"vent": 0.0}},
        {"t": 38.0, "mode": L, "set": {"pumps.0": 0.0, "pumps.1": 0.0, "pumps.3": 0.0}},
        {"t": 33.5, "mode": S, "set": {"diesels.0": 0.0}},
        {"t": 40.0, "mode": L, "set": {"diesels.0": 1.0}},
        {"t": 34.2, "mode": S, "set": {"diesels.1": 0.0}},
        {"t": 40.5, "mode": L, "set": {"diesels.1": 1.0}},
        {"t": 36.0, "mode": S, "set": {"alarms": [_a("az", 3, True), _a("bo", 3, True)]}},
        {"t": 40.5, "mode": S, "set": {"vent": 0.0}},
        {"t": 41.5, "mode": L, "set": {"vent": 0.6}},                # вентиляция от ДГ
    ]
    cues = [
        {"t": 5.0, "name": "tumbler"}, {"t": 5.7, "name": "tumbler"}, {"t": 6.4, "name": "tumbler"},
        {"t": 6.9, "name": "button"}, {"t": 15.5, "name": "ack"}, {"t": 22.6, "name": "ack"},
        {"t": 25.0, "name": "scram"}, {"t": 28.0, "name": "ack"}, {"t": 33.5, "name": "diesel_start"},
        {"t": 36.0, "name": "ack"}, {"t": 42.8, "name": "mentor"},
    ]
    events = [
        {"t": 9.0, "label": "Стержни пошли вниз"}, {"t": 12.0, "label": "Отказ ГЦН-3"},
        {"t": 15.5, "label": "Квитирование"}, {"t": 19.0, "label": "Сброс пара"},
        {"t": 25.0, "label": "АЗ"}, {"t": 30.0, "label": "Блэкаут"}, {"t": 33.5, "label": "Пуск ДГ"},
    ]
    return {"name": "default", "duration": 48.0, "fps": 20, "base": copy.deepcopy(BASE_VIEW),
            "keys": keys, "cues": cues, "events": events,
            "steady": [[1.5, 4.9], [44.0, 47.8]],
            "alarm_windows": [[12.5, 15.4], [19.3, 22.5], [25.2, 27.9], [30.3, 35.9]],
            "repeat": ["tumbler"]}


def scenario_startup():
    """Пуск с минимального уровня: счёт нейтронов должен учащаться задолго до того, как сдвинется стрелка."""
    base = copy.deepcopy(BASE_VIEW)
    base.update({"power": 1e-7, "turbine": 0.0, "steam": 0.0})
    keys = [
        {"t": 2.0, "mode": "step", "set": {"rods": 1, "power": 1e-7}},
        {"t": 3.8, "mode": "step", "set": {"rods": 0}},
        {"t": 22.0, "mode": "log", "set": {"power": 3e-3}},
        {"t": 30.0, "mode": "log", "set": {"power": 0.08}},
    ]
    return {"name": "startup", "duration": 32.0, "fps": 20, "base": base, "keys": keys, "cues": [],
            "events": [{"t": 2.0, "label": "Стержни вверх"}], "steady": [[0.3, 1.9]],
            "alarm_windows": [], "repeat": [], "count_windows": [[4.5, 7.5], [18.0, 21.0]]}


SCENARIOS = {"default": scenario_default, "startup": scenario_startup}


def load_scenario(name_or_path):
    if name_or_path in SCENARIOS:
        return SCENARIOS[name_or_path]()
    sc = json.loads(Path(name_or_path).read_text(encoding="utf-8"))
    sc.setdefault("name", Path(name_or_path).stem)
    sc.setdefault("fps", 20)
    sc.setdefault("base", copy.deepcopy(BASE_VIEW))
    for k in ("keys", "cues", "events", "steady", "alarm_windows", "repeat"):
        sc.setdefault(k, [])
    return sc


# ---------------------------------------------------------------- развёртка сценария в кадры
def _get(d, path):
    for p in path.split("."):
        d = d[int(p)] if isinstance(d, list) else d[p]
    return d


def _set(d, path, v):
    parts = path.split(".")
    for p in parts[:-1]:
        d = d[int(p)] if isinstance(d, list) else d[p]
    k = parts[-1]
    if isinstance(d, list):
        d[int(k)] = v
    else:
        d[k] = v


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def expand(sc):
    """Ключи: {"t", "mode": step|lerp|log, "set": {путь: значение}}; mode описывает отрезок, который кончается на ключе."""
    tracks = {}
    for k in sorted(sc["keys"], key=lambda k: k["t"]):
        for path, v in k["set"].items():
            tracks.setdefault(path, []).append((float(k["t"]), v, k.get("mode", "lerp")))
    frames = []
    for i in range(int(round(sc["duration"] * sc["fps"])) + 1):
        t = i / sc["fps"]
        view = copy.deepcopy(sc["base"])
        for path, keys in tracks.items():
            prev, nxt = (0.0, _get(sc["base"], path), "step"), None
            for key in keys:
                if key[0] <= t:
                    prev = key
                else:
                    nxt = key
                    break
            v = prev[1]
            if nxt and nxt[2] in ("lerp", "log") and _num(prev[1]) and _num(nxt[1]) and nxt[0] > prev[0]:
                a = (t - prev[0]) / (nxt[0] - prev[0])
                if nxt[2] == "log" and prev[1] > 0 and nxt[1] > 0:
                    v = 10 ** (math.log10(prev[1]) + a * (math.log10(nxt[1]) - math.log10(prev[1])))
                else:
                    v = prev[1] + a * (nxt[1] - prev[1])
            _set(view, path, copy.deepcopy(v))
        frames.append({"t": round(t, 4), "view": view})
    return frames


# ---------------------------------------------------------------- рендер в Chromium
RENDER_JS = r"""
async ({frames, cues, duration, sr}) => {
  const A = window.NightShiftAudio;
  if (!A || typeof A.create !== 'function') return {error: 'no-engine'};
  const ctx = new OfflineAudioContext(2, Math.ceil(duration * sr), sr);
  let eng;
  try { eng = A.create(ctx, {seed: 1234}); } catch (e) { return {error: 'create: ' + e}; }
  const errors = [];
  const items = frames.map(f => ({t: f.t, k: 0, f})).concat(cues.map(c => ({t: c.t, k: 1, c})));
  items.sort((a, b) => a.t - b.t || a.k - b.k);
  for (const it of items) {
    try {
      if (it.k === 0) eng.update(it.f.view, it.t);
      else if (eng.cue(it.c.name, it.t, it.c.opts || {}) === false) errors.push('неизвестный разовый звук: ' + it.c.name);
    } catch (e) {
      errors.push((it.k === 0 ? 'update' : 'cue ' + it.c.name) + ' @' + it.t + ': ' + e);
      if (errors.length > 20) break;
    }
  }
  const buf = await ctx.startRendering();
  const enc = (ch) => {
    const f = buf.getChannelData(ch), i16 = new Int16Array(f.length);
    let peak = 0, clip = 0;
    for (let i = 0; i < f.length; i++) {
      const v = f[i], a = Math.abs(v);
      if (a > peak) peak = a;
      if (a >= 0.999) clip++;
      i16[i] = Math.max(-1, Math.min(1, v)) * 32767;
    }
    const u8 = new Uint8Array(i16.buffer);
    let s = '';
    for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    return {b64: btoa(s), peak, clip};
  };
  return {errors, n: buf.length, sr: buf.sampleRate, L: enc(0), R: enc(buf.numberOfChannels > 1 ? 1 : 0)};
}
"""


def render(game, sc, timeout_ms=120000):
    from playwright.sync_api import sync_playwright
    frames = expand(sc)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(timeout_ms)
        page_errors = []
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.goto(Path(game).resolve().as_uri() + "?audiotest=1")
        page.wait_for_timeout(300)
        res = page.evaluate(RENDER_JS, {"frames": frames, "cues": sc["cues"], "duration": sc["duration"], "sr": SR})
        browser.close()
    res["page_errors"] = page_errors
    return res


# ---------------------------------------------------------------- замеры
def kweight(x):
    from scipy.signal import lfilter
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]
    return lfilter(b2, a2, lfilter(b1, a1, x, axis=0), axis=0)


def loudness_series(x, sr, win=0.4, hop=0.1):
    import numpy as np
    p = (kweight(x) ** 2).sum(axis=1)
    w, h = int(win * sr), int(hop * sr)
    cs = np.concatenate([[0.0], np.cumsum(p, dtype=np.float64)])
    starts = np.arange(0, len(p) - w + 1, h)
    ms = (cs[starts + w] - cs[starts]) / w
    return (starts + w / 2) / sr, -0.691 + 10 * np.log10(ms + 1e-12), ms


def integrated(ms):
    import numpy as np
    lk = -0.691 + 10 * np.log10(ms + 1e-12)
    g = ms[lk > -70]
    if not len(g):
        return float("-inf")
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g2 = ms[(lk > -70) & (lk > rel)]
    return float(-0.691 + 10 * np.log10(g2.mean())) if len(g2) else float("-inf")


def lmean(lt, ms, a, b, keep=None):
    import numpy as np
    m = (lt >= a) & (lt < b)
    if keep is not None and (m & keep).sum() >= 3:
        m = m & keep
    return float(-0.691 + 10 * np.log10(ms[m].mean() + 1e-12)) if m.any() else None


def find_clicks(x, sr):
    """Разрыв = одиночная пара выбросов второй разности (ступенька) в гладком сигнале.
    Шумовые щелчки (тумблер, счёт нейтронов) и периодические фронты волны не в счёт."""
    import numpy as np
    from scipy.ndimage import median_filter
    blk, half = int(0.005 * sr), int(0.0013 * sr)
    hits = []
    for ch in range(x.shape[1]):
        s = x[:, ch].astype(np.float64)
        d2 = np.abs(s[2:] - 2 * s[1:-1] + s[:-2])
        nb = len(d2) // blk
        if nb < 20:
            continue
        D = d2[: nb * blk].reshape(nb, blk)
        mx = D.max(axis=1)
        neigh = median_filter(mx, size=19, mode="nearest")
        found = []
        for b in np.nonzero((mx > 0.01) & (mx > 6.0 * neigh + 1e-4))[0]:
            pos = b * blk + int(np.argmax(D[b]))
            w = d2[max(0, pos - half): pos + half + 1] ** 2       # окно вокруг выброса, а не блок
            if np.partition(w, -2)[-2:].sum() / (w.sum() + 1e-18) > 0.75:
                found.append(pos)
        found = np.array(found)
        for pos in found:
            if np.sum(np.abs(found - pos) <= int(0.05 * sr)) > 3:   # густо — форма волны, не щелчок
                continue
            hits.append(((pos + 1) / sr, float(d2[pos])))
    hits.sort()
    merged = []
    for t, m in hits:
        if merged and t - merged[-1][0] < 0.005:
            continue
        merged.append((round(t, 3), round(m, 4)))
    return merged


BANDS = [(20, 45), (45, 90), (90, 180), (180, 355), (355, 710), (710, 1400), (1400, 2800), (2800, 5600),
         (5600, 11200), (11200, 20000)]


def spectrum(mono, sr, nfft=4096, hop=1024):
    import numpy as np
    from scipy.signal import stft
    f, t, Z = stft(mono, fs=sr, window="hann", nperseg=nfft, noverlap=nfft - hop, boundary=None, padded=False)
    P = np.abs(Z).astype(np.float64) ** 2
    E = np.stack([P[(f >= lo) & (f < hi)].sum(axis=0) for lo, hi in BANDS])
    return f, t, P, E


def cue_mask(times, cues):
    """Кадры, не задетые разовыми звуками (−0,05…+0,6 с от каждого)."""
    import numpy as np
    keep = np.ones(len(times), dtype=bool)
    for c in cues:
        keep &= ~((times >= c["t"] - 0.05) & (times < c["t"] + 0.6))
    return keep


def wmean_db(tE, E, a, b, keep=None):
    import numpy as np
    m = (tE >= a) & (tE < b)
    if keep is not None and (m & keep).sum() >= 3:
        m = m & keep
    return 10 * np.log10(E[:, m].mean(axis=1) + 1e-14) if m.any() else None


def cue_repeat(mono, sr, times):
    """Сходство повторов одного звука за вычетом фона: 1 — одинаковы до сэмпла, около 0 — разные.
    Меряется в октаве, где звук сильнее всего над фоном; если фон громче звука — None (не измерить)."""
    import numpy as np
    from scipy.signal import butter, sosfiltfilt
    L, gap, lag = int(0.06 * sr), int(0.01 * sr), int(0.0015 * sr)
    i0 = int(times[0] * sr)
    if i0 - L - gap < 0:
        return None
    fr = np.fft.rfftfreq(8192, 1 / sr)
    psd = lambda seg: np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 8192)) ** 2
    pc, pb = psd(mono[i0:i0 + L]), psd(mono[i0 - L - gap:i0 - gap])
    band, snr = None, 1.0
    for lo in (125, 250, 500, 1000, 2000, 4000, 8000):
        m = (fr >= lo) & (fr < 2 * lo)
        b = pb[m].sum() + 1e-18
        if (pc[m].sum() - b) / b > snr:
            band, snr = (lo, 2 * lo), (pc[m].sum() - b) / b
    if band is None:
        return None
    y = sosfiltfilt(butter(4, band, btype="bandpass", fs=sr, output="sos"), mono)
    sims = []
    for i in range(len(times)):
        for j in range(i + 1, len(times)):
            ia, ib = int(times[i] * sr), int(times[j] * sr)
            if min(ia, ib) - L - gap - lag < 0 or max(ia, ib) + L + lag > len(y):
                continue
            sa, ba = y[ia:ia + L], y[ia - L - gap:ia - gap]
            ea = float(np.mean(sa ** 2) - np.mean(ba ** 2))
            if ea <= 0:
                continue
            k = max(range(-lag, lag + 1), key=lambda k: float(np.dot(sa, y[ib + k:ib + k + L])))
            sb, bb = y[ib + k:ib + k + L], y[ib + k - L - gap:ib + k - gap]
            sims.append((float(np.mean(sa * sb)) - float(np.mean(ba * bb))) / ea)
    return max(sims) if sims else None


def count_rate(mono, sr, a, b):
    import numpy as np
    from scipy.signal import butter, find_peaks, sosfiltfilt
    seg = mono[int(a * sr):int(b * sr)]
    y = np.abs(sosfiltfilt(butter(4, [1800, 3000], btype="bandpass", fs=sr, output="sos"), seg))
    w = max(1, int(0.001 * sr))
    env = np.convolve(y, np.ones(w) / w, mode="same")
    pk, _ = find_peaks(env, height=max(6 * np.median(env), 0.002), distance=int(0.002 * sr))
    return len(pk) / (b - a)


def plot(path, f, tE, P, lt, lk, sc, clicks):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    sel = np.unique(np.clip(np.searchsorted(f, np.geomspace(30, 16000, 420)), 1, len(f) - 1))
    S = 10 * np.log10(P[sel] + 1e-14)
    vmax = float(np.percentile(S, 99.7))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(18, 9), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    a1.pcolormesh(tE, f[sel], S, shading="auto", cmap="magma", vmin=vmax - 80, vmax=vmax)
    a1.set_yscale("log")
    a1.set_ylim(30, 16000)
    a1.set_ylabel("Гц")
    a1.set_title(f"«{sc['name']}»: спектрограмма. Белые линии — события, голубые метки — разовые звуки, красные — щелчки")
    for ev in sc["events"]:
        a1.axvline(ev["t"], color="white", lw=0.9, alpha=0.85)
        a1.text(ev["t"] + 0.12, 13000, ev["label"], color="white", fontsize=9, rotation=90, va="top")
    for c in sc["cues"]:
        a1.plot([c["t"]], [36], marker="^", color="#7fd3ff", ms=7)
    good = lk[np.isfinite(lk)]
    a2.plot(lt, lk, color="#222", lw=1)
    for a, b in sc["steady"]:
        a2.axvspan(a, b, color="#2E9E47", alpha=0.2)
    for a, b in sc.get("alarm_windows", []):
        a2.axvspan(a, b, color="#D7301F", alpha=0.13)
    for t, _ in clicks:
        a1.axvline(t, color="red", lw=1.3)
        a2.axvline(t, color="red", lw=1.3)
    a2.set_ylim(max(-70.0, float(good.min()) - 3) if len(good) else -70, float(good.max()) + 3 if len(good) else 0)
    a2.set_ylabel("LUFS, 400 мс")
    a2.set_xlabel("с  (зелёное — устойчивая работа, красное — тревога звучит)")
    a2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def analyze(x, sr, sc, peak, clip):
    import numpy as np
    from scipy.signal import butter, sosfiltfilt
    mono = x.mean(axis=1)
    rep = {"peak_dbfs": round(20 * math.log10(max(peak, 1e-9)), 2), "clip_samples": int(clip),
           "dc": [round(float(x[:, c].mean()), 5) for c in range(x.shape[1])]}
    lt, lk, ms = loudness_series(x, sr)
    rep["loudness_lufs"] = round(integrated(ms), 1)
    rep["clicks"] = find_clicks(x, sr)
    f, tE, P, E = spectrum(mono, sr)
    floor = 10 * math.log10(float(E.max()) + 1e-14) - 75
    keepE, keepL = cue_mask(tE, sc["cues"]), cue_mask(lt, sc["cues"])
    rep["events"] = []
    for ev in sc["events"]:
        t = ev["t"]
        pre, post = wmean_db(tE, E, t - 2.0, t - 0.2, keepE), wmean_db(tE, E, t + 0.4, t + 2.4, keepE)
        lp, lq = lmean(lt, ms, t - 2.0, t - 0.2, keepL), lmean(lt, ms, t + 0.4, t + 2.4, keepL)
        if pre is None or post is None or lp is None or lq is None:
            continue
        valid = np.maximum(pre, post) > floor
        diff = (post - pre)[valid]
        dist = float(np.sqrt(np.mean(diff ** 2))) if len(diff) else 0.0
        rep["events"].append({"t": t, "label": ev["label"], "spectral_db": round(dist, 1),
                              "loud_lu": round(lq - lp, 1), "ok": bool(dist >= 2.0 or abs(lq - lp) >= 1.5)})
    rep["steady"] = []
    for a, b in sc["steady"]:
        m = (lt >= a) & (lt < b)
        mp = (tE >= a) & (tE < b)
        if m.sum() < 4 or not mp.any():
            continue
        pt = P[:, mp].sum(axis=1)
        tot = float(pt.sum()) + 1e-14
        rep["steady"].append({"from": a, "to": b, "level_lufs": round(lmean(lt, ms, a, b), 1),
                              "life_lu": round(float(np.std(lk[m])), 2),
                              "harsh_2_5k": round(float(pt[(f >= 2000) & (f < 5000)].sum()) / tot, 3),
                              "sub_40": round(float(pt[f < 40].sum()) / tot, 3)})
    rep["alarm_over_steady_lu"] = None
    if sc.get("alarm_windows") and rep["steady"]:
        base = rep["steady"][0]["level_lufs"]
        overs = [lmean(lt, ms, a, b) for a, b in sc["alarm_windows"]]
        overs = [o - base for o in overs if o is not None]
        if overs:
            rep["alarm_over_steady_lu"] = round(min(overs), 1)
    rep["repeats"] = []
    if sc.get("repeat"):
        for name in sc["repeat"]:
            times = [c["t"] for c in sc["cues"] if c["name"] == name]
            if len(times) >= 2:
                sim = cue_repeat(mono, sr, times)
                rep["repeats"].append({"cue": name, "similarity": None if sim is None else round(float(sim), 3)})
    rep["count"] = None
    if sc.get("count_windows"):
        (a1, b1), (a2, b2) = sc["count_windows"][:2]
        early, late = count_rate(mono, sr, a1, b1), count_rate(mono, sr, a2, b2)
        rep["count"] = {"early_per_s": round(early, 1), "late_per_s": round(late, 1),
                        "ratio": round(late / early, 1) if early > 0 else None}
    return rep, (f, tE, P, lt, lk)


def findings_from(rep, sc):
    F = []

    def add(sev, rule, msg, hint):
        F.append({"sev": sev, "rule": rule, "msg": msg, "hint": hint})

    tag = f"[{sc['name']}] "
    if rep.get("errors"):
        add(SLOP, "A-errors", tag + "Ошибки движка при рендере: " + "; ".join(rep["errors"][:3]),
            "Исправить — в игре звук сломается так же.")
    if rep["clip_samples"] > 0 or rep["peak_dbfs"] > -0.3:
        add(SLOP, "A-clip", tag + f"Перегруз: пик {rep['peak_dbfs']} дБFS, клиппинг {rep['clip_samples']} отсч.",
            "Снизить уровни слоёв и шин; лимитер на мастере.")
    elif rep["peak_dbfs"] > -1.0:
        add(CHECK, "A-peak", tag + f"Пик {rep['peak_dbfs']} дБFS — почти без запаса.", "Оставить запас ≥ 1 дБ.")
    if rep["clicks"]:
        ts = ", ".join(f"{t:.2f} с" for t, _ in rep["clicks"][:6])
        add(SLOP, "A-clicks", tag + f"Щелчки-разрывы: {len(rep['clicks'])} (первые: {ts}).",
            "Найди, что стартует/останавливается или скачет в это время; дай рампу 2–10 мс.")
    if max(abs(d) for d in rep["dc"]) > 0.005:
        add(CHECK, "A-dc", tag + f"Постоянная составляющая {rep['dc']}.", "Срез ниже 20 Гц на мастере, шумы без смещения.")
    for ev in rep["events"]:
        if not ev["ok"]:
            add(SLOP, "A-react", tag + f"Событие «{ev['label']}» почти не слышно: спектр {ev['spectral_db']} дБ, "
                                       f"громкость {ev['loud_lu']:+} LU.",
                "Привяжи слой к полю аудио-вида или усиль реакцию: каждое событие должно быть слышно.")
    for st in rep["steady"]:
        if st["life_lu"] < 0.12:
            add(CHECK, "A-dead", tag + f"{st['from']}–{st['to']} с: громкость стоит как вкопанная "
                                       f"(σ {st['life_lu']} LU) — мёртвый гул.",
                "Медленная жизнь: биения, случайное блуждание ±1–2 дБ, связь с мелкими колебаниями модели.")
        if st["harsh_2_5k"] > 0.25:
            add(CHECK, "A-harsh", tag + f"{st['from']}–{st['to']} с: {st['harsh_2_5k'] * 100:.0f} % энергии в 2–5 кГц — утомляет.",
                "Долгие слои ниже ~1,5 кГц; 2–5 кГц — только коротко.")
        if st["sub_40"] > 0.35:
            add(CHECK, "A-sub", tag + f"{st['from']}–{st['to']} с: {st['sub_40'] * 100:.0f} % энергии ниже 40 Гц.",
                "Ноутбук этого не воспроизведёт, а лимитер начнёт качать — поднять гулы выше 40 Гц.")
    lu = rep["loudness_lufs"]
    if lu < -40:
        add(CHECK, "A-quiet", tag + f"Общая громкость {lu} LUFS — почти ничего не слышно.", "Ориентир в покое −28…−20 LUFS.")
    elif lu > -16:
        add(CHECK, "A-loud", tag + f"Общая громкость {lu} LUFS — слишком громко.", "Ориентир в покое −28…−20 LUFS.")
    if rep["alarm_over_steady_lu"] is not None and rep["alarm_over_steady_lu"] < 4:
        add(CHECK, "A-alarm-masked", tag + f"Тревога всего на {rep['alarm_over_steady_lu']} LU громче покоя.",
            "Тревога поверх всего: ≥ 6 LU над покоем, приглушение машин под тревогу.")
    for r in rep["repeats"]:
        if r["similarity"] is not None and r["similarity"] > 0.9:
            add(CHECK, "A-repeat", tag + f"«{r['cue']}» повторяется одинаково до сэмпла (сходство {r['similarity']}).",
                "Разброс высоты ±3–5 %, громкости ±1–1,5 дБ, тайминга ±2 мс.")
    c = rep.get("count")
    if c and (c["ratio"] is None or c["ratio"] < 2):
        add(CHECK, "A-count", tag + f"Счёт нейтронов почти не учащается при разгоне ({c['early_per_s']} → {c['late_per_s']} в с).",
            "Частота щелчков — логарифм мощности (sound.md, «Счёт нейтронов»).")
    return F


def run(game, out, scenario="default"):
    import numpy as np
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sc = load_scenario(scenario)
    res = render(game, sc)
    if res.get("error") == "no-engine":
        return {"scenario": sc["name"], "skipped": True,
                "findings": [{"sev": CHECK, "rule": "A-none",
                              "msg": "На странице нет window.NightShiftAudio — оффлайн-проверка звука невозможна.",
                              "hint": "Подключи движок по контракту (assets/audio-engine-skeleton.js, sound.md)."}]}
    if res.get("error"):
        return {"scenario": sc["name"], "skipped": True,
                "findings": [{"sev": SLOP, "rule": "A-errors", "msg": "Движок не создаётся: " + res["error"],
                              "hint": "Исправить create(ctx)."}]}
    n = res["n"]
    ch = [np.frombuffer(base64.b64decode(res[k]["b64"]), dtype="<i2").astype(np.float32)[:n] / 32767.0 for k in ("L", "R")]
    x = np.stack(ch, axis=1)
    peak = max(res["L"]["peak"], res["R"]["peak"])
    clip = res["L"]["clip"] + res["R"]["clip"]
    rep, (f, tE, P, lt, lk) = analyze(x, res["sr"], sc, peak, clip)
    rep["errors"] = res.get("errors", []) + res.get("page_errors", [])
    rep["scenario"], rep["duration"] = sc["name"], sc["duration"]
    stem = f"audio_{sc['name']}"
    from scipy.io import wavfile
    wavfile.write(out / f"{stem}.wav", res["sr"], (np.clip(x, -1, 1) * 32767).astype(np.int16))
    rep["wav"] = str(out / f"{stem}.wav")
    try:
        plot(out / f"{stem}_spectrogram.png", f, tE, P, lt, lk, sc, rep["clicks"])
        rep["spectrogram"] = str(out / f"{stem}_spectrogram.png")
    except ImportError:
        rep["spectrogram"] = None
    rep["findings"] = findings_from(rep, sc)
    (out / f"{stem}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def to_markdown(rep) -> str:
    sc = rep.get("scenario", "?")
    if rep.get("skipped"):
        f = rep["findings"][0]
        return f"### Звук, сценарий «{sc}»\n{f['sev']} {f['msg']}\n    → {f['hint']}"
    L = [f"### Звук, сценарий «{sc}» ({rep['duration']:g} с)",
         f"Пик {rep['peak_dbfs']} дБFS · клиппинг {rep['clip_samples']} · щелчков {len(rep['clicks'])} · "
         f"громкость {rep['loudness_lufs']} LUFS"
         + (f" · тревога над покоем {rep['alarm_over_steady_lu']:+} LU" if rep['alarm_over_steady_lu'] is not None else "")]
    if rep["events"]:
        L.append("События (изменение спектра / громкости):")
        for e in rep["events"]:
            L.append(f"  {'ок' if e['ok'] else '✗ не слышно'} — {e['t']:g} с «{e['label']}»: {e['spectral_db']} дБ / {e['loud_lu']:+} LU")
    for s in rep["steady"]:
        L.append(f"Устойчиво {s['from']}–{s['to']} с: {s['level_lufs']} LUFS, жизнь σ {s['life_lu']} LU, "
                 f"2–5 кГц {s['harsh_2_5k'] * 100:.0f} %, ниже 40 Гц {s['sub_40'] * 100:.0f} %")
    for r in rep["repeats"]:
        L.append(f"Повторы «{r['cue']}»: " + ("не измерить — фон громче звука" if r["similarity"] is None
                 else f"сходство {r['similarity']} (1 — одинаковы до сэмпла)"))
    if rep.get("count"):
        c = rep["count"]
        L.append(f"Счёт нейтронов: {c['early_per_s']} → {c['late_per_s']} щелчков в с (×{c['ratio']})")
    for f in rep["findings"]:
        L.append(f"{f['sev']} [{f['rule']}] {f['msg']}\n    → {f['hint']}")
    if rep.get("spectrogram"):
        L.append(f"Посмотреть: {rep['spectrogram']} · Дать послушать автору: {rep['wav']}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--out", default="selfcheck")
    ap.add_argument("--scenario", default="default", help="default, startup или путь к JSON (через запятую — несколько)")
    a = ap.parse_args()
    bad = False
    for name in a.scenario.split(","):
        rep = run(a.file, a.out, name.strip())
        print(to_markdown(rep), end="\n\n")
        bad |= any(f["sev"] == SLOP for f in rep["findings"])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
