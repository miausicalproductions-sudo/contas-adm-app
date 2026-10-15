"""miau-ia: o programa da IA local da Studios Miau (roda no PC 1 e, se quiser, no PC 2).

O painel chama http://127.0.0.1:8765 com o código do PC (X-Miau-Token). Não precisa de nada
além do Python para o servidor (usa o servidor HTTP que já vem nele); as IAs (rembg, SDXL, Claude)
são carregadas só quando usadas.

Rotas:
  GET  /health            status: placa, modelos na memória, PC 2, Claude e gasto
  POST /recorte           {imagem}                 -> {imagem} PNG sem fundo
  POST /figurinha         {prompt, n}              -> {imagens:[PNG sem fundo], onde}
  POST /claude/dia        {empresa, sistema, empresa_md, pedido, schema}        -> {dados, uso}
  POST /claude/layouts    idem (schema dos modelos)                              -> {dados, uso}
  POST /claude/modelo     idem + imagens (arte de referência)                    -> {dados, uso}
  POST /claude/chat       {empresa, empresa_md, mensagem}                        -> {texto, uso}
  GET  /claude/uso        gasto do mês por empresa
"""
import hmac
import json
import os
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vram  # noqa: E402
from claude_api import ClaudeAPIManager, ErroClaude, LimiteAtingido  # noqa: E402
from config import carregar  # noqa: E402
from jobs import aparar, de_dataurl, para_dataurl  # noqa: E402
from jobs import figurinha as J_FIG  # noqa: E402
from jobs import recorte as J_REC  # noqa: E402

VERSAO = "1.0"
MAX_CORPO = 30 * 2**20


