"""miau-ia: o programa da IA local da Studios Miau (roda no PC 1 e, se quiser, no PC 2).

O painel chama http://127.0.0.1:8765 com o código do PC (X-Miau-Token). Não precisa de nada
além do Python para o servidor (usa o servidor HTTP que já vem nele); as IAs (rembg, SDXL, Claude)
são carregadas só quando usadas.

Rotas:
  GET  /health            status: placa, modelos na memória, PC 2, Claude e gasto
  POST /recorte           {imagem}                 -> {imagem} PNG sem fundo
  POST /figurinha         {prompt, n, estilo}      -> {imagens:[PNG], onde}  estilo: figurinha | elemento | textura
  POST /transcrever       {audio, nome}            -> {texto, segmentos, duracao}
  POST /descrever         {midia, tipo, nome}      -> {resumo, cenas, texto_tela, fala, via}  (Story do celular)
  POST /claude/classificar {empresa, texto}        -> {dados:{entrada, prio, tipo, dia, resumo}, uso}
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
from claude_api import ClaudeAPIManager, ErroClaude, LimiteAtingido, explicar  # noqa: E402
from config import carregar  # noqa: E402
from jobs import aparar, de_dataurl, para_dataurl  # noqa: E402
from jobs import figurinha as J_FIG  # noqa: E402
from jobs import recorte as J_REC  # noqa: E402
from jobs import transcrever as J_VOZ  # noqa: E402
from jobs import descrever as J_VER  # noqa: E402
from jobs import midia as J_MID  # noqa: E402
import trabalhador  # noqa: E402
import collections  # noqa: E402
import contextlib  # noqa: E402
import base64  # noqa: E402
import io  # noqa: E402
import re  # noqa: E402
import tempfile  # noqa: E402

VERSAO = "1.15"
SCHEMA_CLASSE = {"type": "object", "properties": {
    "entrada": {"type": "string", "enum": ["ideia", "diretriz", "contexto", "pedido"],
                "description": "ideia = ideia solta para o banco; diretriz = algo obrigatório num dia ou campanha; contexto = bastidor/informação; pedido = pedem um Story/post agora"},
    "prio": {"type": "string", "enum": ["alta", "banco"], "description": "alta = a equipe quer usar logo"},
    "tipo": {"type": "string", "enum": ["stories", "reels", "carrossel", "feed"]},
    "dia": {"type": "string", "description": "data AAAA-MM-DD se a fala citar um dia; senão vazio"},
    "resumo": {"type": "string", "description": "a ideia reescrita em até 2 frases, sem perder detalhes concretos"},
    "empresa": {"type": "string", "description": "nome da empresa citada, se houver"}}, "required": ["entrada", "prio", "tipo", "resumo"]}
MAX_CORPO = 30 * 2**20


NOMES_IA = {"recorte": ("✂️", "Recorte de fundo", "BiRefNet"), "figurinha": ("🎨", "Gerador de figurinhas", "SDXL Lightning"),
            "transcrever": ("🎙", "Transcrição de áudio", "faster-whisper"), "descrever": ("👁", "Leitura de imagem", "Florence-2")}


HOSTS_MIDIA = (".cdninstagram.com", ".fbcdn.net", ".fbsbx.com")


def baixar_midia(url, limite=100 * 2**20):
    """Vídeo/foto de um post do Instagram (link do CDN da Meta, que vem da Business Discovery) -> data URL."""
    import base64
    from urllib.parse import urlparse
    h = (urlparse(str(url)).hostname or "").lower()
    if not str(url).startswith("https://") or not any(h.endswith(x) for x in HOSTS_MIDIA):
        raise ValueError("só baixo mídia do Instagram (link do CDN da Meta)")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            tipo = (r.headers.get("Content-Type") or "video/mp4").split(";")[0]
            dados = r.read(limite + 1)
    except urllib.error.HTTPError as e:
        raise ValueError("o link do vídeo expirou ou foi recusado (%s): clique em ↻ para buscar de novo" % e.code)
    if len(dados) > limite:
        raise ValueError("vídeo grande demais (mais de 100 MB)")
    return "data:%s;base64,%s" % (tipo, base64.b64encode(dados).decode())


class Trabalhador:
    """Liga, usa e desliga o processo das IAs da placa (trabalhador.py)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.p = None
        self.conn = None
        self.trava = threading.Lock()
        self.ult = time.time()
        self.modelos = []
        self.ligado_em = None
        threading.Thread(target=self._vigia, daemon=True).start()

    def ligado(self):
        return self.p is not None and self.p.is_alive()

    def _ligar(self):
        if self.ligado():
            return
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        a, b = ctx.Pipe()
        self.p = ctx.Process(target=trabalhador.principal, args=(b, self.cfg), daemon=True, name="miau-ia-trabalhador")
        self.p.start()
        self.conn = a
        self.ligado_em = time.time()
        self.modelos = []

    def ligar(self):
        with self.trava:
            self._ligar()
            self.ult = time.time()

    def desligar(self):
        with self.trava:
            self._desligar()

    def _desligar(self):
        if self.p is None:
            return
        try:
            if self.p.is_alive():
                self.conn.send(("sair", None))
                self.p.join(5)
            if self.p.is_alive():
                self.p.terminate()
                self.p.join(3)
        except Exception:
            pass
        self.p = None
        self.conn = None
        self.modelos = []
        self.ligado_em = None

    def chamar(self, nome, *args):
        with self.trava:
            self._ligar()
            try:
                self.conn.send((nome, args))
                st, res, mods = self.conn.recv()
            except (EOFError, OSError, BrokenPipeError):
                self._desligar()
                raise RuntimeError("a IA local fechou no meio da tarefa (falta de memória?). Tente de novo.")
            finally:
                self.ult = time.time()
            self.modelos = mods
            if st == "erro":
                raise RuntimeError(res)
            return res

    def _vigia(self):
        while True:
            time.sleep(15)
            lim = getattr(self.cfg, "desligar_apos_s", 600)
            if lim and self.ligado() and time.time() - self.ult > lim and self.trava.acquire(False):
                try:
                    self._desligar()
                finally:
                    self.trava.release()


