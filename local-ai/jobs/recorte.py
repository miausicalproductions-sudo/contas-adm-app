"""Recorte de fundo com rembg (BiRefNet na placa de vídeo; sem placa, no processador)."""
from PIL import Image, ImageDraw

PESO_GB = 1.2


def carregar(cfg):
    if cfg.simular:
        return "simulado"
    try:  # onnxruntime-gpu acha as DLLs do CUDA que vêm com o PyTorch
        import onnxruntime as ort
        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls()
    except Exception:
        pass
    from rembg import new_session
    try:
        return new_session(cfg.recorte_modelo, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    except Exception:
        return new_session("isnet-general-use", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])


def rodar(sessao, img):
    if sessao == "simulado":
        return _simular(img)
    from rembg import remove
    return remove(img, session=sessao, post_process_mask=True).convert("RGBA")


def _simular(img):
    """Sem IA: tira o que for quase igual à cor dos cantos (só para testes)."""
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    cs = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    r, g, b = (sum(c[i] for c in cs) // 4 for i in range(3))
    out = Image.new("RGBA", img.size)
    po = out.load()
    for y in range(h):
        for x in range(w):
            p = px[x, y]
            po[x, y] = (p[0], p[1], p[2], 0 if abs(p[0] - r) + abs(p[1] - g) + abs(p[2] - b) < 60 else p[3])
    return out


def simular_figurinha(prompt, i=0):
    img = Image.new("RGBA", (512, 512), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    cor = [(240, 112, 33), (27, 163, 176), (14, 79, 100), (240, 180, 41)][i % 4]
    d.ellipse((96, 96, 416, 416), fill=cor)
    d.text((140, 240), (prompt or "")[:24], fill=(255, 255, 255))
    return img
