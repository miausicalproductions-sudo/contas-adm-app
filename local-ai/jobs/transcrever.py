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


def audio(caminho):
    """Só o áudio (16 kHz, mono, numpy) de um vídeo ou áudio. Devolve (amostras, segundos) ou (None, motivo)."""
    try:
        import av
        with av.open(caminho) as c:
            if not c.streams.audio:
                return None, "o vídeo não tem faixa de áudio"
    except Exception as e:
        return None, "não abriu o arquivo (%s)" % e
    from faster_whisper import decode_audio
    try:
        a = decode_audio(caminho, sampling_rate=16000)
    except Exception as e:
        return None, "não consegui ler o áudio (%s)" % e
    if a is None or len(a) < 1600:
        return None, "faixa de áudio vazia"
    return a, len(a) / 16000.0


def _rodar(m, caminho, idioma):
    som, info_a = audio(caminho)
    if som is None:
        return {"texto": "", "segmentos": [], "duracao": 0.0, "idioma": "", "diag": str(info_a)}
    diag, L, txt, info = [], [], "", None
    for vad in (True, False):   # o filtro de voz às vezes corta fala por cima de música: sem nada, tenta sem ele
        segs, info = m.transcribe(som, language=idioma or None, vad_filter=vad, beam_size=5)
        L = [{"ini": round(s.start, 1), "fim": round(s.end, 1), "texto": s.text.strip()} for s in segs]   # aqui é que a placa trabalha
        txt = " ".join(x["texto"] for x in L).strip()
        diag.append("%s: %d trechos" % ("com filtro de voz" if vad else "sem filtro", len(L)))
        if txt:
            break
    lang = getattr(info, "language", idioma) or ""
    return {"texto": txt, "segmentos": L, "duracao": round(float(info_a), 1), "idioma": lang,
            "diag": "áudio de %.0f s · idioma %s · %s" % (float(info_a), lang or "?", " / ".join(diag))}


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
