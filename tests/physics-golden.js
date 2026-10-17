// Эталон физики «Ночной смены»: смены 1–10 должны вести себя ровно как в v1.
//
//   node tests/physics-golden.js            — сравнить с tests/golden-v1.json
//   node tests/physics-golden.js --write    — записать эталон заново (только по решению автора)
//   node tests/physics-golden.js игра.html  — проверить другой файл
//
// Берётся логика до маркера «ИНТЕРФЕЙС» (через module.exports), Math.random подменяется сидированным
// генератором. Каждая смена прогоняется дважды: без игрока и по сценарию действий. Снимки состояния,
// табло, квитирования, реплик и итогов сравниваются целиком.
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');

const args = process.argv.slice(2);
const WRITE = args.includes('--write');
const file = args.find(a => a.endsWith('.html')) || path.join(__dirname, '..', 'night-shift-4.html');
const goldenPath = path.join(__dirname, 'golden-v1.json');

function load(html) {
  const a = html.indexOf('<script>') + '<script>'.length;
  const endMark = html.indexOf('if (typeof module', a);
  if (a < 8 || endMark < 0) throw new Error('не нашёл логику до маркера «ИНТЕРФЕЙС»');
  const b = html.indexOf('\n', endMark);
  const code = html.slice(a, b);
  let seed = 1;
  const rand = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const M = Object.create(Math); M.random = rand;
  const sandbox = { module: { exports: {} }, Math: M, console };
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox, { filename: 'logic.js' });
  return { api: sandbox.module.exports, reseed: s => { seed = s >>> 0; } };
}

// Сценарии действий игрока: [время, действие, аргумент]. Не обязаны побеждать — должны пройти по веткам кода.
const SCRIPTS = {
  1: [[1, 'rodPress', 1], [4, 'rodRelease'], [20, 'rodPress', 1], [21.5, 'rodRelease'], [40, 'rodPress', -1], [40.6, 'rodRelease'], [45, 'ack'], [60, 'rodPress', 1], [60.4, 'rodRelease']],
  2: [[1, 'togglePump', 1], [3, 'togglePump', 2], [5, 'rodPress', 1], [9, 'rodRelease'], [30, 'togglePump', 3], [35, 'rodPress', 1], [37, 'rodRelease'], [50, 'ack']],
  3: [[1, 'valve', 1], [1.2, 'valveRep', 1, 30], [10, 'rodPress', 1], [12, 'rodRelease'], [25, 'valveRep', 1, 20], [60, 'valveRep', -1, 5], [70, 'ack']],
  4: [[1, 'valveRep', 1, 25], [5, 'setSpray', true], [15, 'setSpray', false], [16, 'setHeater', true], [30, 'setHeater', false], [32, 'rodPress', 1], [34, 'rodRelease'], [50, 'ack']],
  5: [[1, 'boron', 1], [1.1, 'boronRep', 1, 40], [10, 'rodPress', 1], [14, 'rodRelease'], [20, 'valveRep', 1, 15], [60, 'valveRep', 1, 10], [100, 'boron', -1], [140, 'valveRep', -1, 20], [150, 'setSpray', true], [160, 'setSpray', false]],
  6: [[22.5, 'rodPress', -1], [27, 'rodRelease'], [23, 'valveRep', -1, 20], [24, 'togglePump', 2], [30, 'ack'], [40, 'setHeater', true], [50, 'setHeater', false]],
  7: [[3, 'startDG'], [15, 'togglePump', 0], [15.5, 'togglePump', 1], [16, 'togglePump', 2], [20, 'ack'], [40, 'valve', 1]],
  8: [[2, 'boron', -1], [2.1, 'boronRep', -1, 60], [10, 'rodPress', 1], [15, 'rodRelease'], [60, 'rodPress', -1], [61, 'rodRelease'], [80, 'ack']],
  9: [[5, 'valveRep', -1, 10], [60, 'valveRep', -1, 15], [120, 'boron', 1], [200, 'valveRep', 1, 20], [250, 'rodPress', 1], [252, 'rodRelease'], [300, 'ack'], [310, 'valveRep', 1, 20]],
  10: [[5, 'valveRep', -1, 10], [100, 'rodPress', -1], [104, 'rodRelease'], [150, 'valveRep', -1, 30], [200, 'openAZ'], [201, 'pressScram']],
};
const DUR = { 1: 120, 2: 120, 3: 150, 4: 120, 5: 220, 6: 120, 7: 160, 8: 160, 9: 380, 10: 380 };

const r9 = x => (typeof x === 'number' && isFinite(x)) ? +x.toPrecision(10) : x;
function snapState(s) {
  const o = {};
  for (const k of Object.keys(s).sort()) {
    const v = s[k];
    if (typeof v === 'number' || typeof v === 'boolean' || typeof v === 'string' || v == null) o[k] = r9(v);
    else if (Array.isArray(v)) o[k] = JSON.parse(JSON.stringify(v, (kk, vv) => r9(vv)));
    else if (typeof v === 'object') o[k] = JSON.parse(JSON.stringify(v, (kk, vv) => r9(vv)));
  }
  return o;
}

