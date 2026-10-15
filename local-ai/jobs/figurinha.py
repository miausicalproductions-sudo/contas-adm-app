"""Figurinhas: SDXL Lightning (4 passos) em fp16, com descarga para a RAM para caber em 8 GB.

Depois de gerar, cada imagem passa pelo recorte (jobs/recorte.py) e volta sem fundo e aparada.
"""
PESO_GB = 5.5
BASE = "stabilityai/stable-diffusion-xl-base-1.0"
LIGHTNING = ("ByteDance/SDXL-Lightning", "sdxl_lightning_4step_unet.safetensors")
VAE = "madebyollin/sdxl-vae-fp16-fix"
# estilos: figurinha (adesivo recortado), elemento (ícone/forma que o editor não desenha, recortado),
# textura (fundo/padrão que preenche a caixa inteira, sem recorte)
ESTILOS = {
    "figurinha": ("{p}, cute die-cut sticker, flat vector illustration, bold clean outlines, simple shapes, "
                  "vibrant colors, centered, full body inside the frame, isolated on plain white background, "
                  "no text, no letters, no watermark"),
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


def rodar(pipe, prompt, n=2, semente=None, lado=1024, estilo="figurinha"):
    from jobs.recorte import simular_figurinha
    n = max(1, min(4, int(n or 2)))
    if pipe == "simulado":
        return [simular_figurinha(prompt, i) for i in range(n)]
    modelo = ESTILOS.get(estilo, ESTILO)
    import random
    import torch
    base = int(semente) if semente is not None else random.randint(0, 2**31 - 1)
    out = []
    for i in range(n):
        g = torch.Generator("cpu").manual_seed(base + i)
        img = pipe(prompt=modelo.format(p=prompt), num_inference_steps=4, guidance_scale=0,
                   width=lado, height=lado, generator=g).images[0]
        out.append(img.convert("RGBA"))
    return out