class Servico:
    def __init__(self, cfg, cliente_claude=None):
        self.cfg = cfg
        self.trab = Trabalhador(cfg)
        self.claude = ClaudeAPIManager(cfg, cliente_claude)
        self.agora = {}
        self.recentes = collections.deque(maxlen=30)
        self.trava_at = threading.Lock()
        self._nat = 0
        self.fila = 0
        self.trava_fila = threading.Lock()
        self._pc2 = {"t": 0, "ok": False, "ms": None}

    # ---------- config.toml mudou? relê sem reiniciar ----------
    arq_config = None
    _mt = None

    def recarregar(self):
        if not self.arq_config:
            return
        try:
            mt = os.path.getmtime(self.arq_config)
        except OSError:
            return
        if self._mt is None:
            self._mt = mt
            return
        if mt == self._mt:
            return
        self._mt = mt
        try:
            novo = carregar(self.arq_config)
        except Exception as e:  # arquivo salvo pela metade ou com erro: mantém o que estava valendo
            sys.stderr.write("config.toml com erro, mantive o anterior: %s\n" % e)
            return
        chave_mudou = novo.chave != self.cfg.chave
        for k in ("chave", "modelo", "modelo_rapido", "teto_mensal_usd", "cache_ttl", "precos", "token", "pc2", "pc2_token",
                  "desligar_apos_s", "descarregar_apos_s", "descrever"):
            setattr(self.cfg, k, getattr(novo, k))
        if chave_mudou:
            self.claude.trocar_chave(self.cfg.chave)
        print("config.toml relido%s" % (" (chave nova do Claude)" if chave_mudou else ""))

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

    # ---------- o que está rodando agora (monitor do painel) ----------
    @contextlib.contextmanager
    def ativ(self, ia, tarefa, onde="placa de vídeo"):
        with self.trava_at:
            self._nat += 1
            k = self._nat
            self.agora[k] = {"ia": ia, "tarefa": tarefa, "onde": onde, "desde": time.time()}
        ok = False
        try:
            yield
            ok = True
        finally:
            with self.trava_at:
                a = self.agora.pop(k, None)
                if a:
                    self.recentes.appendleft({**a, "dur": round(time.time() - a["desde"], 1), "ok": ok})

    def atividade(self):
        agora = time.time()
        with self.trava_at:
            at = [{**a, "seg": round(agora - a["desde"])} for a in self.agora.values()]
            rec = list(self.recentes)[:15]
        return {"agora": at, "recentes": rec, "ia_local": {"ligada": self.trab.ligado(), "modelos": self.trab.modelos if self.trab.ligado() else [],
                "parada_ha_s": round(agora - self.trab.ult) if self.trab.ligado() else None, "desliga_apos_s": getattr(self.cfg, "desligar_apos_s", 600)},
                "nomes": NOMES_IA, **vram.info()}

    def _ia(self, chave, tarefa):
        e, n, m = NOMES_IA[chave]
        return self.ativ(e + " " + n + " (" + m + ")", tarefa)

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
        with self._ia("recorte", "tirando o fundo de uma foto"):
            return self._gpu(lambda: self.trab.chamar("recortar", img))

    def figurinhas(self, prompt, n, semente=None, estilo="figurinha", refs=None, forca="medio"):
        estilo = estilo if estilo in J_FIG.ESTILOS else "figurinha"
        R = []
        for r in (refs or [])[:3]:
            try:
                from PIL import Image
                R.append(Image.open(io.BytesIO(base64.b64decode(str(r).split(",", 1)[-1]))).convert("RGBA"))
            except Exception:
                pass
        with self._ia("figurinha", "desenhando %d %s: %s%s%s" % (n, estilo, prompt[:60], " · no estilo de %d referência%s" % (len(R), "s" if len(R) > 1 else "") if R else "", " + recorte" if J_FIG.RECORTA[estilo] else "")):
            return self._gpu(lambda: self.trab.chamar("figurinhas", prompt, n, semente, estilo, R, forca))

    def _arquivo(self, dataurl, nome, padrao="bin"):
        m = re.match(r"^data:([\w/+.-]+)(?:;[^,]*)?;base64,", str(dataurl or ""))
        dados = base64.b64decode(str(dataurl)[m.end():] if m else str(dataurl or ""))
        if not dados:
            raise ValueError("arquivo vazio")
        ext = (re.search(r"\.(\w{2,5})$", nome or "") or re.search(r"/(\w+)", m.group(1) if m else "") or [None, padrao])[1]
        with tempfile.NamedTemporaryFile(suffix="." + ext.replace("mpeg", "mp3").replace("quicktime", "mov"), delete=False) as t:
            t.write(dados)
            return t.name

    def descrever(self, dataurl, tipo="foto", nome="", empresa=None, quadros=3, idioma="pt", passo=0):
        """Story (foto ou vídeo) -> o que aparece, o texto escrito e a fala, resumidos em português."""
        from PIL import Image
        caminho = self._arquivo(dataurl, nome, "mp4" if tipo == "video" else "jpg")
        try:
            tempos = []
            if tipo == "video" and passo > 0:               # análise completa: 1 quadro a cada `passo` s + cortes de cena
                par = self.trab.chamar("cenas", caminho, float(passo), max(4, min(30, quadros)))
                imgs, tempos = [p[0] for p in par], [p[1] for p in par]
            else:
                imgs = self.trab.chamar("quadros", caminho, max(1, min(8, quadros))) if tipo == "video" else [Image.open(caminho).convert("RGB")]
            fala, fala_erro, fala_idioma, segs = "", "", "", []
            if tipo == "video":
                try:
                    tr = self.transcrever_arquivo(caminho, idioma)
                    fala, fala_idioma, segs = tr.get("texto", ""), tr.get("idioma", ""), tr.get("segmentos") or []
                    if not fala:
                        fala_erro = "sem fala detectada: " + (tr.get("diag") or "só música ou silêncio")
                except Exception as e:
                    fala_erro = str(e)[:300]
                    sys.stderr.write("vídeo sem áudio legível: %s\n" % e)
            via, cenas = "local", []
            if self.cfg.descrever != "claude":
                try:
                    with self._ia("descrever", "lendo um Story (%s, %d imagem%s)" % (tipo, len(imgs), "ns" if len(imgs) > 1 else "")):
                        cenas = self._gpu(lambda: self.trab.chamar("ver", imgs))
                except Exception as e:
                    sys.stderr.write("Florence não rodou (%s); usando o Claude\n" % e)
                    cenas = []
            if not cenas and self.claude.configurada:
                via = "claude"
                pequenas = []
                for im in imgs:
                    im = im.copy()
                    im.thumbnail((768, 768))
                    pequenas.append(para_dataurl(im.convert("RGB"), "JPEG"))
                with self.ativ("⚡ Claude Haiku", "lendo o Story (a leitura local não rodou)", "nuvem"):
                    t, _ = self.claude.texto("descrever", empresa, "", "", "Descreva em português, em 2 a 3 frases, o que aparece neste Story do Instagram (quadros de um mesmo vídeo ou uma foto) e transcreva o texto escrito na imagem, se houver, numa linha começando com TEXTO:.", 400, pequenas)
                partes = t.split("TEXTO:")  # noqa
                cenas = [{"cena": partes[0].strip(), "texto": partes[1].strip() if len(partes) > 1 else ""}]
            if tempos and len(tempos) == len(cenas):
                for c, t in zip(cenas, tempos):
                    c["t"] = t
            texto_tela = " / ".join(sorted({c["texto"] for c in cenas if c.get("texto")}))
            resumo = " ".join(c["cena"] for c in cenas if c.get("cena"))
            em_ingles = via == "local"
            if via == "local" and self.claude.configurada and cenas:
                try:
                    resumo, _ = self.claude.texto("resumir", empresa, "", "", (
                        "Resuma em português, em 1 a 2 frases objetivas, o que este Story do Instagram mostra e diz. "
                        "Use só estas informações (descrições automáticas em inglês dos quadros, texto da tela e fala):\n"
                        + "\n".join("- " + ("[%ss] " % c["t"] if "t" in c else "") + c["cena"] for c in cenas) + "\nTexto na tela: " + (texto_tela or "nenhum") + "\nFala: " + (fala[:1500] or "nenhuma")), 300)
                    em_ingles = False
                except Exception:
                    pass
            return {"resumo": resumo.strip(), "cenas": cenas, "texto_tela": texto_tela, "fala": fala, "fala_erro": fala_erro, "idioma": fala_idioma, "via": via, "segmentos": segs[:120],
                    "em_ingles": em_ingles}
        finally:
            try:
                os.remove(caminho)
            except OSError:
                pass

    def transcrever_arquivo(self, caminho, idioma="pt"):
        with self._ia("transcrever", "transcrevendo um áudio"):
            return self._gpu(lambda: self.trab.chamar("transcrever", caminho, idioma))

    def transcrever(self, dataurl, nome=""):
        caminho = self._arquivo(dataurl, nome, "webm")
        try:
            return self.transcrever_arquivo(caminho)
        finally:
            try:
                os.remove(caminho)
            except OSError:
                pass

    def health(self, completo):
        d = {"ok": True, "servico": "miau-ia", "versao": VERSAO, "papel": self.cfg.papel, "rede": self.cfg.escutar not in ("127.0.0.1", "localhost")}
        if completo and d["rede"]:
            try:
                import rede
                d["enderecos"] = ["http://%s:%d" % (ip, self.cfg.porta) for ip in rede.ips()]
            except Exception:
                pass
        if not completo:
            return d
        d.update(vram.info())
        d["simulado"] = self.cfg.simular
        d["modelos_na_memoria"] = self.trab.modelos if self.trab.ligado() else []
        d["ia_local_ligada"] = self.trab.ligado()
        d["fila"] = self.fila
        d["pc2"] = {"endereco": self.cfg.pc2, "online": self.pc2_online(), "ms": self._pc2["ms"]} if self.cfg.pc2 else None
        d["claude"] = {"configurada": self.claude.configurada, "modelo": self.cfg.modelo,
                       "modelo_rapido": self.cfg.modelo_rapido, "cache": self.cfg.cache_ttl, **self.claude.resumo()}
        d["claude"].pop("empresas", None)
        if self.cfg.chave and not str(self.cfg.chave).startswith("sk-ant-"):
            d["claude"]["aviso"] = "a chave no config.toml não parece da Anthropic (começa com sk-ant-)"
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
            sv.recarregar()
            if self.path.startswith("/midia?"):   # vídeo/foto do Instagram para o <video> do painel (o link do CDN às vezes não abre direto)
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query)
                if cfg.token and not hmac.compare_digest((q.get("k") or [""])[0], cfg.token):
                    return self._json(401, {"erro": "código do PC errado"})
                try:
                    d = baixar_midia((q.get("u") or [""])[0])
                except Exception as e:
                    return self._json(400, {"erro": str(e)})
                import base64
                tipo, b64 = d[5:].split(";base64,", 1)
                dados = base64.b64decode(b64)
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(dados)))
                self.send_header("Cache-Control", "private, max-age=3600")
                self.end_headers()
                self.wfile.write(dados)
                return
            if self.path.split("?")[0] == "/health":
                return self._json(200, sv.health(self._autorizado()))
            if not self._autorizado():
                return self._json(401, {"erro": "código do PC errado (Config → IA local no painel)"})
            if self.path == "/claude/uso":
                return self._json(200, sv.claude.resumo())
            if self.path == "/atividade":
                return self._json(200, sv.atividade())
            self._json(404, {"erro": "rota não existe"})

        def do_POST(self):
            sv.recarregar()
            if not self._autorizado():
                return self._json(401, {"erro": "código do PC errado (Config → IA local no painel)"})
            try:
                b = self._corpo()
                rota = self.path.split("?")[0]
                if rota == "/config/pc2":   # o painel do PC 1 grava o endereço e o código do PC 2 no config.toml
                    if self.client_address[0] not in ("127.0.0.1", "::1"):
                        return self._json(403, {"erro": "só o próprio PC 1 pode mudar a configuração"})
                    end, tk = str(b.get("pc2") or "").strip().rstrip("/"), str(b.get("pc2_token") or "").strip()
                    if end and not re.match(r"^https?://[\w.\-]+(:\d+)?$", end):
                        return self._json(400, {"erro": "endereço inválido (ex.: http://192.168.0.20:8765)"})
                    arq = sv.arq_config or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.toml")
                    t = open(arq, encoding="utf-8").read() if os.path.exists(arq) else "[servico]\n"
                    for k, v in (("pc2", end), ("pc2_token", tk)):
                        if re.search(r"^\s*%s\s*=" % k, t, re.M):
                            t = re.sub(r'^(\s*%s\s*=\s*)"[^"]*"' % k, lambda m: m.group(1) + '"%s"' % v, t, count=1, flags=re.M)
                        else:
                            t = t.replace("[servico]", '[servico]\n%s = "%s"' % (k, v), 1)
                    open(arq, "w", encoding="utf-8").write(t)
                    cfg.pc2, cfg.pc2_token = end, tk
                    sv._pc2["t"] = 0
                    return self._json(200, {"ok": True, "pc2": sv.pc2_online() if end else False})
                if rota == "/ia/desligar":
                    sv.trab.desligar()
                    return self._json(200, {"ok": True, "ligada": False})
                if rota == "/ia/ligar":
                    sv.trab.ligar()
                    sv.trab.chamar("ping")
                    return self._json(200, {"ok": True, "ligada": True})
                if rota == "/recorte":
                    img = de_dataurl(b.get("imagem"))
                    return self._json(200, {"imagem": para_dataurl(sv.recortar(img)), "onde": cfg.papel})
                if rota == "/figurinha":
                    n = max(1, min(4, int(b.get("n") or 2)))
                    prompt = str(b.get("prompt") or "").strip()[:300]
                    if not prompt:
                        return self._json(400, {"erro": "falta a descrição da figurinha"})
                    if b.get("traduzir", True) and sv.claude.configurada:
                        with sv.ativ("⚡ Claude Haiku", "traduzindo o pedido da figurinha para o gerador", "nuvem"):
                            prompt = sv.claude.prompt_figurinha(prompt)
                    if b.get("extra"):   # estilo da empresa e o que a equipe não quer (já em inglês, vindo do painel)
                        prompt = (prompt + ", " + str(b.get("extra"))[:400]).strip(", ")
                    if cfg.pc2 and not b.get("_local") and sv.pc2_online():
                        try:
                            r = sv.no_pc2("/figurinha", {"prompt": prompt, "n": n, "traduzir": False, "_local": True, "estilo": b.get("estilo") or "figurinha", "refs": b.get("refs") or [], "forca": b.get("forca") or "medio"})
                            r["onde"] = "pc2"
                            return self._json(200, r)
                        except Exception as e:
                            sys.stderr.write("PC 2 falhou, fazendo no PC 1: %s\n" % e)
                    imgs = sv.figurinhas(prompt, n, b.get("semente"), b.get("estilo") or "figurinha", b.get("refs") or [], b.get("forca") or "medio")
                    return self._json(200, {"imagens": [para_dataurl(i) for i in imgs], "prompt": prompt, "onde": cfg.papel})
                if rota == "/transcrever":
                    if not b.get("audio"):
                        return self._json(400, {"erro": "falta o áudio"})
                    return self._json(200, sv.transcrever(b.get("audio"), b.get("nome") or ""))
                if rota == "/descrever":
                    midia = b.get("midia")
                    if not midia and b.get("url"):
                        midia = baixar_midia(b.get("url"))
                    if not midia:
                        return self._json(400, {"erro": "falta a foto ou o vídeo"})
                    return self._json(200, sv.descrever(midia, "video" if b.get("tipo") == "video" else "foto", b.get("nome") or "", b.get("empresa"), int(b.get("quadros") or 3), b.get("idioma") or "pt", float(b.get("passo") or 0)))
                if rota == "/claude/classificar":
                    with sv.ativ("⚡ Claude Haiku", "classificando uma ideia", "nuvem"):
                      dados, uso = sv.claude.ferramenta("classificar", b.get("empresa"), b.get("sistema") or "", b.get("empresa_md") or "",
                                                      "Classifique esta ideia da equipe (transcrição de áudio ou texto do celular):\n\n" + str(b.get("texto") or "")[:6000],
                                                      "classificar", "Classifica a ideia para o banco de ideias da agência.", b.get("schema") or SCHEMA_CLASSE, max_tokens=800)
                    return self._json(200, {"dados": dados, "uso": uso})
                if rota in ("/claude/dia", "/claude/layouts", "/claude/modelo"):
                    tarefa = rota.rsplit("/", 1)[1]
                    nome, desc = {
                        "dia": ("montar_telas", "Entrega as telas do dia (texto de cada tela, modelo e legenda) para o painel montar."),
                        "layouts": ("criar_modelo", "Entrega os modelos de layout (camadas) que o painel desenha."),
                        "modelo": ("criar_modelo", "Entrega o modelo de layout (camadas) que recria a arte de referência."),
                    }[tarefa]
                    with sv.ativ("🧠 Claude Sonnet", {"dia": "montando as telas do dia", "layouts": "criando os layouts", "modelo": "lendo a arte de referência"}[tarefa] + ((" · " + str((b.get("empresa") or {}).get("nome") or "")) if b.get("empresa") else ""), "nuvem"):
                        dados, uso = sv.claude.ferramenta(tarefa, b.get("empresa"), b.get("sistema"), b.get("empresa_md"),
                                                          b.get("pedido"), nome, desc, b.get("schema"), b.get("imagens"))
                    return self._json(200, {"dados": dados, "uso": uso})
                if rota == "/claude/testar":
                    with sv.ativ("⚡ Claude Haiku", "testando a chave da API", "nuvem"):
                        return self._json(200, sv.claude.testar())
                if rota == "/claude/chat":
                    tarefa = b.get("tarefa") if b.get("tarefa") in ("chat", "roteiro", "sugerir") else "chat"
                    rot = {"roteiro": ("🧠 Claude Sonnet", "adaptando um formato viral"), "sugerir": ("🧠 Claude Sonnet", "sugerindo perfis de referência")}.get(tarefa, ("⚡ Claude Haiku", "respondendo"))
                    with sv.ativ(rot[0], rot[1] + ((" · " + str((b.get("empresa") or {}).get("nome") or "")) if b.get("empresa") else ""), "nuvem"):
                        txt, uso = sv.claude.texto(tarefa, b.get("empresa"), b.get("sistema"), b.get("empresa_md"), b.get("mensagem"), int(b.get("max_tokens") or 2500), busca=bool(b.get("busca")) and tarefa == "sugerir")
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
                if "credit balance" in msg.lower() or "billing" in msg.lower():
                    return self._json(402, {"erro": "A conta da API está sem crédito. Em console.anthropic.com → Billing (Configurar cobrança), adicione créditos e tente de novo."})
                if "Authentication" in nome or "PermissionDenied" in nome or "NotFound" in nome:
                    return self._json(401, {"erro": explicar(e)})
                return self._json(500, {"erro": "%s: %s" % (nome, msg[:300])})

    return H


def main():
    cfg = carregar()
    if sys.stdout is None or sys.stderr is None:  # aberto escondido (pythonw): mensagens vão para dados/miau-ia.log
        sys.stdout = sys.stderr = open(os.path.join(cfg.pasta_dados, "miau-ia.log"), "a", encoding="utf-8", buffering=1)
    if cfg.escutar not in ("127.0.0.1", "localhost") and not cfg.token:
        sys.exit("Para escutar na rede (%s) é obrigatório ter token no config.toml." % cfg.escutar)
    sv = Servico(cfg)
    sv.arq_config = os.environ.get("MIAU_CONFIG") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.toml")
    sv.recarregar()
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
