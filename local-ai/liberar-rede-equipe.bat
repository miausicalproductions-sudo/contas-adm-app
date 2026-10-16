@echo off
chcp 65001 >nul
rem No PC 1, como administrador: deixa o Mac (e outros computadores da equipe) usarem as IAs deste PC pela rede local.
net session >nul 2>&1 || (echo Clique com o botao direito neste arquivo e escolha "Executar como administrador". & pause & exit /b)
cd /d "%~dp0"
netsh advfirewall firewall delete rule name="miau-ia 8765" >nul 2>nul
netsh advfirewall firewall add rule name="miau-ia 8765" dir=in action=allow protocol=TCP localport=8765 profile=private >nul && echo Firewall liberado (rede privada, porta 8765).
"%~dp0venv\Scripts\python.exe" rede.py abrir
taskkill /f /im pythonw.exe >nul 2>nul
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0server.py"
echo miau-ia reiniciado.
echo.
echo Se o Mac nao conectar: no Windows, Configuracoes - Rede - a rede de voces precisa estar como "Privada".
pause
