@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  Gerador de figurinhas da IA local (SDXL Lightning + recorte)
echo  Usa o Python e o PyTorch que o instalar.bat ja colocou aqui:
echo  NAO baixa tudo de novo, so o que falta (uns 7 GB do modelo).
echo ============================================================
if not exist venv\Scripts\python.exe (
  echo Nao achei a instalacao do miau-ia nesta pasta. Rode o instalar.bat primeiro.
  pause
  exit /b 1
)
set PY=venv\Scripts\python.exe
%PY% -c "import torch;print('PyTorch',torch.__version__,'| placa:',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NENHUMA')" || goto erro
echo -- bibliotecas (so instala o que faltar) --
%PY% -m pip install "diffusers>=0.30" "transformers>=4.44" "accelerate>=0.33" "safetensors>=0.4" "huggingface_hub>=0.24" "rembg[gpu]>=2.0.57" || goto erro
echo.
echo -- baixando o modelo e testando (gera dados\teste_figurinha.png) --
%PY% baixar_modelos.py imagens --testar || goto erro
echo.
echo Pronto. Abra a pasta dados e veja o teste_figurinha.png.
echo Feche o miau-ia escondido (ou reinicie o PC) para ele usar o gerador.
start "" "%~dp0dados"
pause
exit /b 0
:erro
echo.
echo Deu erro. Tire um print desta janela e mande para o Claude.
pause
exit /b 1
