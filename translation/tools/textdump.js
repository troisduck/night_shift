#!/usr/bin/env node
/* Снимок всех текстов игры по экранам — для перевода (задание 4-night-shift-english-prompt.md).
   Открывает игру в Chromium через отладочные параметры адреса и с каждого экрана собирает:
   текст DOM и SVG, атрибуты aria-label / title / alt / placeholder, CSS content у ::before / ::after,
   всё, что нарисовано на canvas (fillText), подсказки при наведении (tipFor), наложение «?», «Вызов».

     node translation/tools/textdump.js --lang ru --out translation/dump/ru-before
     node translation/tools/textdump.js --lang en --out translation/dump/en --shots 1920x1080,1024x768,390x844

   Пишет texts.json (экран → отсортированный список строк) и, с --shots, снимки экранов.
   Сравнить два снимка: node translation/tools/textdump.js --diff папка1 папка2
   Кириллица в снимке: node translation/tools/textdump.js --cyr папка */
'use strict';
const fs = require('fs'), path = require('path');
const PW = process.env.PLAYWRIGHT_MODULE || '/opt/node-tools/node_modules/playwright';

const argv = process.argv.slice(2), opt = k => { const i = argv.indexOf('--' + k); return i >= 0 ? argv[i + 1] : null; };
const ROOT = path.resolve(__dirname, '..', '..');

if (opt('diff') != null) {
  // числа живых приборов и клеймо ОТК зависят от времени — без --exact цифры не сравниваются
  const norm = x => (argv.includes('--exact') ? x : x.replace(/\d+/g, '#'));
  const rd = i => { const o = JSON.parse(fs.readFileSync(path.join(argv[argv.indexOf('--diff') + i], 'texts.json'), 'utf8')); for (const k in o) o[k] = o[k].map(norm); return o; };
  const a = rd(1), b = rd(2);
  let n = 0;
  for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) {
    const A = new Set(a[k] || []), B = new Set(b[k] || []);
    const gone = [...A].filter(x => !B.has(x)), added = [...B].filter(x => !A.has(x));
    if (!gone.length && !added.length) continue;
    n++; console.log(`\n== ${k}`); gone.forEach(x => console.log('  - ' + x)); added.forEach(x => console.log('  + ' + x));
  }
  console.log(n ? `\nэкранов с отличиями: ${n}` : 'тексты совпадают на всех экранах');
  process.exit(n ? 1 : 0);
}
if (opt('cyr') != null) {
  const a = JSON.parse(fs.readFileSync(path.join(opt('cyr'), 'texts.json'), 'utf8'));
  // название языка в выборе языка — на нём самом (задание: «подпись каждого варианта — на его языке»)
  const allow = new Set(['Русский']);
  let n = 0;
  for (const [k, list] of Object.entries(a)) for (const x of list) if (/[А-Яа-яЁё]/.test(x) && !allow.has(x)) { n++; console.log(`${k}: ${x}`); }
  console.log(n ? `\nстрок с кириллицей: ${n}` : 'кириллицы нет ни на одном экране');
  process.exit(n ? 1 : 0);
}

const FILE = path.resolve(ROOT, opt('file') || 'night-shift-4.html');
const LANG = opt('lang') || 'ru';
const OUT = path.resolve(ROOT, opt('out') || `translation/dump/${LANG}`);
const SHOTS = (opt('shots') || '').split(',').filter(Boolean).map(s => s.split('x').map(Number));
const ONLY = opt('only') ? new RegExp(opt('only')) : null;

const levels = Array.from({ length: 10 }, (_, i) => i + 1);
// экран: q — параметры адреса, act — что сделать на странице, wait — мс до снимка
const STATES = [
  { id: 'splash', q: 'screen=splash', wait: 300 },
  { id: 'door', q: 'screen=door', wait: 600 },
  { id: 'door-reset', q: 'screen=door', wait: 600, act: async p => { await p.click('.gl-links [data-a="reset"]'); } },
  { id: 'intro', q: 'screen=intro', wait: 900, act: async p => { const seen = new Set(); for (let i = 0; i < 2; i++) { (await p.evaluate(COLLECT)).forEach(x => seen.add(x)); await p.mouse.click(300, 300); await p.waitForTimeout(700); } return seen; } },
  { id: 'sign', q: 'screen=sign', wait: 600 },
  { id: 'shifts', q: 'screen=shifts', wait: 600 },
  { id: 'shifts-all', q: 'screen=shifts', wait: 600, save: { stars: { wake: 3, water: 2, power: 1, pressure: 3, peak: 2, pump: 1, blackout: 3, xenon: 2, shift: 1 }, introSeen: true, hallSeen: true } },
  { id: 'shifts-expert', q: 'screen=shifts', wait: 600, act: async p => { await p.click('.gs-knife'); await p.waitForTimeout(200); } },
  { id: 'settings', q: 'screen=settings', wait: 500 },
  { id: 'settings-reset', q: 'screen=settings', wait: 500, act: async p => { await p.click('.st-sheet [data-a="reset"]'); } },
  ...levels.map(n => ({ id: `brief-${n}`, q: `level=${n}&paused=1`, wait: 700, act: async p => { await p.evaluate(i => showBrief(i), n - 1); await p.waitForTimeout(300); } })),
  ...levels.map(n => ({ id: `play-${n}`, q: `level=${n}&paused=1`, wait: 900, keys: true, what: true })),
  ...levels.map(n => ({ id: `result-ok-${n}`, q: `screen=result&level=${n}`, wait: 3500 })),
  ...[1, 6, 9].map(n => ({ id: `result-fail-${n}`, q: `screen=result&level=${n}&fail=1`, wait: 3500 })),
  { id: 'event-pump', q: 'level=6&event=pump_trip&paused=1', wait: 1200, what: true },
  { id: 'event-blackout', q: 'level=7&event=blackout&paused=1', wait: 1200, what: true },
  { id: 'alarm-test', q: 'unlockall=1&event=alarm_test', wait: 800 },
  { id: 'unlockall', q: 'level=9&unlockall=1&paused=1', wait: 800, keys: true },
  { id: 'moment-guide', q: 'moment=guide', wait: 1500 },
  { id: 'moment-unlock', q: 'moment=unlock', wait: 4500 },
  { id: 'moment-hall', q: 'moment=hall', wait: 4000 },
  { id: 'moment-sync', q: 'moment=sync', wait: 6000 },
  { id: 'moment-pump', q: 'moment=pump', wait: 2500 },
  { id: 'moment-scram', q: 'moment=scram', wait: 9000 },
  { id: 'moment-blackout', q: 'moment=blackout', wait: 3000 },
  { id: 'moment-explosion', q: 'moment=explosion', wait: 16000 },
  ...['overpower', 'period', 'tout', 'subcool', 'pHigh', 'pLow', 'pumpLimit', 'backup', 'schedule'].map(w => ({ id: `end-${w}`, q: `moment=end&why=${w}`, wait: 7000 })),
  { id: 'moment-dawn', q: 'moment=dawn', wait: 7000 },
];

