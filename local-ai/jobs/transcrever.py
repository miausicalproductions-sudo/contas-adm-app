"""Transcrição de áudio com faster-whisper (medium, int8_float16 na placa; sem placa, int8 no processador).

Lê .ogg/.opus (WhatsApp, Telegram), .m4a, .mp3, .wav e .webm (gravado no painel): o faster-whisper usa o
PyAV, que já traz o decodificador (não precisa instalar o ffmpeg).
"""
PESO_GB = 2.5
MODELO = "medium"


def carregar(cfg):
    if cfg.simular:
        return "simulado"
    # o CTranslate2 (motor do faster-whisper) precisa do cuBLAS 12 e do cuDNN 9: usa os que vêm com o PyTorch
    from jobs.recorte import _dlls_do_torch
    _dlls_do_torch()
    from faster_whisper import WhisperModel
    nome = getattr(cfg, "whisper_modelo", MODELO)
    try:
        return {"m": WhisperModel(nome, device="cuda", compute_type="int8_float16"), "nome": nome, "dev": "cuda"}
    except Exception as e:
        print("Whisper na placa não carregou (%s); usando o processador" % e)
        return {"m": WhisperModel(nome, device="cpu", compute_type="int8"), "nome": nome, "dev": "cpu"}


def _rodar(m, caminho, idioma):
    segs, info = m.transcribe(caminho, language=idioma or None, vad_filter=True, beam_size=5)
    L = [{"ini": round(s.start, 1), "fim": round(s.end, 1), "texto": s.text.strip()} for s in segs]   # aqui é que a placa trabalha (gerador)
    return {"texto": " ".join(x["texto"] for x in L).strip(), "segmentos": L, "duracao": round(getattr(info, "duration", 0.0), 1),
            "idioma": getattr(info, "language", idioma) or ""}


def rodar(modelo, caminho, idioma="pt"):
    """idioma "pt" (ideias e Stories da equipe) ou None/"auto" (vídeos de outros perfis, inclusive em inglês)."""
    if modelo == "simulado":
        import os
        n = os.path.getsize(caminho)
        return {"texto": "Ideia gravada em áudio (transcrição simulada, %d bytes)." % n, "segmentos": [], "duracao": 0.0}
    idioma = None if idioma in (None, "", "auto") else idioma
    try:
        return _rodar(modelo["m"], caminho, idioma)
    except Exception as e:
        if modelo.get("dev") != "cuda":
            raise
        print("Whisper falhou na placa (%s); tentando no processador" % e)   # ex.: cudnn_ops64_9.dll não encontrado
        from faster_whisper import WhisperModel
        modelo["m"] = WhisperModel(modelo["nome"], device="cpu", compute_type="int8")
        modelo["dev"] = "cpu"
        return _rodar(modelo["m"], caminho, idioma)
