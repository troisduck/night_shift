#!/usr/bin/env node
/* Проверка словаря STRINGS (задание 4-night-shift-english-prompt.md):
   - у каждого ключа в STRINGS.ru есть пара в STRINGS.en и наоборот;
   - в шаблонах обоих языков одинаковый набор {подстановок};
   - в английском нет кириллицы;
   - каждый ключ, который упоминает код (t('…'), tn('…'), data-t="…", ключи в данных), есть в STRINGS.ru;
   - имя t нигде не перекрыто локальной переменной там, где его вызывают (иначе t('…') вызовет не ту функцию).

     node tests/strings.js            всё; ✗ — код выхода 1
     node tests/strings.js --file другой.html */
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const NM = process.env.NODE_TOOLS || '/opt/node-tools/node_modules';
const args = process.argv.slice(2), fi = args.indexOf('--file');
const FILE = path.resolve(__dirname, '..', fi >= 0 ? args[fi + 1] : 'night-shift-4.html');
const src = fs.readFileSync(FILE, 'utf8');
const a = src.indexOf('<script>') + '<script>'.length, z = src.lastIndexOf('</script>');
const code = src.slice(a, z);
const logic = code.slice(0, code.lastIndexOf('/*', code.indexOf('ИНТЕРФЕЙС. Только отрисовка')));
const mod = { exports: {} };
vm.runInNewContext(logic, { module: mod, Math, console });
const { STRINGS } = mod.exports;

let bad = 0; const warn = [];
const fail = m => { bad++; console.log('✗ ' + m); };
const params = s => new Set((s.match(/\{(\w+)\}/g) || []).map(x => x.slice(1, -1)));
const ru = STRINGS.ru, en = STRINGS.en;

// 1. пары ключей и подстановки
for (const k of Object.keys(ru)) if (!(k in en)) fail(`нет в en: ${k}`);
for (const k of Object.keys(en)) if (!(k in ru)) fail(`нет в ru: ${k}`);
for (const k of Object.keys(ru)) {
  if (!(k in en)) continue;
  const p = [...params(ru[k])].sort().join(','), q = [...params(en[k])].sort().join(',');
  if (p !== q) fail(`подстановки разные: ${k} — ru {${p}} / en {${q}}`);
  const fr = ru[k].split('|').length, fe = en[k].split('|').length;
  if ((fr > 1 || fe > 1) && !(fr === 3 && fe === 2) && fr !== fe && !k.startsWith('date.')) warn.push(`формы через «|»: ${k} — ru ${fr}, en ${fe}`);
}
// 2. кириллица в английском
for (const [k, v] of Object.entries(en)) if (/[А-Яа-яЁё]/.test(v)) fail(`кириллица в en: ${k} = ${v}`);

// 3. ключи, которые упоминает код
const prefixes = new Set(Object.keys(ru).map(k => k.split('.')[0]));
const used = new Set();
const espree = require(path.join(NM, 'espree')), escope = require(path.join(NM, 'eslint-scope'));
const ast = espree.parse(code, { ecmaVersion: 'latest', range: true, loc: true });
(function walk(n) {
  if (!n || typeof n.type !== 'string') return;
  if (n.type === 'Literal' && typeof n.value === 'string' && /^[a-z]+(\.[A-Za-z0-9]+)+$/.test(n.value) && prefixes.has(n.value.split('.')[0])) used.add(n.value);
  for (const key of Object.keys(n)) { const v = n[key]; if (Array.isArray(v)) v.forEach(walk); else if (v && typeof v.type === 'string') walk(v); }
})(ast);
for (const m of src.matchAll(/data-t(?:-aria|-html)?="([^"]+)"/g)) used.add(m[1]);
for (const k of used) if (!(k in ru)) fail(`ключа нет в STRINGS.ru: ${k}`);
const unused = Object.keys(ru).filter(k => !used.has(k));
if (unused.length) warn.push(`ключи, которых код не упоминает буквально (${unused.length}): ${unused.join(', ')}`);

// 4. имя t перекрыто там, где его вызывают
const calls = new Set();
(function walk(n) {
  if (!n || typeof n.type !== 'string') return;
  if (n.type === 'CallExpression' && n.callee.type === 'Identifier' && (n.callee.name === 't' || n.callee.name === 'tn')) calls.add(n.callee);
  for (const key of Object.keys(n)) { const v = n[key]; if (Array.isArray(v)) v.forEach(walk); else if (v && typeof v.type === 'string') walk(v); }
})(ast);
const sm = escope.analyze(ast, { ecmaVersion: 2022, sourceType: 'script' });
let nCalls = 0;
for (const sc of sm.scopes) for (const ref of sc.references) {
  if (!calls.has(ref.identifier)) continue;
  nCalls++;
  const r = ref.resolved;
  if (r && r.scope.type !== 'global') fail(`${ref.identifier.name}() перекрыт локальным именем — строка скрипта ${ref.identifier.loc.start.line}`);
}

warn.forEach(w => console.log('? ' + w));
console.log(`\nключей: ru ${Object.keys(ru).length}, en ${Object.keys(en).length} · вызовов t/tn: ${nCalls} · ${bad ? '✗ ' + bad : '✓ без ошибок'}`);
process.exit(bad ? 1 : 0);