const INIT = (seed, save) => {
  // canvas: записываем всё, что рисуется текстом
  window.__ct = new Set();
  for (const P of [CanvasRenderingContext2D.prototype]) {
    for (const fn of ['fillText', 'strokeText']) { const f = P[fn]; P[fn] = function (t, ...r) { try { window.__ct.add(String(t)); } catch (e) { /* — */ } return f.call(this, t, ...r); }; }
  }
  // случайности на зерне — кадры повторяются
  let s = seed >>> 0;
  Math.random = () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  try { localStorage.clear(); if (save) localStorage.setItem('night-shift-npp-v1', JSON.stringify(save)); } catch (e) { /* — */ }
};

const COLLECT = () => {
  const out = new Set(), add = (p, s) => { s = String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); if (s) out.add(p + s); };
  add('title: ', document.title); add('lang: ', document.documentElement.lang);
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) { const t = n.parentNode && n.parentNode.tagName; if (t === 'SCRIPT' || t === 'STYLE') continue; add('', n.nodeValue); }
  for (const el of document.querySelectorAll('*')) {
    for (const a of ['aria-label', 'title', 'alt', 'placeholder']) if (el.hasAttribute(a)) add(a + ': ', el.getAttribute(a));
    for (const ps of ['::before', '::after']) { const c = getComputedStyle(el, ps).content; if (c && c !== 'none' && c !== 'normal' && /[A-Za-zА-Яа-яЁё]/.test(c)) add('css: ', c); }
  }
  for (const t of window.__ct || []) add('canvas: ', t);
  if (typeof tipFor === 'function') for (const el of document.querySelectorAll('[data-tip], .cover')) {
    try { const c = tipFor(el); if (c) add('tip: ', c[0] + ' | ' + c[1] + (c[2] ? ' | ' + c[2].join(' ') : '')); } catch (e) { /* — */ }
  }
  return [...out];
};

(async () => {
  const { chromium } = require(PW);
  const browser = await chromium.launch();
  fs.mkdirSync(OUT, { recursive: true });
  const texts = {}, errors = [];
  const sizes = SHOTS.length ? SHOTS : [[1366, 768]];
  for (const st of STATES) {
    if (ONLY && !ONLY.test(st.id)) continue;
    for (const [W, H] of sizes) {
      const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
      await ctx.addInitScript(INIT, 7, st.save || null);
      const p = await ctx.newPage();
      p.on('pageerror', e => errors.push(`${st.id}: ${e.message}`));
      p.on('console', m => { if (m.type() === 'error') errors.push(`${st.id}: console: ${m.text()}`); });
      const url = 'file://' + FILE + '?' + st.q + (LANG ? '&lang=' + LANG : '');
      await p.goto(url); await p.waitForTimeout(st.wait || 800);
      const set = new Set(await p.evaluate(COLLECT));
      if (st.act) { const got = await st.act(p); if (got) got.forEach(x => set.add(x)); await p.waitForTimeout(300); (await p.evaluate(COLLECT)).forEach(x => set.add(x)); }
      if (st.what) { try { await p.click('#btn-what'); await p.waitForTimeout(400); (await p.evaluate(COLLECT)).forEach(x => set.add(x)); } catch (e) { errors.push(`${st.id}: «Вызов»: ${e.message.split('\n')[0]}`); } }
      if (st.keys) { await p.keyboard.press('Slash'); await p.waitForTimeout(250); (await p.evaluate(COLLECT)).forEach(x => set.add(x)); await p.keyboard.press('Escape'); }
      if (SHOTS.length) await p.screenshot({ path: path.join(OUT, `${st.id}-${W}x${H}.png`) });
      if (W === sizes[0][0] && H === sizes[0][1]) texts[st.id] = [...set].sort();
      await ctx.close();
    }
    process.stdout.write('.');
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'texts.json'), JSON.stringify(texts, null, 1));
  fs.writeFileSync(path.join(OUT, 'errors.txt'), errors.join('\n') + '\n');
  console.log(`\n${Object.keys(texts).length} экранов → ${path.relative(ROOT, OUT)}; ошибок страницы: ${errors.length}`);
})().catch(e => { console.error(e); process.exit(1); });
