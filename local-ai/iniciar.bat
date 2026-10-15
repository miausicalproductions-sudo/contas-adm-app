@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo miau-ia com a janela aberta (para ver erros). Feche esta janela para parar.
venv\Scripts\python.exe server.py
pause
