"""Configuração do miau-ia: lê config.toml (ao lado deste arquivo) e completa com os padrões."""
import os
import tomllib
from dataclasses import dataclass, field

PASTA = os.path.dirname(os.path.abspath(__file__))


@dataclass
class Config:
    # [servico]
    escutar: str = "127.0.0.1"      # PC 1: só o próprio computador · PC 2: "0.0.0.0" (rede local)
    porta: int = 8765
    token: str = ""                 # código que o painel manda em X-Miau-Token
    pc2: str = ""                   # endereço do PC 2 (ex.: http://192.168.0.20:8765); vazio no próprio PC 2
    pc2_token: str = ""
    # [claude]
    chave: str = ""                 # chave da API da Anthropic: SÓ no PC 1, nunca no GitHub nem no painel
    modelo: str = "claude-sonnet-5-5"
    modelo_rapido: str = "claude-haiku-5-5"
    teto_mensal_usd: float = 20.0
    cache_ttl: str = "5m"           # "5m" ou "1h"
    precos: dict = field(default_factory=lambda: {
        # US$ por milhão de tokens (entrada, saída). Confira em https://www.anthropic.com/pricing e ajuste.
        "claude-sonnet-5-5": [3.0, 15.0],
        "claude-haiku-5-5": [1.0, 5.0],
    })
    # [gpu]
    simular: bool = False           # testes sem placa de vídeo: devolve imagens de mentira
    vram_gb: float = 7.0            # quanto a IA local pode ocupar (a placa tem 8 GB)
    descarregar_apos_s: int = 90        # tira o modelo da placa depois de parado
    desligar_apos_s: int = 600          # desliga a IA local inteira (libera a RAM) depois de 10 min parada
    recorte_modelo: str = "birefnet-general"
    figurinha_modelo: str = "sdxl-lightning"
    whisper_modelo: str = "medium"      # "small" (mais leve) ou "large-v3" (mais preciso)
    descrever: str = "local"            # leitura dos Stories: "local" (Florence-2 na placa) ou "claude" (Haiku, centavos)
    pasta_dados: str = os.path.join(PASTA, "dados")

    @property
    def papel(self):
        return "pc2" if self.escutar not in ("127.0.0.1", "localhost") and not self.pc2 else "pc1"


def carregar(caminho=None):
    caminho = caminho or os.environ.get("MIAU_CONFIG") or os.path.join(PASTA, "config.toml")
    c = Config()
    if os.path.exists(caminho):
        with open(caminho, "rb") as f:
            d = tomllib.load(f)
        for sec in ("servico", "claude", "gpu"):
            for k, v in (d.get(sec) or {}).items():
                if k == "precos" and isinstance(v, dict):
                    c.precos.update({m: list(p) for m, p in v.items()})
                elif hasattr(c, k):
                    setattr(c, k, v)
    if os.environ.get("MIAU_SIMULAR") == "1":
        c.simular = True
    if not os.path.isabs(c.pasta_dados):
        c.pasta_dados = os.path.join(PASTA, c.pasta_dados)
    os.makedirs(c.pasta_dados, exist_ok=True)
    return c
