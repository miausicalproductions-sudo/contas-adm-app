@echo off
rem Liga o miau-ia escondido, sem janela (o mesmo que acontece ao ligar o PC).
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0server.py"
echo miau-ia ligado.
timeout /t 2 >nul
