"""Transcrição de áudio com faster-whisper (medium, int8_float16 na placa; sem placa, int8 no processador).

Lê .ogg/.opus (WhatsApp, Telegram), .m4a, .mp3, .wav e .webm (gravado no painel): o faster-whisper usa o
PyAV, que já traz o decodificador (não precisa instalar o ffmpeg).
"""
PESO_GB = 2.5
MODELO = "medium"


def carregar(cfg):
    if cfg.simular:
        return "simulado"
    from faster_whisper import WhisperModel
    try:
        return WhisperModel(getattr(cfg, "whisper_modelo", MODELO), device="cuda", compute_type="int8_float16")
    except Exception:
        return WhisperModel(getattr(cfg, "whisper_modelo", MODELO), device="cpu", compute_type="int8")


def rodar(modelo, caminho, idioma="pt"):
    if modelo == "simulado":
        import os
        n = os.path.getsize(caminho)
        return {"texto": "Ideia gravada em áudio (transcrição simulada, %d bytes)." % n, "segmentos": [], "duracao": 0.0}
    segs, info = modelo.transcribe(caminho, language=idioma or None, vad_filter=True, beam_size=5)
    L = [{"ini": round(s.start, 1), "fim": round(s.end, 1), "texto": s.text.strip()} for s in segs]
    return {"texto": " ".join(x["texto"] for x in L).strip(), "segmentos": L, "duracao": round(getattr(info, "duration", 0.0), 1)}
