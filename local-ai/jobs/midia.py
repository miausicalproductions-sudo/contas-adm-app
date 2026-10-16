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