function act(g, a) {
  const [, name, x, n] = a;
  if (name === 'valveRep') { for (let i = 0; i < n; i++) g.valve(x, true); return; }
  if (name === 'boronRep') { for (let i = 0; i < n; i++) g.boron(x, true); return; }
  if (name === 'ack') { g.ack(); return; }
  if (name === 'openAZ') return;
  if (typeof g[name] === 'function') g[name](x);
}

function run(api, reseed, num, scripted) {
  reseed(1000 + num);
  const idx = api.LEVELS.findIndex(l => l.num === num);
  const g = new api.Game(idx), dt = api.CONFIG.dt;
  const actions = scripted ? [...(SCRIPTS[num] || [])].sort((p, q) => p[0] - q[0]) : [];
  const snaps = [], msgs = [], annLog = [];
  let ai = 0, lastMsg = null, nextSnap = 0;
  const steps = Math.round(DUR[num] / dt);
  for (let i = 0; i <= steps; i++) {
    while (ai < actions.length && actions[ai][0] <= g.t + 1e-9) act(g, actions[ai++]);
    if (g.t >= nextSnap - 1e-9) {
      snaps.push({ t: r9(g.t), s: snapState(g.s), lamps: { ...g.lamps }, prog: r9(g.prog) });
      nextSnap += 5;
    }
    if (g.msg && g.msg !== lastMsg) { lastMsg = g.msg; msgs.push([r9(g.msg.t), g.msg.prio, g.msg.src || '', g.msg.text]); }
    g.update(dt);
  }
  for (const id of Object.keys(g.ann).sort()) { const a = g.ann[id]; annLog.push([id, a.state, a.lv, r9(a.newT), r9(a.ackT), r9(a.offT)]); }
  return {
    level: num, scripted, events: g.events.map(e => ({ t: r9(e.t), type: e.type, pump: e.pump })),
    snaps, msgs, ann: annLog, log: g.log.map(e => [r9(e.t), e.kind, e.label]),
    m: JSON.parse(JSON.stringify(g.m, (k, v) => r9(v))),
    done: g.done, result: g.result && { success: g.result.success, reason: g.result.reason, nStars: g.result.nStars, score: g.result.score,
      title: g.result.title, stars: g.result.stars.map(s => [s.label, s.ok]), lines: g.result.lines },
  };
}

const { api, reseed } = load(fs.readFileSync(file, 'utf8'));
const out = [];
for (const lv of api.LEVELS) for (const sc of [false, true]) out.push(run(api, reseed, lv.num, sc));

if (WRITE) {
  fs.writeFileSync(goldenPath, JSON.stringify(out));
  console.log(`Эталон записан: ${path.relative(process.cwd(), goldenPath)} — ${out.length} прогонов`);
  for (const r of out) console.log(`  смена ${String(r.level).padStart(2)} ${r.scripted ? 'сценарий' : 'без игрока'}: ${r.done ? (r.result.success ? 'успех' : 'провал: ' + r.result.reason) + ', звёзд ' + r.result.nStars : 'не закончена'}`);
  process.exit(0);
}
// Строго: физика, события, табло, квитирование, метрики, исход и звёзды, моменты и важность реплик.
// Тексты подачи (реплики, журнал, заголовки итогов) полишинг переписывает — их расхождение только отчёт.
const physics = r => ({ snaps: r.snaps, events: r.events, ann: r.ann, m: r.m, done: r.done,
  msgs: r.msgs.map(x => x.slice(0, 3)), log: r.log.map(x => x.slice(0, 2)),
  result: r.result && { success: r.result.success, reason: r.result.reason, nStars: r.result.nStars, score: r.result.score, stars: r.result.stars.map(s => s[1]) } });
const texts = r => ({ msgs: r.msgs.map(x => x[3]), log: r.log.map(x => x[2]), result: r.result && { title: r.result.title, lines: r.result.lines, stars: r.result.stars.map(s => s[0]) } });
const gold = JSON.parse(fs.readFileSync(goldenPath, 'utf8'));
let bad = 0, txt = 0;
for (let i = 0; i < gold.length; i++) {
  const G = gold[i], O = out[i] || { msgs: [], log: [] };
  const P = physics(G), Q = physics(O);
  if (JSON.stringify(P) !== JSON.stringify(Q)) {
    bad++;
    const where = Object.keys(P).filter(k => JSON.stringify(P[k]) !== JSON.stringify(Q[k])).join(', ');
    console.log(`✗ смена ${G.level} ${G.scripted ? 'сценарий' : 'без игрока'}: физика расходится — ${where}`);
  }
  if (JSON.stringify(texts(G)) !== JSON.stringify(texts(O))) txt++;
}
if (bad) { console.log(`Физика изменилась: ${bad} из ${gold.length} прогонов.`); process.exit(1); }
console.log(`✓ Физика совпадает с v1: ${gold.length} прогонов (смены 1–10, без игрока и по сценарию).`);
if (txt) console.log(`  Тексты подачи отличаются от v1 в ${txt} прогонах — это ожидаемо, если их правили.`);
