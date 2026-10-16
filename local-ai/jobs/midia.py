"""Quadros de um vídeo (PyAV, que já vem com o faster-whisper; não precisa de ffmpeg)."""
from PIL import Image


def quadros(caminho, n=3, simular=False):
    if simular:
        return [Image.new("RGB", (360, 640), (120 + 40 * i, 90, 60)) for i in range(n)]
    import av
    with av.open(caminho) as c:
        v = c.streams.video[0]
        dur = float(v.duration * v.time_base) if v.duration else (c.duration / 1e6 if c.duration else 0)
        out = []
        for k in range(n):
            alvo = dur * (k + 1) / (n + 1) if dur else 0
            try:
                c.seek(int(alvo / v.time_base), stream=v, any_frame=False, backward=True)
            except Exception:
                pass
            for q in c.decode(v):
                if q.time is None or q.time >= alvo - 0.05:
                    img = q.to_image()
                    img.thumbnail((768, 768))
                    out.append(img)
                    break
        return out


def cenas(caminho, passo=3.0, maximo=24, simular=False):
    """Um quadro a cada `passo` segundos e também quando a cena muda (corte). Devolve [(imagem, segundo)]."""
    if simular:
        return [(Image.new("RGB", (360, 640), (120 + 30 * i, 90, 60)), round(i * passo, 1)) for i in range(4)]
    import av
    import numpy as np
    out, ult, t_ult, prox = [], None, -1e9, 0.0
    with av.open(caminho) as c:
        v = c.streams.video[0]
        v.thread_type = "AUTO"
        for q in c.decode(v):
            t = float(q.time or 0.0)
            if t < prox:
                continue
            prox = t + 0.5                                   # olha 2 quadros por segundo
            img = q.to_image()
            mini = np.asarray(img.convert("L").resize((32, 56)), dtype=np.float32)
            corte = ult is not None and float(np.abs(mini - ult).mean()) > 28 and t - t_ult >= 0.8
            if ult is None or t - t_ult >= passo or corte:
                img.thumbnail((768, 768))
                out.append((img, round(t, 1)))
                ult, t_ult = mini, t
                if len(out) >= maximo:
                    break
    return out
