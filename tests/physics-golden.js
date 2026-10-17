#!/usr/bin/env node
/* Эталон физики смен 1–10: логика игры (всё до маркера «ИНТЕРФЕЙС») гоняется в Node без браузера.
   Каждая смена — несколько сценариев: без игрока, простой «оператор», «лихач» (стержни вверх до АЗ),
   «ключ» (защиты выведены ключом). Случайности — на зерне, поэтому прогон повторяется точь-в-точь.

     node tests/physics-golden.js            сравнить с эталоном
     node tests/physics-golden.js --write    снять эталон заново (только по решению автора)
     node tests/physics-golden.js --file другой.html
     node tests/physics-golden.js --notes 500   показать больше отличий текста (по умолчанию 40)
     node tests/physics-golden.js --lang en     все тексты прогонов по-английски — прочитать подряд, кириллица — ошибка

   Физика (числа состояния, конец смены, звёзды) сравнивается строго — расхождение = ошибка.
   Тексты (реплики, журнал действий, итоги, «Вызов») снимаются по-русски и сравниваются отчётом:
   тексты подачи меняются по заданиям, физика — нет. */
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');

const args = process.argv.slice(2);
const WRITE = args.includes('--write');
const fileArg = args.indexOf('--file');
const FILE = path.resolve(__dirname, '..', fileArg >= 0 ? args[fileArg + 1] : 'night-shift-4.html');
const notesArg = args.indexOf('--notes'), NOTES = notesArg >= 0 ? +args[notesArg + 1] : 40;   // сколько отличий текста показать
const langArg = args.indexOf('--lang'), LANG = langArg >= 0 ? args[langArg + 1] : null;        // --lang en: все тексты прогонов на этом языке — без сравнения
const GOLD = path.join(__dirname, 'golden-pre-translation.json');

// логика без DOM: от начала скрипта до комментария с маркером «ИНТЕРФЕЙС»
function loadLogic(seed) {
  const src = fs.readFileSync(FILE, 'utf8');
  const a = src.indexOf('<script>') + '<script>'.length;
  const m = src.indexOf('ИНТЕРФЕЙС. Только отрисовка');
  if (a < 8 || m < 0) throw new Error('не нашёл <script> или маркер «ИНТЕРФЕЙС» в ' + FILE);
  const b = src.lastIndexOf('/*', m);
  let s = seed >>> 0;
  const M = Object.create(Math);
  M.random = () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const mod = { exports: {} };
  vm.runInNewContext(src.slice(a, b), { module: mod, Math: M, console });
  const L = mod.exports;
  if (typeof L.setLang === 'function') L.setLang(LANG || 'ru');   // тексты эталона — по-русски
  return L;
}

const num = v => (typeof v === 'number' ? (Number.isFinite(v) ? +v.toPrecision(12) : String(v)) : v);

// простой «оператор»: идёт к цели короткими нажатиями, следит за насосами, давлением, бором и дизелями
function operator(L, g, st) {
  const s = g.s, gc = g.goalCfg, C = L.CONFIG;
  if (st.hold > 0) { st.hold -= C.dt; if (st.hold <= 0) g.rodRelease(); return; }
  st.k = (st.k || 0) + 1; if (st.k % 10) return;                     // решает раз в 0,5 с
  if (s.offsite) s.pumps.forEach((p, i) => { if (!p.on && !p.tripped && g.open.has('pumps')) g.togglePump(i); });
  if (!s.offsite && s.dg === 'off' && g.open.has('dg')) g.startDG();
  if (!s.offsite && s.dg === 'on') [0, 1].forEach(i => { if (!s.pumps[i].on) g.togglePump(i); });
  if (g.open.has('pressure') && !s.flags.autoPressure) {
    if (s.p < 15.7) g.setHeater(true); else if (s.p > 16.3) g.setSpray(true);
    else { if (s.heater) g.setHeater(false); if (s.spray) g.setSpray(false); }
  }
  if (g.open.has('boron') && !s.scram) { if (s.h > 58) g.boron(1, false); else if (s.h < 32) g.boron(-1, false); }
  let dir = 0;
  if (s.overT > 0) { dir = -1; g.valve(-1, false); }
  else if (gc.v === 'power') { const e = s.Pth - gc.target; if (e < -gc.tol / 2 && s.doubling > 25) dir = 1; else if (e > gc.tol / 2 && s.rho > -40) dir = -1; }
  else if (gc.v === 'mwe' && s.turbineOnline) {
    const d = g.demand(); if (s.mwe < d * 0.98) g.valve(1, false); else if (s.mwe > d * 1.02) g.valve(-1, false);
    if (s.Tout < 300 && s.doubling > 25) dir = 1; else if (s.Tout > 318) dir = -1;
  } else if (gc.v === 'powerMax') { if (s.Pth > gc.max - 0.04) { dir = -1; g.valve(-1, false); } }
  if (dir) { g.rodPress(dir); st.hold = 0.25; }
  if (st.k % 300 === 0) g.explain();
}
const SCEN = {
  idle: () => {},
  operator,
  reckless: (L, g, st) => { if (!st.on) { st.on = 1; g.rodPress(1); } },
  key: (L, g, st) => {
    if (!st.k) { st.k = 1; g.breakSeal(); g.setProtection(false); g.rodPress(1); }
    if (g.s.Pth > 1.2 && g.s.inp.rodDir) g.rodRelease();
  },
};