class Servico:
    def __init__(self, cfg, cliente_claude=None):
        self.cfg = cfg
        self.gpu = vram.Gerente(cfg.vram_gb, cfg.descarregar_apos_s)
        self.claude = ClaudeAPIManager(cfg, cliente_claude)
        self.fila = 0
        self.trava_fila = threading.Lock()
        self._pc2 = {"t": 0, "ok": False, "ms": None}

    # ---------- PC 2 ----------
    def pc2_online(self):
        if not self.cfg.pc2:
            return False
        if time.time() - self._pc2["t"] < 10:
            return self._pc2["ok"]
        t0 = time.time()
        ok = False
        try:
            with urllib.request.urlopen(self.cfg.pc2.rstrip("/") + "/health", timeout=0.4) as r:
                ok = json.load(r).get("servico") == "miau-ia"
        except Exception:
            ok = False
        self._pc2 = {"t": time.time(), "ok": ok, "ms": round((time.time() - t0) * 1000) if ok else None}
        return ok

    def no_pc2(self, rota, corpo, timeout=300):
        req = urllib.request.Request(self.cfg.pc2.rstrip("/") + rota, data=json.dumps(corpo).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-Miau-Token": self.cfg.pc2_token or ""})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)

    # ---------- tarefas ----------
    def _gpu(self, f):
        with self.trava_fila:
            self.fila += 1
        try:
            return f()
        finally:
            with self.trava_fila:
                self.fila -= 1

    def recortar(self, img):
        def f():
            with self.gpu.uso("recorte", J_REC.PESO_GB, lambda: J_REC.carregar(self.cfg)) as s:
                return J_REC.rodar(s, img)
        return self._gpu(f)

    def figurinhas(self, prompt, n, semente=None):
        def f():
            with self.gpu.uso("figurinha", J_FIG.PESO_GB, lambda: J_FIG.carregar(self.cfg)) as p:
                brutas = J_FIG.rodar(p, prompt, n, semente)
            with self.gpu.uso("recorte", J_REC.PESO_GB, lambda: J_REC.carregar(self.cfg)) as s:
                return [aparar(J_REC.rodar(s, b)) for b in brutas]
        return self._gpu(f)

    def health(self, completo):
        d = {"ok": True, "servico": "miau-ia", "versao": VERSAO, "papel": self.cfg.papel}
        if not completo:
            return d
        d.update(vram.info())
        d["simulado"] = self.cfg.simular
        d["modelos_na_memoria"] = self.gpu.carregados()
        d["fila"] = self.fila
        d["pc2"] = {"endereco": self.cfg.pc2, "online": self.pc2_online(), "ms": self._pc2["ms"]} if self.cfg.pc2 else None
        d["claude"] = {"configurada": self.claude.configurada, "modelo": self.cfg.modelo,
                       "modelo_rapido": self.cfg.modelo_rapido, "cache": self.cfg.cache_ttl, **self.claude.resumo()}
        d["claude"].pop("empresas", None)
        return d


def criar_handler(sv):
    cfg = sv.cfg

    class H(BaseHTTPRequestHandler):
        server_version = "miau-ia/" + VERSAO

        def log_message(self, fmt, *a):
            sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % a))

        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Miau-Token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Max-Age", "600")

        def _json(self, cod, obj):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(cod)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _autorizado(self):
            if not cfg.token:
                return self.client_address[0] in ("127.0.0.1", "::1")
            return hmac.compare_digest(self.headers.get("X-Miau-Token", ""), cfg.token)

        def _corpo(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_CORPO:
                raise ValueError("pedido grande demais")
            return json.loads(self.rfile.read(n) or b"{}")

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            if self.path.split("?")[0] == "/health":
                return self._json(200, sv.health(self._autorizado()))
            if not self._autorizado():
                return self._json(401, {"erro": "código do PC errado (Config → IA local no painel)"})
            if self.path == "/claude/uso":
                return self._json(200, sv.claude.resumo())
            self._json(404, {"erro": "rota não existe"})

        def do_POST(self):
            if not self._autorizado():
                return self._json(401, {"erro": "código do PC errado (Config → IA local no painel)"})
            try:
                b = self._corpo()
                rota = self.path.split("?")[0]
                if rota == "/recorte":
                    img = de_dataurl(b.get("imagem"))
                    return self._json(200, {"imagem": para_dataurl(sv.recortar(img)), "onde": cfg.papel})
                if rota == "/figurinha":
                    n = max(1, min(4, int(b.get("n") or 2)))
                    prompt = str(b.get("prompt") or "").strip()[:300]
                    if not prompt:
                        return self._json(400, {"erro": "falta a descrição da figurinha"})
                    if b.get("traduzir", True):
                        prompt = sv.claude.prompt_figurinha(prompt)
                    if cfg.pc2 and not b.get("_local") and sv.pc2_online():
                        try:
                            r = sv.no_pc2("/figurinha", {"prompt": prompt, "n": n, "traduzir": False, "_local": True})
                            r["onde"] = "pc2"
                            return self._json(200, r)
                        except Exception as e:
                            sys.stderr.write("PC 2 falhou, fazendo no PC 1: %s\n" % e)
                    imgs = sv.figurinhas(prompt, n, b.get("semente"))
                    return self._json(200, {"imagens": [para_dataurl(i) for i in imgs], "prompt": prompt, "onde": cfg.papel})
                if rota in ("/claude/dia", "/claude/layouts", "/claude/modelo"):
                    tarefa = rota.rsplit("/", 1)[1]
                    nome, desc = {
                        "dia": ("montar_telas", "Entrega as telas do dia (texto de cada tela, modelo e legenda) para o painel montar."),
                        "layouts": ("criar_modelo", "Entrega os modelos de layout (camadas) que o painel desenha."),
                        "modelo": ("criar_modelo", "Entrega o modelo de layout (camadas) que recria a arte de referência."),
                    }[tarefa]
                    dados, uso = sv.claude.ferramenta(tarefa, b.get("empresa"), b.get("sistema"), b.get("empresa_md"),
                                                      b.get("pedido"), nome, desc, b.get("schema"), b.get("imagens"))
                    return self._json(200, {"dados": dados, "uso": uso})
                if rota == "/claude/chat":
                    txt, uso = sv.claude.texto("chat", b.get("empresa"), b.get("sistema"), b.get("empresa_md"), b.get("mensagem"))
                    return self._json(200, {"texto": txt, "uso": uso})
                return self._json(404, {"erro": "rota não existe"})
            except LimiteAtingido as e:
                return self._json(402, {"erro": str(e), "teto": True})
            except (ErroClaude, ValueError) as e:
                return self._json(400, {"erro": str(e)})
            except Exception as e:
                traceback.print_exc()
                nome = type(e).__name__
                msg = str(e)
                if "RateLimit" in nome or "Overloaded" in nome or "529" in msg:
                    return self._json(503, {"erro": "O Claude está ocupado agora; tente de novo em 1 minuto."})
                if "Authentication" in nome:
                    return self._json(401, {"erro": "A chave da API no config.toml foi recusada pela Anthropic."})
                return self._json(500, {"erro": "%s: %s" % (nome, msg[:300])})

    return H


def main():
    cfg = carregar()
    if sys.stdout is None or sys.stderr is None:  # aberto escondido (pythonw): mensagens vão para dados/miau-ia.log
        sys.stdout = sys.stderr = open(os.path.join(cfg.pasta_dados, "miau-ia.log"), "a", encoding="utf-8", buffering=1)
    if cfg.escutar not in ("127.0.0.1", "localhost") and not cfg.token:
        sys.exit("Para escutar na rede (%s) é obrigatório ter token no config.toml." % cfg.escutar)
    sv = Servico(cfg)
    srv = ThreadingHTTPServer((cfg.escutar, cfg.porta), criar_handler(sv))
    print("miau-ia %s em http://%s:%d (%s%s)%s" % (VERSAO, cfg.escutar, cfg.porta, cfg.papel.upper(),
          ", SIMULADO" if cfg.simular else "", " · Claude: " + cfg.modelo if sv.claude.configurada else " · Claude: sem chave"))
    print(vram.info())
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
