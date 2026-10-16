"""Figurinhas: SDXL Lightning (4 passos) em fp16, com descarga para a RAM para caber em 8 GB.

Depois de gerar, cada imagem passa pelo recorte (jobs/recorte.py) e volta sem fundo e aparada.
"""
PESO_GB = 6.5   # com o IP-Adapter (estilo das referências) carregado
IPA = ("h94/IP-Adapter", "sdxl_models", "ip-adapter-plus_sdxl_vit-h.safetensors")
IPA_ENC = ("h94/IP-Adapter", "models/image_encoder")
FORCA = {"leve": 0.5, "medio": 0.8, "forte": 1.0}
BASE = "stabilityai/stable-diffusion-xl-base-1.0"
LIGHTNING = ("ByteDance/SDXL-Lightning", "sdxl_lightning_4step_unet.safetensors")
VAE = "madebyollin/sdxl-vae-fp16-fix"
# estilos: figurinha (adesivo recortado), elemento (ícone/forma que o editor não desenha, recortado),
# textura (fundo/padrão que preenche a caixa inteira, sem recorte)
ESTILOS = {
    "figurinha": ("{p}, cute die-cut sticker, flat vector illustration, bold clean outlines, simple shapes, "
                  "vibrant colors, single subject only, centered, full body inside the frame, isolated on plain white background, "
                  "no frame, no border scene, no background objects, no text, no letters, no watermark"),
    "elemento": ("{p}, single flat graphic element, minimal vector icon, clean shape, solid colors, centered, "
                 "isolated on plain white background, no text, no letters, no watermark"),
    "textura": ("{p}, seamless background texture pattern, flat illustration, evenly distributed, soft colors, "
                "fills the whole frame, no text, no letters, no watermark"),
}
ESTILO = ESTILOS["figurinha"]
RECORTA = {"figurinha": True, "elemento": True, "textura": False}


def carregar(cfg):
    if cfg.simular:
        return "simulado"
    import torch
    from diffusers import AutoencoderKL, EulerDiscreteScheduler, StableDiffusionXLPipeline, UNet2DConditionModel
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file

    unet = UNet2DConditionModel.from_config(BASE, subfolder="unet").to(torch.float16)
    unet.load_state_dict(load_file(hf_hub_download(*LIGHTNING), device="cpu"))
    vae = AutoencoderKL.from_pretrained(VAE, torch_dtype=torch.float16)
    pipe = StableDiffusionXLPipeline.from_pretrained(BASE, unet=unet, vae=vae, torch_dtype=torch.float16, variant="fp16")
    pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config, timestep_spacing="trailing")
    pipe.enable_model_cpu_offload()  # só a parte que está trabalhando fica na placa
    return pipe


def _ipa(pipe):
    """Liga o IP-Adapter (só quando a empresa tem figurinhas de referência). Baixa ~3 GB na primeira vez."""
    if getattr(pipe, "_miau_ipa", None) is not None:
        return pipe._miau_ipa
    try:
        import torch
        from transformers import CLIPVisionModelWithProjection
        enc = CLIPVisionModelWithProjection.from_pretrained(IPA_ENC[0], subfolder=IPA_ENC[1], torch_dtype=torch.float16)
        pipe.register_modules(image_encoder=enc)
        pipe.load_ip_adapter(IPA[0], subfolder=IPA[1], weight_name=IPA[2], image_encoder_folder=None)
        pipe.enable_model_cpu_offload()
        pipe._miau_ipa = True
    except Exception as e:
        print("IP-Adapter não carregou (as figurinhas saem sem copiar o estilo):", e)
        pipe._miau_ipa = False
    return pipe._miau_ipa


def _quadrado(img, lado=512):
    """Referência sem fundo -> quadrado com fundo branco (o que o encoder de imagem espera)."""
    from PIL import Image
    img = img.convert("RGBA")
    img.thumbnail((lado, lado))
    q = Image.new("RGB", (lado, lado), (255, 255, 255))
    q.paste(img, ((lado - img.width) // 2, (lado - img.height) // 2), img)
    return q


def rodar(pipe, prompt, n=2, semente=None, lado=1024, estilo="figurinha", refs=None, forca="medio"):
    """refs = figurinhas aprovadas / artes da marca (PIL): as novas saem "na mesma mão" (só o ESTILO delas, o assunto vem do texto)."""
    from jobs.recorte import simular_figurinha
    n = max(1, min(4, int(n or 2)))
    if pipe == "simulado":
        return [simular_figurinha(prompt, i) for i in range(n)]
    modelo = ESTILOS.get(estilo, ESTILO)
    import random
    import torch
    base = int(semente) if semente is not None else random.randint(0, 2**31 - 1)
    extra = {}
    usa = bool(refs) and _ipa(pipe)
    if getattr(pipe, "_miau_ipa", None):
        if usa:
            f = FORCA.get(forca, 0.8) if not isinstance(forca, (int, float)) else float(forca)
            # InstantStyle: o adaptador só age nos blocos de estilo (cor, traço, textura), não copia o desenho
            pipe.set_ip_adapter_scale({"up": {"block_0": [0.0, f, 0.0]}})
            extra["ip_adapter_image"] = [[_quadrado(r) for r in refs[:3]]]
        else:
            from PIL import Image
            pipe.set_ip_adapter_scale(0.0)
            extra["ip_adapter_image"] = [[Image.new("RGB", (512, 512), (255, 255, 255))]]
    out = []
    for i in range(n):
        g = torch.Generator("cpu").manual_seed(base + i)
        try:
            img = pipe(prompt=modelo.format(p=prompt), num_inference_steps=4, guidance_scale=0,
                       width=lado, height=lado, generator=g, **extra).images[0]
        except Exception as e:
            if "ip_adapter_image" not in extra or len(extra["ip_adapter_image"][0]) == 1:
                raise
            print("várias referências juntas não rodaram; usando só a primeira:", e)
            extra["ip_adapter_image"] = [extra["ip_adapter_image"][0][:1]]
            img = pipe(prompt=modelo.format(p=prompt), num_inference_steps=4, guidance_scale=0,
                       width=lado, height=lado, generator=g, **extra).images[0]
        out.append(img.convert("RGBA"))
    return out