function run(level, scen, seed) {
  const L = loadLogic(seed), g = new L.Game(level), C = L.CONFIG, st = {};
  const phys = [], msgs = [], expl = [];
  let lastMsg = 0, endT = null;
  const T = 420;
  for (let i = 0; i * C.dt < T; i++) {
    SCEN[scen](L, g, st);
    g.update(C.dt);
    if (g.msg && g.msg.id !== lastMsg) { lastMsg = g.msg.id; msgs.push([+g.t.toFixed(2), g.msg.prio, g.msg.src || '', g.msg.text]); }
    if (i % 100 === 0) {
      const s = g.s;
      phys.push([s.t, s.Pth, s.P, s.Tout, s.Tin, s.p, s.mwe, s.h, s.v, s.cB, s.xx, s.W, s.flow, s.rho, s.dmg, s.scram, s.scramReason, s.dg, s.offsite, s.damaged, g.prog].map(num));
      if (i % 600 === 0) expl.push([+g.t.toFixed(2), g.explain()]);
    }
    if (g.done && endT == null) endT = g.t;
    if (endT != null && g.t - endT > 6) break;
  }
  const r = g.result;
  return {
    physics: { phys, end: endT == null ? null : num(endT), success: r ? r.success : null, reason: r ? r.reason || null : null,
      stars: r ? r.stars.map(x => x.ok) : null, nStars: r ? r.nStars : null, score: r ? r.score : null },
    texts: { msgs, expl, log: g.log.map(e => [+e.t.toFixed(2), e.kind, e.label]),
      result: r ? { title: r.title, lines: r.lines, stars: r.stars.map(x => [x.label, x.hint]) } : null },
  };
}

function all() {
  const L = loadLogic(1), out = {};
  L.LEVELS.forEach((lv, i) => {
    for (const sc of Object.keys(SCEN)) {
      if (sc === 'key' && lv.physics.automation === false) continue;   // в «Без страховки» ключа нет
      out[`${i + 1}-${lv.id}-${sc}`] = run(i, sc, 1000 + i * 17 + sc.length);
    }
  });
  return out;
}

const cur = all();
if (LANG) {   // все реплики, «Вызов», журнал и итоги прогонов на выбранном языке — прочитать подряд; кириллица — ошибка
  const seen = new Map();
  for (const [k, r] of Object.entries(cur)) {
    const add = (kind, x) => { if (x && !seen.has(x)) seen.set(x, `${k} · ${kind}`); };
    r.texts.msgs.forEach(m => add('реплика', m[3])); r.texts.expl.forEach(e => add('«Вызов»', e[1])); r.texts.log.forEach(l => add('журнал', l[2]));
    if (r.texts.result) { add('итог', r.texts.result.title); r.texts.result.lines.forEach(x => add('итог', x)); r.texts.result.stars.forEach(s => { add('звезда', s[0]); add('звезда', s[1]); }); }
  }
  let cyr = 0;
  for (const [x, where] of seen) { const c = /[А-Яа-яЁё]/.test(x); if (c) cyr++; console.log(`${c ? '✗ ' : ''}[${where}] ${x}`); }
  console.log(`\nразных текстов: ${seen.size} · с кириллицей: ${cyr}`);
  process.exit(cyr ? 1 : 0);
}
if (WRITE) {
  fs.writeFileSync(GOLD, JSON.stringify(cur));
  console.log(`эталон записан: ${path.relative(process.cwd(), GOLD)}, прогонов ${Object.keys(cur).length}`);
  process.exit(0);
}
if (!fs.existsSync(GOLD)) { console.error('нет эталона — снять: node tests/physics-golden.js --write'); process.exit(2); }
const gold = JSON.parse(fs.readFileSync(GOLD, 'utf8'));
let bad = 0, txt = 0; const notes = [];
for (const k of Object.keys(gold)) {
  if (!cur[k]) { bad++; notes.push(`✗ ${k}: прогона нет`); continue; }
  if (JSON.stringify(gold[k].physics) !== JSON.stringify(cur[k].physics)) { bad++; notes.push(`✗ ${k}: физика разошлась`); }
  const a = gold[k].texts, b = cur[k].texts;
  for (const part of ['msgs', 'expl', 'log']) {
    const n = Math.max(a[part].length, b[part].length);
    for (let i = 0; i < n; i++) if (JSON.stringify(a[part][i]) !== JSON.stringify(b[part][i])) {
      txt++; if (txt <= NOTES) notes.push(`  ~ ${k} ${part}[${i}]\n      было: ${JSON.stringify(a[part][i])}\n      стало: ${JSON.stringify(b[part][i])}`);
    }
  }
  if (JSON.stringify(a.result) !== JSON.stringify(b.result)) { txt++; if (txt <= NOTES) notes.push(`  ~ ${k} итоги\n      было: ${JSON.stringify(a.result)}\n      стало: ${JSON.stringify(b.result)}`); }
}
console.log(notes.join('\n'));
console.log(`\nфизика: ${bad ? '✗ ' + bad + ' расхождений' : '✓ совпадает'} (${Object.keys(gold).length} прогонов) · тексты: ${txt ? txt + ' отличий (отчётом)' : 'совпадают'}`);
process.exit(bad ? 1 : 0);
