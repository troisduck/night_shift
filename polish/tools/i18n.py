#!/usr/bin/env python3
"""Английская версия «Ночной смены»: проверяет словарь i18n/en.json и вписывает его в игру.

  python polish/tools/i18n.py            — проверить и вписать словарь между маркерами I18N-EN
  python polish/tools/i18n.py --check    — только проверить (ничего не пишет)

Как устроен перевод (модуль L в начале скрипта игры):
  * в коде тексты остаются русскими и обёрнуты: ru('Строка') или ru`Строка ${x}`;
  * ключ словаря — сама русская строка; у шаблона подстановки заменены на {0}, {1}… (в переводе их можно переставлять);
  * статичная разметка <body> переводится при запуске по тем же ключам (текстовые узлы, aria-label, title);
  * подписи из CSS (content: "…") — правила html[lang="en"] в конце <style>.
Новый русский текст в коде — оберни в ru(…), добавь перевод в i18n/en.json и запусти этот скрипт.
Проверка: у каждого ключа есть перевод; плейсхолдеры {N} и HTML-теги совпадают; в переводе нет кириллицы.
"""
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME, DICT = ROOT / 'night-shift-4.html', ROOT / 'i18n' / 'en.json'
CY = re.compile(r'[А-Яа-яЁё]')
BEGIN, END = '/* I18N-EN */', '/* /I18N-EN */'


def cook(s):
    out, i = '', 0
    while i < len(s):
        c = s[i]
        if c != '\\': out += c; i += 1; continue
        n = s[i + 1]
        if n in 'ntr0': out += {'n': '\n', 't': '\t', 'r': '\r', '0': '\0'}[n]; i += 2
        elif n == 'u':
            if s[i + 2] == '{': j = s.index('}', i); out += chr(int(s[i + 3:j], 16)); i = j + 1
            else: out += chr(int(s[i + 2:i + 6], 16)); i += 6
        elif n == 'x': out += chr(int(s[i + 2:i + 4], 16)); i += 4
        elif n == '\n': i += 2
        else: out += n; i += 2
    return out


def scan_js(src, a, b):
    """Ключи из обёрток ru('…') и ru`…`: обходит строки, шаблоны (с вложенными ${…}), комментарии и регулярки."""
    keys, loose, stack, i = [], [], [], a
    def lit_end(i, q):
        j = i + 1
        while src[j] != q:
            j += 2 if src[j] == '\\' else 1
        return j
    def tpl_parts(i):   # от открывающей ` до закрывающей: части текста, конец
        parts, j = [''], i + 1
        while True:
            ch = src[j]
            if ch == '\\': parts[-1] += src[j:j + 2]; j += 2; continue
            if ch == '`': return parts, j
            if src.startswith('${', j):
                k, d = j + 2, 1
                while d:
                    c = src[k]
                    if c == '{': d += 1
                    elif c == '}': d -= 1
                    elif c in '\'"': k = lit_end(k, c)
                    elif c == '`': k = tpl_parts(k)[1]
                    k += 1
                parts.append(''); j = k; continue
            parts[-1] += ch; j += 1
    while i < b:
        c = src[i]
        if src.startswith(BEGIN, i): i = src.index(END, i) + len(END); continue   # сам словарь не сканируем
        if src.startswith('//', i): i = src.find('\n', i); continue
        if src.startswith('/*', i): i = src.find('*/', i + 2) + 2; continue
        if c == '/':
            k = i - 1
            while src[k] in ' \t': k -= 1
            if src[k] in '(,=:[!&|?;{}\n' or src[k - 5:k + 1] == 'return':
                j, cls = i + 1, False
                while True:
                    ch = src[j]
                    if ch == '\\': j += 2; continue
                    if ch == '[': cls = True
                    elif ch == ']': cls = False
                    elif ch == '/' and not cls: break
                    elif ch == '\n': j = None; break
                    j += 1
                if j: i = j + 1; continue
        if c in '\'"':
            j = lit_end(i, c); s = cook(src[i + 1:j])
            if CY.search(s): (keys if src[i - 3:i] == 'ru(' else loose).append((src.count('\n', 0, i) + 1, s))
            i = j + 1; continue
        if c == '`':
            parts, _ = tpl_parts(i)
            parts = [cook(p) for p in parts]
            if any(CY.search(p) for p in parts):
                k = ''.join(p if n == 0 else '{%d}' % (n - 1) + p for n, p in enumerate(parts))
                (keys if src[i - 2:i] == 'ru' else loose).append((src.count('\n', 0, i) + 1, k))
            # внутрь ${…} — там тоже бывают обёрнутые строки
            j = i + 1
            while src[j] != '`' and not src.startswith('${', j): j += 2 if src[j] == '\\' else 1
            if src[j] == '`': i = j + 1; continue
            stack.append(1); i = j + 2; continue
        if stack and c == '{': stack[-1] += 1
        elif stack and c == '}':
            stack[-1] -= 1
            if stack[-1] == 0:
                stack.pop(); j = i + 1
                while src[j] != '`' and not src.startswith('${', j): j += 2 if src[j] == '\\' else 1
                if src[j] == '`': i = j + 1; continue
                stack.append(1); i = j + 2; continue
        i += 1
    return keys, loose


