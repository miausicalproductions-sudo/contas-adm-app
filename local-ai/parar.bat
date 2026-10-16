@echo off
chcp 65001 >nul
rem Desliga o miau-ia (libera a RAM). Para ligar de novo: iniciar.bat ou reinicie o PC.
taskkill /f /im pythonw.exe >nul 2>nul && echo miau-ia desligado. || echo O miau-ia ja estava desligado.
pause
