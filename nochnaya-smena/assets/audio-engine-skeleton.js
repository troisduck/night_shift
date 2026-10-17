/* ==NS-AUDIO== «Ночная смена» — звуковой движок, скелет v1.
 *
 * Контракт (по нему работают и игра, и самопроверка scripts/audio_check.py):
 *   const eng = NightShiftAudio.create(ctx, { seed, volume })
 *       ctx — AudioContext в игре или OfflineAudioContext в самопроверке.
 *   eng.update(view, when)   непрерывные слои плавно идут к «аудио-виду» к моменту when (с, часы ctx)
 *   eng.cue(name, when, o)   разовый звук; вернёт false, если имя неизвестно
 *   eng.setVolume(0..1)  eng.setMuted(bool)  eng.dispose()
 * Всё планируется по часам ctx, поэтому один и тот же код звучит в игре
 * и рендерится оффлайн для проверки.
 *
 * Аудио-вид — только то, что слышно:
 *   power      0..1.1   тепловая мощность, доля номинала (на пуске до 1e-7)
 *   pumps      [0..1]×4 обороты ГЦН
 *   turbine    0..1     обороты турбины (1 = синхронно с сетью)
 *   steam      0..1     расход пара на турбину
 *   rods       -1|0|1   стержни едут вниз / стоят / вверх
 *   heaters    0..1     ТЭНы компенсатора давления;  spray 0..1 — впрыск в КД
 *   relief     0..1     открытие сброса пара (предохранительный клапан, БРУ-А)
 *   diesels    [0..1]×3 обороты ДГ
 *   vent       0..1     вентиляция БЩУ;  mains 0..1 — питание собственных нужд
 *   countAudio true|false|undefined  динамик счёта нейтронов (по умолчанию сам на малой мощности)
 *   alarms     [{ id, level: 1|2|3, acked }]
 *
 * Разовые звуки: tumbler, button, cover, key, relay, ack, mentor, scram, phone, diesel_start.
 *
 * В игре:  const snd = NightShiftAudio.live();      // AudioContext появится по первому жесту
 *          в цикле отрисовки: snd.update(audioView(state));
 *          на действиях:      snd.cue('tumbler');
 *          выключатель звука: snd.setMuted(true);    пауза игры: snd.pause(true)
 */