def scan_html(src):
    body = src[src.index('<body>'):src.index('<script>')]
    keys = []
    class P(HTMLParser):
        def handle_data(self, d):
            if CY.search(d): keys.append(d.strip())
        def handle_starttag(self, tag, attrs):
            for k, v in attrs:
                if k in ('aria-label', 'title', 'placeholder', 'alt') and v and CY.search(v): keys.append(v.strip())
    P(convert_charrefs=True).feed(body)
    keys.append(re.search(r'<title>(.*?)</title>', src).group(1))
    return keys


def skeleton(s):   # теги без переводимых атрибутов — должны совпасть у ключа и перевода
    return [re.sub(r'\s(aria-label|title|placeholder|alt)="[^"]*"', '', t) for t in re.findall(r'<[^>]+>', s)]


def main():
    raw = GAME.read_text(encoding='utf-8')
    src = raw.replace('\r\n', '\n')
    a = src.index('<script>') + 8; b = src.rindex('</script>')
    jk, loose = scan_js(src, a, b)
    keys = list(dict.fromkeys([k for _, k in jk] + scan_html(src)))
    en = json.loads(DICT.read_text(encoding='utf-8'))
    errs = []
    for k in keys:
        if k not in en: errs.append(f'нет перевода: {k[:90]!r}'); continue
        v = en[k]
        if sorted(re.findall(r'\{\d+\}', k)) != sorted(re.findall(r'\{\d+\}', v)): errs.append(f'плейсхолдеры: {k[:70]!r}')
        if skeleton(k) != skeleton(v): errs.append(f'теги: {k[:70]!r}')
        if CY.search(v): errs.append(f'кириллица в переводе: {k[:70]!r}')
    unused = [k for k in en if k not in set(keys)]
    print(f'ключей в игре: {len(keys)}, в словаре: {len(en)}, лишних в словаре: {len(unused)}; необёрнутых русских литералов: {len(loose)} (звук и отладка — нарочно)')
    for e in errs: print('  ✗', e)
    if errs: sys.exit(1)
    if '--check' in sys.argv: return
    used = {k: en[k] for k in keys}
    blob = json.dumps(used, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    i, j = raw.index(BEGIN) + len(BEGIN), raw.index(END)
    GAME.write_text(raw[:i] + ' ' + blob + ' ' + raw[j:], encoding='utf-8', newline='')
    print(f'вписано в {GAME.name}: {len(blob) / 1024:.0f} КБ')


if __name__ == '__main__':
    main()
