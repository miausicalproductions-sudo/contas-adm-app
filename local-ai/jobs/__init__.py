"""Tarefas de GPU do miau-ia. Cada uma tem carregar(cfg) -> modelo e rodar(modelo, ...)."""
import base64
import io
import re

from PIL import Image

MAX_LADO = 2048


def de_dataurl(s):
    """'data:image/png;base64,...' (ou só o base64) -> PIL.Image (RGBA), no máximo 2048 px."""
    s = str(s or "")
    m = re.match(r"^data:[\w/+.-]+;base64,", s)
    if m:
        s = s[m.end():]
    try:
        img = Image.open(io.BytesIO(base64.b64decode(s, validate=False)))
        img.load()
    except Exception as e:
        raise ValueError("imagem inválida") from e
    img = img.convert("RGBA")
    if max(img.size) > MAX_LADO:
        img.thumbnail((MAX_LADO, MAX_LADO))
    return img


def para_dataurl(img, fmt="PNG"):
    b = io.BytesIO()
    img.save(b, fmt, optimize=fmt == "PNG")
    return "data:image/%s;base64,%s" % (fmt.lower(), base64.b64encode(b.getvalue()).decode())


def aparar(img, folga=6):
    """Corta as bordas transparentes (figurinha justa na caixa)."""
    a = img.getchannel("A").point(lambda v: 255 if v > 16 else 0)
    bb = a.getbbox()
    if not bb:
        return img
    x0, y0, x1, y1 = bb
    return img.crop((max(0, x0 - folga), max(0, y0 - folga), min(img.width, x1 + folga), min(img.height, y1 + folga)))
