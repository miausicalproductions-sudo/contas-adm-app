"""Baixa e testa os modelos da IA local (uma vez; depois ficam no cache do computador).

    python baixar_modelos.py            tudo (recorte, figurinhas, transcrição)
    python baixar_modelos.py imagens    só o gerador de figurinhas + o recorte de fundo
    python baixar_modelos.py voz        só a transcrição de áudio
    python baixar_modelos.py leitura    só a leitura de imagem (Florence-2, Stories do celular)
    python baixar_modelos.py imagens --testar   baixa e gera uma figurinha de teste em dados/
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import carregar  # noqa: E402
from jobs import aparar  # noqa: E402
from jobs import descrever, figurinha, recorte, transcrever  # noqa: E402

cfg = carregar()
arg = [a for a in sys.argv[1:] if not a.startswith("-")]
quais = arg[0] if arg else "tudo"
testar = "--testar" in sys.argv
if cfg.simular:
    sys.exit("Modo simulado ligado no config.toml: nada para baixar.")


def placa():
    try:
        import torch
        if torch.cuda.is_available():
            livre, total = torch.cuda.mem_get_info()
            return "%s (%.1f de %.1f GB livres)" % (torch.cuda.get_device_name(0), livre / 2**30, total / 2**30)
        return "NENHUMA placa NVIDIA encontrada pelo PyTorch (confira o driver)"
    except Exception as e:
        return "PyTorch não carregou: %s" % e


print("Placa de vídeo:", placa())
if quais in ("tudo", "imagens"):
    print("\n[1] Recorte de fundo (%s)..." % cfg.recorte_modelo)
    s = recorte.carregar(cfg)
    print("    ok")
    print("[2] Gerador de figurinhas: SDXL Lightning 4 passos, fp16 (uns 7 GB na primeira vez)...")
    t0 = time.time()
    p = figurinha.carregar(cfg)
    print("    ok (%.0f s)" % (time.time() - t0))
    if testar:
        print("[3] Teste: gerando uma figurinha...")
        t0 = time.time()
        img = figurinha.rodar(p, "cute orange cat sleeping", n=1)[0]
        t1 = time.time()
        img = aparar(recorte.rodar(s, img))
        caminho = os.path.join(cfg.pasta_dados, "teste_figurinha.png")
        img.save(caminho)
        print("    pronto: gerou em %.1f s e recortou em %.1f s -> %s" % (t1 - t0, time.time() - t1, caminho))
        print("    Placa agora:", placa())
if quais in ("tudo", "voz"):
    print("\n[4] Transcrição de áudio (faster-whisper %s)..." % cfg.whisper_modelo)
    transcrever.carregar(cfg)
    print("    ok")
if quais in ("tudo", "leitura") and cfg.descrever != "claude":
    print("\n[5] Leitura de imagem (Florence-2-large, ~1,6 GB)...")
    try:
        descrever.carregar(cfg)
        print("    ok")
    except Exception as e:
        print("    não carregou (%s). Os Stories do celular serão lidos pelo Claude rápido (centavos)." % e)
print("\nPronto: modelos baixados.")
