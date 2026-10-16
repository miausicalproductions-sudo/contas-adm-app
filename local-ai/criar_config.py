"""Cria o config.toml (a partir do config.example.toml) com um código novo para este PC. Não mexe se já existir."""
import os
import secrets

aqui = os.path.dirname(os.path.abspath(__file__))
dest = os.path.join(aqui, "config.toml")
if os.path.exists(dest):
    print("config.toml já existe: mantido.")
else:
    with open(os.path.join(aqui, "config.example.toml"), encoding="utf-8") as f:
        t = f.read()
    t = t.replace('token = ""', 'token = "%s"' % secrets.token_urlsafe(18), 1)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(t)
    print("Criei o config.toml com um código novo para este PC.")
