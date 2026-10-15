"""Baixa os modelos uma vez (uns 8 GB), para a primeira figurinha não demorar. Rode pelo instalar.bat."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import carregar  # noqa: E402
from jobs import figurinha, recorte  # noqa: E402

cfg = carregar()
if cfg.simular:
    sys.exit("Modo simulado: nada para baixar.")
print("1/2 recorte de fundo (%s)..." % cfg.recorte_modelo)
recorte.carregar(cfg)
print("2/2 figurinhas (SDXL Lightning, a parte maior)...")
figurinha.carregar(cfg)
print("Pronto: modelos baixados.")
