"""Leitura de imagem local: Florence-2-large (descrição detalhada + texto escrito na imagem), fp16, ~1,8 GB.

Para vídeo, jobs/midia.py tira 3 quadros (e o áudio vai para a transcrição).
Se o Florence não carregar nesta máquina, o servidor usa o Claude rápido (Haiku) com as mesmas imagens.
"""
PESO_GB = 1.8
MODELO = "microsoft/Florence-2-large"


def carregar(cfg):
    if cfg.simular:
        return "simulado"
    from unittest.mock import patch

    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor
    from transformers.dynamic_module_utils import get_imports

    def sem_flash(arq):  # o código do Florence pede flash_attn, que não existe no Windows; não é necessário
        return [i for i in get_imports(arq) if i != "flash_attn"]

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tipo = torch.float16 if dev == "cuda" else torch.float32
    with patch("transformers.dynamic_module_utils.get_imports", sem_flash):
        modelo = AutoModelForCausalLM.from_pretrained(MODELO, trust_remote_code=True, torch_dtype=tipo, attn_implementation="eager").to(dev).eval()
    proc = AutoProcessor.from_pretrained(MODELO, trust_remote_code=True)
    return {"m": modelo, "p": proc, "dev": dev, "tipo": tipo}


def _tarefa(mp, img, tarefa):
    import torch
    ent = mp["p"](text=tarefa, images=img, return_tensors="pt").to(mp["dev"], mp["tipo"])
    with torch.inference_mode():
        ids = mp["m"].generate(input_ids=ent["input_ids"], pixel_values=ent["pixel_values"], max_new_tokens=256, num_beams=3, do_sample=False)
    txt = mp["p"].batch_decode(ids, skip_special_tokens=False)[0]
    return str(mp["p"].post_process_generation(txt, task=tarefa, image_size=img.size).get(tarefa, "")).strip()


def rodar(mp, imagens):
    """imagens: lista de PIL.Image -> [{"cena": descrição em inglês, "texto": texto lido na imagem}]"""
    if mp == "simulado":
        return [{"cena": "a dog in a bathtub with foam (simulated %d)" % (i + 1), "texto": "PROMO HOJE" if i == 0 else ""} for i in range(len(imagens))]
    out = []
    for img in imagens:
        img = img.convert("RGB")
        out.append({"cena": _tarefa(mp, img, "<MORE_DETAILED_CAPTION>"), "texto": _tarefa(mp, img, "<OCR>")})
    return out
