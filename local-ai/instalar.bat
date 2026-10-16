@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  Instalando a IA local da Studios Miau (miau-ia)
echo  Precisa de internet e uns 15 GB livres. Demora de 10 a 30 min.
echo ============================================================
where py >nul 2>nul
if errorlevel 1 (
  echo Falta o Python. Instale o Python 3.12 em https://www.python.org/downloads/
  echo marcando "Add python.exe to PATH" e rode este arquivo de novo.
  pause
  exit /b 1
)
if not exist venv (
  py -3.12 -m venv venv 2>nul || py -3.11 -m venv venv
)
if not exist venv\Scripts\python.exe (
  echo Nao consegui criar o ambiente do Python 3.12 ou 3.11.
  pause
  exit /b 1
)
set PY=venv\Scripts\python.exe
%PY% -m pip install --upgrade pip
echo.
echo -- PyTorch com CUDA 12.8 (RTX 4060 Ti e RTX 5060) --
%PY% -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 || goto erro
%PY% -m pip install -r requirements.txt || goto erro
%PY% criar_config.py || goto erro
echo.
echo -- Baixando os modelos (uns 8 GB na primeira vez) --
%PY% baixar_modelos.py
echo.
echo -- Abrir o miau-ia junto com o Windows (escondido) --
set VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\miau-ia.vbs
> "%VBS%" echo CreateObject("WScript.Shell").Run """%~dp0venv\Scripts\pythonw.exe"" ""%~dp0server.py""", 0, False
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0server.py"
echo.
echo ============================================================
echo  Pronto! O miau-ia esta rodando e abre sozinho com o Windows.
echo  No painel: Config, "IA local e Claude API":
echo    Endereco: http://127.0.0.1:8765
%PY% -c "import tomllib;print('   Codigo do PC:', tomllib.load(open('config.toml','rb'))['servico']['token'])"
echo  So no PC 1: abra o config.toml no Bloco de Notas e cole a chave
echo  da API do Claude em [claude] chave = "...". Depois reinicie o PC
echo  (ou rode o iniciar.bat).
echo ============================================================
pause
exit /b 0
:erro
echo.
echo Deu erro na instalacao. Tire um print desta janela e mande para o Claude.
pause
exit /b 1
