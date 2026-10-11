# Troca o ícone padrão do Capacitor pelo ícone do Contas ADM em todas as densidades
import os, sys
from PIL import Image
src = Image.open(os.path.join(os.path.dirname(__file__), '..', 'build', 'icon.png')).convert('RGBA')
res = os.path.join(os.path.dirname(__file__), '..', 'android', 'app', 'src', 'main', 'res')
sizes = {'mdpi': 48, 'hdpi': 72, 'xhdpi': 96, 'xxhdpi': 144, 'xxxhdpi': 192}
for d, s in sizes.items():
    folder = os.path.join(res, 'mipmap-' + d)
    if not os.path.isdir(folder): continue
    for name in ('ic_launcher.png', 'ic_launcher_round.png'):
        src.resize((s, s), Image.LANCZOS).save(os.path.join(folder, name))
    fg = Image.new('RGBA', (int(s * 2.25), int(s * 2.25)), (0, 0, 0, 0)); k = int(s * 2.25 * 0.70)
    fg.paste(src.resize((k, k), Image.LANCZOS), ((fg.width - k) // 2, (fg.height - k) // 2))
    fg.save(os.path.join(folder, 'ic_launcher_foreground.png'))
# ícone adaptativo: fundo da mesma cor do ícone
vals = os.path.join(res, 'values', 'ic_launcher_background.xml')
if os.path.exists(vals):
    open(vals, 'w').write('<?xml version="1.0" encoding="utf-8"?>\n<resources><color name="ic_launcher_background">#FFFFFF</color></resources>\n')
print('ícones ok')

# ícone pequeno (branco) das notificações e permissões de aviso na hora certa
noti = Image.open(os.path.join(os.path.dirname(__file__), '..', 'build', 'src', 'notify-192.png')).convert('RGBA')
for d, s in {'mdpi': 24, 'hdpi': 36, 'xhdpi': 48, 'xxhdpi': 72, 'xxxhdpi': 96}.items():
    folder = os.path.join(res, 'drawable-' + d); os.makedirs(folder, exist_ok=True)
    noti.resize((s, s), Image.LANCZOS).save(os.path.join(folder, 'ic_stat_notify.png'))
man = os.path.join(res, '..', 'AndroidManifest.xml')
if os.path.exists(man):
    m = open(man).read()
    add = ''.join('    <uses-permission android:name="android.permission.%s" />\n' % p for p in ('POST_NOTIFICATIONS', 'SCHEDULE_EXACT_ALARM', 'RECEIVE_BOOT_COMPLETED') if p not in m)
    if add:
        m = m.replace('</manifest>', add + '</manifest>'); open(man, 'w').write(m)
print('notificações ok')
