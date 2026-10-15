@echo off
chcp 65001 >nul
rem So no PC 2, como administrador: deixa o PC 1 falar com o miau-ia pela rede local (perfil Privado).
netsh advfirewall firewall add rule name="miau-ia 8765" dir=in action=allow protocol=TCP localport=8765 profile=private
pause
