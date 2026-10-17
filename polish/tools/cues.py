#!/usr/bin/env python3
"""Оффлайн-рендер разовых звуков движка: громкость каждого, wav для автора.

  python polish/tools/cues.py button buttonUp [--repeat 4] [--gap 0.6] [--out polish/sound/P1-cues.wav]

Каждый звук звучит --repeat раз через --gap секунд (видно разброс повторов). Меряется пик и громкость
окна 100 мс (как в сведении шага 2 для коротких звуков) — по K-взвешиванию BS.1770, упрощённо.
"""
import argparse, base64, json, sys, wave
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]

JS = """async ([names, rep, gap]) => {
  const SR = 48000, dur = 0.4 + names.length * rep * gap;
  const ctx = new OfflineAudioContext(2, Math.ceil(SR * dur), SR);
  const eng = NightShiftAudio.create(ctx, { volume: { master: 0.8, station: 0, alarms: 1 }, seed: 20261015 });
  if (eng.setMode) eng.setMode('play');
  let t = 0.3; const marks = [];
  for (const nn of names) for (let i = 0; i < rep; i++) { const [n, m] = nn.split(':'); eng.cue(n, t, m ? { m } : {}); marks.push([nn, t]); t += gap; }   // имя:материал — для knock (П7)
  const buf = await ctx.startRendering();
  const L = buf.getChannelData(0), R = buf.getChannelData(1);
  const pcm = new Int16Array(L.length * 2);
  for (let i = 0; i < L.length; i++) { pcm[2 * i] = Math.max(-1, Math.min(1, L[i])) * 32767; pcm[2 * i + 1] = Math.max(-1, Math.min(1, R[i])) * 32767; }
  let s = ''; const u8 = new Uint8Array(pcm.buffer); for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return { sr: SR, b64: btoa(s), marks };
}"""


def kweight(x, sr):
    import numpy as np
    from scipy.signal import lfilter
    # BS.1770: полка +4 дБ выше ~1,5 кГц и срез ниже ~38 Гц
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621]
    return lfilter(b2, a2, lfilter(b1, a1, x))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("names", nargs="+")
    ap.add_argument("--repeat", type=int, default=4); ap.add_argument("--gap", type=float, default=0.6)
    ap.add_argument("--game", default=str(ROOT / "night-shift-4.html")); ap.add_argument("--out", default=str(ROOT / "polish" / "sound" / "cues.wav"))
    a = ap.parse_args()
    import numpy as np
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(); pg = br.new_page()
        pg.goto(Path(a.game).resolve().as_uri() + "?level=1&paused=1"); pg.wait_for_timeout(400)
        r = pg.evaluate(JS, [a.names, a.repeat, a.gap]); br.close()
    raw = base64.b64decode(r["b64"]); sr = r["sr"]
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(raw)
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float64).reshape(-1, 2) / 32767
    k = np.stack([kweight(x[:, 0], sr), kweight(x[:, 1], sr)], 1)
    res = {}
    for n, t in r["marks"]:
        i0 = int(t * sr); seg = k[i0:i0 + int(0.1 * sr)]; raw_seg = x[i0:i0 + int(a.gap * sr * 0.9)]
        lufs = -0.691 + 10 * np.log10(max(1e-12, (seg ** 2).mean(0).sum()))
        res.setdefault(n, []).append((lufs, 20 * np.log10(max(1e-9, np.abs(raw_seg).max()))))
    for n, v in res.items():
        l = [x[0] for x in v]; pk = [x[1] for x in v]
        print(f"{n:10} громкость 100 мс: {np.mean(l):6.1f} LUFS (разброс {max(l) - min(l):.1f} дБ) · пик {max(pk):6.1f} дБFS")
    print(f"wav: {out}")


if __name__ == "__main__":
    main()