(function (root) {
  'use strict';

  // Детерминированный генератор: оффлайн-проверка повторяема, а разброс всё равно есть.
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function clamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
  function c01(x) { return clamp(Number.isFinite(x) ? x : 0, 0, 1); }
  function fromDb(d) { return Math.pow(10, d / 20); }

  function create(ctx, opts) {
    opts = opts || {};
    const R = mulberry32(opts.seed || 20261005);
    const vary = function (x, pct) { return x * (1 + (R() * 2 - 1) * pct); };
    const T0 = ctx.currentTime;
    const SR = ctx.sampleRate;
    const sources = [];
    let volume = opts.volume == null ? 0.8 : c01(opts.volume);
    let muted = false;

    // ---------- параметры: автоматизация уходит только при заметном изменении
    const lastVal = new WeakMap();
    function init(param, v) { param.setValueAtTime(v, T0); lastVal.set(param, v); }
    function glide(param, v, when, tc) {
      const p = lastVal.get(param);
      if (p !== undefined && Math.abs(p - v) <= 1e-4 * Math.max(1, Math.abs(v))) return;
      lastVal.set(param, v);
      param.setTargetAtTime(v, when, tc);
    }
    function gain(v, dest) { const g = ctx.createGain(); init(g.gain, v); if (dest) g.connect(dest); return g; }
    function filt(type, f, q, dest) {
      const b = ctx.createBiquadFilter(); b.type = type; init(b.frequency, f); init(b.Q, q);
      if (dest) b.connect(dest);
      return b;
    }
    function osc(type, f, dest) {
      const o = ctx.createOscillator(); o.type = type; init(o.frequency, f);
      if (dest) o.connect(dest);
      o.start(T0); sources.push(o);
      return o;
    }
    function panner(x, dest) { const p = ctx.createStereoPanner(); init(p.pan, x); p.connect(dest); return p; }

    // ---------- шумовые буферы создаются один раз; шов петли сшит кроссфейдом, чтобы не щёлкал
    function noise(seconds, color) {
      const n = Math.floor(SR * seconds), x = Math.floor(SR * 0.05);
      const raw = new Float32Array(n + x);
      let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0, br = 0, mean = 0;
      for (let i = 0; i < n + x; i++) {
        const w = R() * 2 - 1;
        let v;
        if (color === 'brown') { br = (br + 0.02 * w) / 1.02; v = br * 3.5; }
        else if (color === 'pink') {            // фильтр Пола Келлета
          b0 = 0.99886 * b0 + w * 0.0555179; b1 = 0.99332 * b1 + w * 0.0750759;
          b2 = 0.969 * b2 + w * 0.153852;    b3 = 0.8665 * b3 + w * 0.3104856;
          b4 = 0.55 * b4 + w * 0.5329522;    b5 = -0.7616 * b5 - w * 0.016898;
          v = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11; b6 = w * 0.115926;
        } else v = w;
        raw[i] = v; mean += v;
      }
      mean /= (n + x);
      const buf = ctx.createBuffer(1, n, SR), d = buf.getChannelData(0);
      for (let i = 0; i < n; i++) d[i] = raw[i] - mean;
      for (let i = 0; i < x; i++) { const k = i / x; d[i] = (raw[i] - mean) * k + (raw[n + i] - mean) * (1 - k); }
      return buf;
    }
    function loop(buf, dest, offset) {
      const s = ctx.createBufferSource(); s.buffer = buf; s.loop = true;
      s.connect(dest); s.start(T0, offset || 0); sources.push(s);
      return s;
    }

    // ---------- мастер: громкость → срез ниже 20 Гц → лимитер → выход
    const out = gain(volume);
    const lowCut = filt('highpass', 20, 0.7);
    const limiter = ctx.createDynamicsCompressor();
    init(limiter.threshold, -10); init(limiter.knee, 4); init(limiter.ratio, 12);
    init(limiter.attack, 0.003); init(limiter.release, 0.25);
    out.connect(lowCut); lowCut.connect(limiter); limiter.connect(ctx.destination);

    // ---------- шины: машины «за стеной», помещение БЩУ, руки и события, сигнализация
    const MIX = { machines: 0.35, room: 0.45 };       // покой тихий: тревога должна быть сильно громче
    const machines = gain(MIX.machines, out);
    const wall = filt('lowpass', 1200, 0.5, machines);
    const room = gain(MIX.room, out);
    const hands = gain(1, out);
    const alarmBus = gain(1, out);

    const brown = noise(7.3, 'brown'), pink = noise(5.9, 'pink'), white = noise(1.3, 'white');

    // ---------- помещение: вентиляция (медленно «живёт») и сетевой гул 100 Гц (сеть 50 Гц)
    const ventG = gain(0, room); loop(brown, filt('lowpass', 480, 0.5, filt('highpass', 45, 0.7, ventG)), 0);
    const grilleG = gain(0, room); loop(pink, filt('bandpass', 1500, 0.8, grilleG), 1.7);
    const humG = gain(0, room);
    [[100, 1], [200, 0.45], [300, 0.2]].forEach(function (h) { osc('sine', h[0], gain(h[1], humG)); });

    // ---------- ГЦН ×4: лопастной тон × обороты + шум потока; у каждого своя частота → живые биения
    const pumps = [0, 1, 2, 3].map(function (i) {
      const pan = panner(-0.55 + 0.37 * i, wall);
      const tone = gain(0, pan), flow = gain(0, pan);
      const f0 = 97 + 1.3 * i;
      const o1 = osc('triangle', f0, gain(0.6, tone));
      const o2 = osc('sine', 2 * f0, gain(0.25, tone));
      loop(pink, filt('bandpass', 360 + 30 * i, 0.9, flow), 0.9 * i);
      return { f0: f0, o1: o1, o2: o2, tone: tone, flow: flow };
    });

    // ---------- турбина: синхронна с сетью — высота постоянна, нагрузку слышно по плотности пара
    const turb = (function () {
      const pan = panner(0.45, wall);
      const rum = gain(0, pan), whine = gain(0, pan), roar = gain(0, pan);
      const oR = osc('sine', 50, rum), oW = osc('sine', 1250, whine);
      loop(pink, filt('bandpass', 650, 0.5, roar), 2.3);
      return { oR: oR, oW: oW, rum: rum, whine: whine, roar: roar };
    })();

    // ---------- компенсатор давления, сброс пара
    const heatG = gain(0, room);
    osc('sine', 100, gain(0.6, heatG));
    loop(white, filt('bandpass', 3200, 2.5, gain(0.15, heatG)), 0.2);  // сухое потрескивание контакторов
    const sprayG = gain(0, wall); loop(white, filt('bandpass', 2600, 0.8, sprayG), 0.4);
    const reliefG = gain(0, room); loop(white, filt('bandpass', 1500, 0.6, filt('lowpass', 3200, 0.5, reliefG)), 0.8);
    const reliefLow = gain(0, room); loop(brown, filt('lowpass', 160, 0.7, filt('highpass', 40, 0.7, reliefLow)), 3.1);

    // ---------- ДГ ×3: тарахтение с частотой вспышек
    const diesels = [0, 1, 2].map(function (i) {
      const outG = gain(0, panner(-0.3 + 0.3 * i, wall));
      const am = gain(0.55, outG);
      loop(brown, filt('lowpass', 260 + 20 * i, 0.8, filt('highpass', 40, 0.7, am)), 1.1 * i);
      const fire = osc('sine', 1, null);
      const depth = gain(0.45, null); fire.connect(depth); depth.connect(am.gain);
      const tone = osc('triangle', 1, gain(0.18, outG));
      return { outG: outG, fire: fire, tone: tone, f: 41 + 0.8 * i };
    });

    // ---------- счёт нейтронов: щелчки, частота растёт с мощностью по логарифму
    const countBus = gain(0, room);
    const countFilt = filt('bandpass', 2300, 1.1, countBus);
    const clickBuf = (function () {
      const n = Math.floor(SR * 0.006), b = ctx.createBuffer(1, n, SR), d = b.getChannelData(0);
      for (let i = 0; i < n; i++) {
        const env = Math.min(1, i / (SR * 0.0003)) * Math.exp(-i / (SR * 0.0009));
        d[i] = (R() * 2 - 1) * env;
      }
      return b;
    })();
    let nextClick = T0;
    function countRate(p) {
      const lp = Math.log10(Math.max(p, 1e-7));
      return clamp(2 * Math.pow(150, (lp + 7) / 6), 1, 320);
    }
    function scheduleClicks(v, when) {
      const p = Number.isFinite(v.power) ? Math.max(0, v.power) : 0;
      const auto = clamp((Math.log10(0.05) - Math.log10(Math.max(p, 1e-9))) / (Math.log10(0.05) - Math.log10(0.01)), 0, 1);
      const lvl = v.countAudio === true ? 1 : v.countAudio === false ? 0 : auto;
      glide(countBus.gain, 0.5 * lvl, when, 0.3);
      if (lvl <= 0.001) { nextClick = when; return; }
      const rate = countRate(p), g = 1 / Math.sqrt(Math.max(1, rate / 30));   // плотный счёт не должен орать
      if (nextClick < when - 0.25) nextClick = when;                           // вкладка спала — не догоняем
      while (nextClick < when + 0.12) {
        const s = ctx.createBufferSource(); s.buffer = clickBuf;
        s.playbackRate.setValueAtTime(vary(1, 0.08), nextClick);
        const cg = ctx.createGain(); cg.gain.setValueAtTime(g * vary(0.85, 0.15), nextClick);
        s.connect(cg); cg.connect(countFilt); s.start(nextClick);
        nextClick += -Math.log(1 - R()) / rate;
      }
    }

    // ---------- разовые звуки: короткие фильтрованные всплески и удары, каждый раз чуть другие
    function burst(t, f, q, dur, level, dest) {
      const s = ctx.createBufferSource(); s.buffer = white;
      const bp = ctx.createBiquadFilter(); bp.type = 'bandpass';
      bp.frequency.setValueAtTime(vary(f, 0.05), t); bp.Q.setValueAtTime(q, t);
      const g = ctx.createGain(); g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(vary(level, 0.12), t + 0.0015);
      g.gain.setTargetAtTime(0, t + 0.0015, dur / 4);
      s.connect(bp); bp.connect(g); g.connect(dest);
      s.start(t, R() * 1.0, dur + 0.05);
    }
    function thump(t, f, dur, level, dest) {
      const o = ctx.createOscillator(); const f1 = vary(f, 0.04);
      o.frequency.setValueAtTime(f1, t); o.frequency.exponentialRampToValueAtTime(f1 * 0.6, t + dur);
      const g = ctx.createGain(); g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(vary(level, 0.12), t + 0.002);
      g.gain.setTargetAtTime(0, t + 0.002, dur / 4);
      o.connect(g); g.connect(dest); o.start(t); o.stop(t + dur * 2 + 0.05);
    }
    function hiss(t, dur, level, dest) {
      const s = ctx.createBufferSource(); s.buffer = white;
      const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.setValueAtTime(2800, t);
      const g = ctx.createGain(); g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(level, t + 0.01); g.gain.setTargetAtTime(0, t + dur * 0.6, dur / 5);
      s.connect(lp); lp.connect(g); g.connect(dest); s.start(t, R() * 0.8, dur + 0.3);
    }
    function air(t) {                                   // пуск ДГ сжатым воздухом
      const s = ctx.createBufferSource(); s.buffer = white;
      const bp = ctx.createBiquadFilter(); bp.type = 'bandpass';
      bp.frequency.setValueAtTime(900, t); bp.frequency.exponentialRampToValueAtTime(500, t + 0.4); bp.Q.setValueAtTime(0.7, t);
      const g = ctx.createGain(); g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.35, t + 0.01); g.gain.setTargetAtTime(0, t + 0.12, 0.09);
      s.connect(bp); bp.connect(g); g.connect(wall); s.start(t, R() * 0.2, 1.05);
      thump(t, 68, 0.12, 0.25, wall);
    }
    function bell(t, rings) {                           // механический звонок телефона диспетчера
      for (let r = 0; r < rings; r++) {
        const t0 = t + r * 3.0, dur = 1.0;
        const g = ctx.createGain(); g.gain.setValueAtTime(0, t0);
        g.gain.linearRampToValueAtTime(0.16, t0 + 0.01); g.gain.setValueAtTime(0.16, t0 + dur);
        g.gain.linearRampToValueAtTime(0, t0 + dur + 0.04);
        const am = ctx.createGain(); am.gain.setValueAtTime(0.5, t0);
        const lfo = ctx.createOscillator(); lfo.frequency.setValueAtTime(24, t0);   // молоточек ~24 удара в секунду
        const depth = ctx.createGain(); depth.gain.setValueAtTime(0.5, t0);
        lfo.connect(depth); depth.connect(am.gain);
        const bp = ctx.createBiquadFilter(); bp.type = 'bandpass';
        bp.frequency.setValueAtTime(1900, t0); bp.Q.setValueAtTime(0.8, t0);
        [1180, 1695, 2910].forEach(function (f, k) {
          const o = ctx.createOscillator(); o.frequency.setValueAtTime(vary(f, 0.004), t0);
          const og = ctx.createGain(); og.gain.setValueAtTime([1, 0.6, 0.3][k], t0);
          o.connect(og); og.connect(am); o.start(t0); o.stop(t0 + dur + 0.1);
        });
        am.connect(bp); bp.connect(g); g.connect(hands);
        lfo.start(t0); lfo.stop(t0 + dur + 0.1);
      }
    }
    function scram(t) {
      for (let k = 0; k < 8; k++) CUES.relay(t + k * vary(0.03, 0.3));          // сыплются реле защиты
      for (let k = 0; k < 61; k++) burst(t + 0.08 + Math.pow(R(), 1.6) * 0.5, vary(2000, 0.3), 2.5, 0.01, 0.07, hands);
      for (let k = 0; k < 61; k++) thump(t + 1.6 + R() * 1.6, vary(105, 0.2), 0.08, 0.06, wall);  // посадка стержней
      thump(t + 0.05, 70, 0.4, 0.35, hands);
    }

    const CUES = {
      tumbler: function (t) {
        burst(t, 3200, 2.0, 0.008, 0.42, hands); thump(t + 0.001, 185, 0.03, 0.3, hands);
        burst(t + vary(0.019, 0.1), 1900, 1.6, 0.01, 0.2, hands);
      },
      button: function (t) { thump(t, 140, 0.04, 0.34, hands); burst(t, 1400, 1.4, 0.01, 0.22, hands); },
      relay: function (t) { burst(t, 2400, 3.0, 0.006, 0.3, hands); thump(t, 230, 0.018, 0.2, hands); },
      ack: function (t) { CUES.button(t); CUES.relay(t + 0.03); },
      cover: function (t) {
        for (let k = 0; k < 3; k++) burst(t + k * 0.04, vary(2700, 0.1), 5, 0.02, 0.08, hands);
        burst(t + 0.16, 2100, 2, 0.01, 0.3, hands); thump(t + 0.16, 110, 0.06, 0.32, hands);
      },
      key: function (t) { burst(t, 4300, 7, 0.03, 0.14, hands); burst(t + 0.09, 3900, 7, 0.035, 0.16, hands); CUES.relay(t + 0.18); },
      mentor: function (t) { thump(t, 92, 0.03, 0.18, hands); hiss(t + 0.01, 0.14, 0.035, hands); },  // щелчок селектора, не писк
      scram: function (t) { scram(t); },
      phone: function (t, o) { bell(t, (o && o.rings) || 2); },
      diesel_start: function (t) { air(t); }
    };

    // ---------- приводы стержней: шаговые щелчки, вверх чуть выше по тону, вниз чуть ниже
    let nextStep = T0;
    function scheduleRods(v, when) {
      const dir = v.rods > 0 ? 1 : v.rods < 0 ? -1 : 0;
      if (!dir) { nextStep = when; return; }
      if (nextStep < when - 0.25) nextStep = when;
      while (nextStep < when + 0.12) {
        burst(nextStep, dir > 0 ? 2100 : 1650, 2.2, 0.012, 0.32, hands);
        thump(nextStep + 0.002, dir > 0 ? 150 : 122, 0.045, 0.28, hands);
        nextStep += vary(1 / 3.4, 0.06);
      }
    }

    // ---------- переходы состояния звучат сами: контакторы, реле
    const prev = { heaters: false, spray: false, mains: true, pumps: [false, false, false, false], primed: false };
    function transitions(v, when) {
      const h = c01(v.heaters) > 0.5, s = c01(v.spray) > 0.5, m = (v.mains == null ? 1 : c01(v.mains)) > 0.5;
      const ps = Array.isArray(v.pumps) ? v.pumps : [];
      if (prev.primed) {
        if (h !== prev.heaters) CUES.relay(when);
        if (s !== prev.spray) CUES.relay(when + 0.01);
        if (m !== prev.mains) for (let k = 0; k < 6; k++) CUES.relay(when + k * vary(0.035, 0.4));
      }
      for (let i = 0; i < 4; i++) {
        const on = c01(ps[i]) > 0.05;
        if (prev.primed && on && !prev.pumps[i]) CUES.relay(when + 0.02 * i);
        prev.pumps[i] = on;
      }
      prev.heaters = h; prev.spray = s; prev.mains = m; prev.primed = true;
    }

    // ---------- сигнализация: звучит до квитирования; аварийная приглушает остальное
    const alarms = new Map();
    function alarmVoice(level, t) {
      const v = { level: level, out: gain(0, alarmBus), gate: null, oscs: [], next: t, stopped: false };
      if (level >= 3) {                                  // ревун: два близких тона с биением, через «рупор»
        const lp = filt('lowpass', 2600, 0.6, filt('bandpass', 700, 1.6, v.out));
        v.oscs.push(osc('sawtooth', 311, lp), osc('sawtooth', 317, lp));   // ns-ok: ревун тревоги, идёт через фильтры
        v.out.gain.setTargetAtTime(0.3, t, 0.02);
      } else if (level === 2) {                          // прерывистый зуммер
        v.gate = gain(0, v.out);
        const lp = filt('lowpass', 1800, 0.6, filt('bandpass', 900, 1.2, v.gate));
        v.oscs.push(osc('square', 196, lp));             // ns-ok: зуммер тревоги, идёт через фильтры
        v.out.gain.setTargetAtTime(0.3, t, 0.01);
      } else {                                           // предупредительная: «дзынь» раз в 2,4 с
        v.out.gain.setTargetAtTime(0.22, t, 0.01);
      }
      return v;
    }
    function alarmStop(v, t) {
      v.out.gain.cancelScheduledValues(t);
      v.out.gain.setTargetAtTime(0, t, 0.02);
      v.oscs.forEach(function (o) { o.stop(t + 0.4); });
      v.stopped = true;
    }
    function chime(t, dest) {
      [[880, 1], [2210, 0.35]].forEach(function (p) {
        const o = ctx.createOscillator(); o.frequency.setValueAtTime(vary(p[0], 0.003), t);
        const g = ctx.createGain(); g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.5 * p[1], t + 0.004); g.gain.setTargetAtTime(0, t + 0.004, 0.25);
        o.connect(g); g.connect(dest); o.start(t); o.stop(t + 2.0);
      });
    }
    function syncAlarms(list, when) {
      const seen = {};
      (Array.isArray(list) ? list : []).forEach(function (a) {
        if (!a || a.id == null) return;
        seen[a.id] = true;
        let v = alarms.get(a.id);
        if (!v) { v = alarmVoice(clamp(a.level | 0, 1, 3), when); alarms.set(a.id, v); if (a.acked) alarmStop(v, when); }
        else if (a.acked && !v.stopped) alarmStop(v, when);
      });
      alarms.forEach(function (v, id) { if (!seen[id]) { if (!v.stopped) alarmStop(v, when); alarms.delete(id); } });
      let loud = false;
      alarms.forEach(function (v) { if (!v.stopped && v.level >= 2) loud = true; });
      glide(machines.gain, MIX.machines * (loud ? 0.5 : 1), when, 0.12);
      glide(room.gain, MIX.room * (loud ? 0.55 : 1), when, 0.12);
    }
    function scheduleAlarms(when) {
      alarms.forEach(function (v) {
        if (v.stopped) return;
        if (v.level === 2) {
          while (v.next < when + 0.15) {
            const t = v.next;
            v.gate.gain.setValueAtTime(0, t);
            v.gate.gain.linearRampToValueAtTime(1, t + 0.006);
            v.gate.gain.setValueAtTime(1, t + 0.36);
            v.gate.gain.linearRampToValueAtTime(0, t + 0.37);
            v.next = t + 0.6;
          }
        } else if (v.level === 1) {
          while (v.next < when + 0.15) { chime(v.next, v.out); v.next += 2.4; }
        }
      });
    }

    // ---------- главный вход: аудио-вид → все слои
    let walk = 0;
    function update(v, when) {
      v = v || {};
      when = Math.max(when == null ? ctx.currentTime : when, ctx.currentTime);
      const vent = v.vent == null ? 1 : c01(v.vent), mains = v.mains == null ? 1 : c01(v.mains);
      walk = clamp(walk + (R() - 0.5) * 0.12, -1, 1);                      // медленная жизнь вентиляции, ±1,5 дБ
      glide(ventG.gain, 0.16 * vent * fromDb(walk * 1.5), when, 0.8);
      glide(grilleG.gain, 0.012 * vent, when, 0.8);
      glide(humG.gain, 0.010 * mains, when, 0.03);

      const ps = Array.isArray(v.pumps) ? v.pumps : [];
      pumps.forEach(function (p, i) {
        const s = c01(ps[i]);
        glide(p.o1.frequency, Math.max(1, p.f0 * s), when, 0.15);
        glide(p.o2.frequency, Math.max(2, 2 * p.f0 * s), when, 0.15);
        glide(p.tone.gain, 0.09 * Math.pow(s, 1.5), when, 0.15);
        glide(p.flow.gain, 0.30 * s * s, when, 0.25);
      });

      const r = c01(v.turbine), st = c01(v.steam);
      glide(turb.oR.frequency, Math.max(1, 50 * r), when, 0.3);
      glide(turb.oW.frequency, Math.max(1, 1250 * r), when, 0.3);
      glide(turb.rum.gain, 0.10 * r, when, 0.3);
      glide(turb.whine.gain, 0.010 * r * r, when, 0.3);
      glide(turb.roar.gain, 0.30 * Math.pow(st, 0.8) + 0.05 * r, when, 0.25);

      glide(heatG.gain, 0.02 * c01(v.heaters), when, 0.05);
      glide(sprayG.gain, 0.10 * c01(v.spray), when, 0.08);
      const rel = c01(v.relief);
      glide(reliefG.gain, 0.42 * rel, when, 0.06);
      glide(reliefLow.gain, 0.30 * rel, when, 0.06);

      const ds = Array.isArray(v.diesels) ? v.diesels : [];
      diesels.forEach(function (d, i) {
        const s = c01(ds[i]);
        glide(d.fire.frequency, Math.max(0.5, d.f * s), when, 0.2);
        glide(d.tone.frequency, Math.max(1, 2 * d.f * s), when, 0.2);
        glide(d.outG.gain, 0.30 * Math.pow(s, 0.7), when, 0.2);
      });

      transitions(v, when);
      syncAlarms(v.alarms, when);
      scheduleClicks(v, when);
      scheduleRods(v, when);
      scheduleAlarms(when);
    }

    function applyOut() { glide(out.gain, muted ? 0 : volume, ctx.currentTime, 0.05); }
    return {
      update: update,
      cue: function (name, when, o) {
        const f = CUES[name];
        if (!f) return false;
        f(Math.max(when == null ? ctx.currentTime : when, ctx.currentTime), o || {});
        return true;
      },
      setVolume: function (x) { volume = c01(x); applyOut(); },
      setMuted: function (m) { muted = !!m; applyOut(); },
      dispose: function () {
        sources.forEach(function (s) { try { s.stop(); } catch (e) { /* уже остановлен */ } });
        try { out.disconnect(); } catch (e) { /* уже отключён */ }
      },
      cueNames: Object.keys(CUES)
    };
  }

  // Живой режим: контекст по первому жесту, тишина при свёрнутой вкладке и на паузе.
  function live(opts) {
    let ctx = null, eng = null, muted = false, volume = 0.8, paused = false;
    function ensure() {
      if (!ctx) {
        const AC = root.AudioContext || root.webkitAudioContext;
        if (!AC) return;
        ctx = new AC(); eng = create(ctx, opts); eng.setVolume(volume); eng.setMuted(muted);
      }
      if (ctx.state === 'suspended' && !paused && !document.hidden) ctx.resume();
    }
    root.addEventListener('pointerdown', ensure, true);
    root.addEventListener('keydown', ensure, true);
    document.addEventListener('visibilitychange', function () {
      if (!ctx) return;
      if (document.hidden) ctx.suspend(); else if (!paused) ctx.resume();
    });
    function ready() { return !!eng && ctx.state === 'running'; }
    return {
      update: function (view) { if (ready()) eng.update(view, ctx.currentTime); },
      cue: function (name, o) { if (ready()) eng.cue(name, ctx.currentTime, o); },
      setMuted: function (m) { muted = !!m; if (eng) eng.setMuted(muted); },
      setVolume: function (x) { volume = c01(x); if (eng) eng.setVolume(volume); },
      pause: function (p) {
        paused = !!p;
        if (!ctx) return;
        if (paused) ctx.suspend(); else if (!document.hidden) ctx.resume();
      },
      get ready() { return ready(); }
    };
  }

  root.NightShiftAudio = { create: create, live: live, version: 1 };
})(typeof window !== 'undefined' ? window : globalThis);
