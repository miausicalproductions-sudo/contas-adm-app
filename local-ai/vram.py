"""Gerente da memória da placa de vídeo (8 GB).

Cada modelo tem um peso aproximado em GB. Antes de carregar um, o gerente descarrega
os que foram usados há mais tempo até caber no limite (vram_gb do config). Um vigia
descarrega tudo o que ficou parado mais que descarregar_apos_s, para a placa ficar livre
para outros programas (jogos, Premiere, ComfyUI...).
Use sempre dentro de `with gerente.uso(nome, peso, carregar) as modelo:` — o uso segura a trava,
então o vigia nunca tira um modelo da memória no meio de uma tarefa.
"""
import gc
import threading
import time
from contextlib import contextmanager


def _torch():
    try:
        import torch  # noqa
        return torch
    except Exception:
        return None


def info():
    """Status da placa sem abrir o CUDA (assim o miau-ia parado não ocupa memória da placa)."""
    try:
        import subprocess
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.free,memory.total", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0 and r.stdout.strip():
            nome, livre, total = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
            return {"gpu": nome, "vram_livre_gb": round(float(livre) / 1024, 1), "vram_total_gb": round(float(total) / 1024, 1)}
    except Exception:
        pass
    import sys
    if "torch" not in sys.modules:   # sem nvidia-smi: não abre o CUDA só para olhar
        return {"gpu": "NVIDIA (detalhes ao usar)"}
    t = _torch()
    if not t or not t.cuda.is_available():
        return {"gpu": None}
    livre, total = t.cuda.mem_get_info()
    return {"gpu": t.cuda.get_device_name(0), "vram_livre_gb": round(livre / 2**30, 1), "vram_total_gb": round(total / 2**30, 1)}


class Gerente:
    def __init__(self, limite_gb=7.0, ocioso_s=90):
        self.limite = limite_gb
        self.ocioso = ocioso_s
        self.trava = threading.RLock()
        self.mods = {}  # nome -> {"obj", "peso", "ult"}
        threading.Thread(target=self._vigia, daemon=True).start()

    def carregados(self):
        return sorted(self.mods)

    @contextmanager
    def uso(self, nome, peso, carregar):
        with self.trava:
            if nome not in self.mods:
                self._abrir_espaco(peso)
                self.mods[nome] = {"obj": carregar(), "peso": peso, "ult": time.time()}
            m = self.mods[nome]
            try:
                yield m["obj"]
            finally:
                m["ult"] = time.time()

    def _abrir_espaco(self, peso):
        while self.mods and sum(m["peso"] for m in self.mods.values()) + peso > self.limite:
            velho = min(self.mods, key=lambda k: self.mods[k]["ult"])
            self._tirar(velho)

    def _tirar(self, nome):
        self.mods.pop(nome, None)
        gc.collect()
        t = _torch()
        if t and t.cuda.is_available():
            t.cuda.empty_cache()

    def liberar_tudo(self):
        with self.trava:
            for n in list(self.mods):
                self._tirar(n)

    def _vigia(self):
        while True:
            time.sleep(10)
            with self.trava:
                agora = time.time()
                for n in [k for k, m in self.mods.items() if agora - m["ult"] > self.ocioso]:
                    self._tirar(n)
