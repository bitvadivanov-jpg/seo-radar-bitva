"""Делает одиночный HTML, открываемый на телефоне даже без хостинга.

Поисковая статистика не включается без OAuth и серверного расписания.
"""
from pathlib import Path
import base64
import json
import re

root=Path(__file__).resolve().parents[1]
web=root/'web'
html=(web/'index.html').read_text(encoding='utf-8')
css=(web/'styles.css').read_text(encoding='utf-8')
js=(web/'app.js').read_text(encoding='utf-8')
keywords=json.loads((root/'config/keywords.json').read_text(encoding='utf-8'))
bootstrap=json.dumps({'keywords':keywords}, ensure_ascii=False)
icon='data:image/png;base64,'+base64.b64encode((web/'icons/icon-192.png').read_bytes()).decode('ascii')
html=html.replace('<link rel="manifest" href="./manifest.webmanifest">','')
html=html.replace('<link rel="icon" type="image/png" sizes="192x192" href="./icons/icon-192.png">',f'<link rel="icon" type="image/png" href="{icon}">')
html=html.replace('<link rel="apple-touch-icon" href="./icons/icon-192.png">','')
html=html.replace('src="./icons/icon-192.png"',f'src="{icon}"')
html=html.replace('<link rel="stylesheet" href="./styles.css">','<style>\n'+css+'\n</style>')
html=html.replace('<script id="bootstrap" type="application/json">{}</script>','<script id="bootstrap" type="application/json">'+bootstrap+'</script>')
html=re.sub(r'<script src="\./app\.js(?:\?[^\"]*)?" defer></script>',lambda _: '<script>\n'+js+'\n</script>',html,count=1)
html=html.replace('<title>SEO-Радар — Битва диванов</title>','<title>SEO-Радар — просмотр на телефоне</title>')
output=root/'SEO_Радар_ПРОСМОТР_НА_ТЕЛЕФОНЕ.html'
output.write_text(html,encoding='utf-8')
print(f'Готово: {output.name}, {len(html)} символов')
