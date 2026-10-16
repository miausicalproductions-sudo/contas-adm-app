"""Processo separado que roda as IAs da placa de vídeo.

O servidor (server.py) é leve e fica sempre ligado; as IAs pesadas (PyTorch, SDXL, Whisper, Florence)
moram neste processo. Desligar a IA local = encerrar este processo: toda a RAM e a placa voltam na hora.
Ele liga sozinho no primeiro pedido e desliga sozinho depois de um tempo parado (desligar_apos_s).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def principal(conn, cfg):
    if sys.stderr is None or sys.stdout is None:
        sys.stdout = sys.stderr = open(os.path.join(cfg.pasta_dados, "miau-ia-trabalhador.log"), "a", encoding="utf-8", buffering=1)
    import vram
    from jobs import aparar
    from jobs import descrever as J_VER
    from jobs import figurinha as J_FIG
    from jobs import midia as J_MID
    from jobs import recorte as J_REC
    from jobs import transcrever as J_VOZ
    g = vram.Gerente(cfg.vram_gb, cfg.descarregar_apos_s)

    def recortar(img):
        with g.uso("recorte", J_REC.PESO_GB, lambda: J_REC.carregar(cfg)) as s:
            return J_REC.rodar(s, img)

    def figurinhas(prompt, n, semente, estilo, refs=None, forca="medio"):
        with g.uso("figurinha", J_FIG.PESO_GB, lambda: J_FIG.carregar(cfg)) as p:
            brutas = J_FIG.rodar(p, prompt, n, semente, estilo=estilo, refs=refs, forca=forca)
        if not J_FIG.RECORTA.get(estilo, True):
            return brutas
        return [aparar(recortar(b)) for b in brutas]

    def transcrever(caminho):
        with g.uso("transcrever", J_VOZ.PESO_GB, lambda: J_VOZ.carregar(cfg)) as w:
            return J_VOZ.rodar(w, caminho)

    def ver(imgs):
        with g.uso("descrever", J_VER.PESO_GB, lambda: J_VER.carregar(cfg)) as mp:
            return J_VER.rodar(mp, imgs)

    def quadros(caminho, n):
        return J_MID.quadros(caminho, n, cfg.simular)

    F = {"recortar": recortar, "figurinhas": figurinhas, "transcrever": transcrever, "ver": ver, "quadros": quadros,
         "liberar": lambda: g.liberar_tudo(), "ping": lambda: "ok"}
    while True:
        try:
            nome, args = conn.recv()
        except (EOFError, OSError):
            break
        if nome == "sair":
            break
        t0 = time.time()
        try:
            res = F[nome](*args)
            conn.send(("ok", res, g.carregados()))
        except Exception as e:
            import traceback
            traceback.print_exc()
            conn.send(("erro", "%s: %s" % (type(e).__name__, str(e)[:400]), g.carregados()))
        sys.stderr.write("%s %s (%.1f s)\n" % (time.strftime("%H:%M:%S"), nome, time.time() - t0))
