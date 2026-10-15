@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  Atualizando o miau-ia (codigo novo do GitHub)
echo  Mantem o config.toml (chave e codigos), o venv e a pasta dados.
echo ============================================================
if not exist venv\Scripts\python.exe (
  echo Nao achei a instalacao nesta pasta. Rode o instalar.bat primeiro.
  pause
  exit /b 1
)
set TMPZ=%TEMP%\miau-ia-novo
if exist "%TMPZ%" rmdir /s /q "%TMPZ%"
mkdir "%TMPZ%"
powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing 'https://github.com/miausicalproductions-sudo/contas-adm-app/archive/refs/heads/main.zip' -OutFile '%TMPZ%\main.zip'; Expand-Archive -Force '%TMPZ%\main.zip' '%TMPZ%'" || goto erro
taskkill /f /im pythonw.exe >nul 2>nul
robocopy "%TMPZ%\contas-adm-app-main\local-ai" "%~dp0." /E /XD venv dados /XF config.toml /NFL /NDL /NJH /NJS >nul
set PY=venv\Scripts\python.exe
%PY% -m pip install -r requirements.txt || goto erro
echo -- modelos novos (so o que faltar) --
%PY% baixar_modelos.py
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0server.py"
echo.
echo Pronto: miau-ia atualizado e aberto de novo.
pause
exit /b 0
:erro
echo.
echo Deu erro. Tire um print desta janela e mande para o Claude.
pause
exit /b 1
