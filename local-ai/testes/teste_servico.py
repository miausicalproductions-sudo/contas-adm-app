"""Testes do miau-ia sem placa de vídeo e sem chave (Claude simulado). Rode: python testes/teste_servico.py"""
import base64
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace as NS

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

from PIL import Image, ImageDraw  # noqa: E402

from config import Config  # noqa: E402
from server import Servico, criar_handler  # noqa: E402


class ClaudeFalso:
    def __init__(self):
        self.pedidos = []
        self.messages = self

    def create(self, **kw):
        self.pedidos.append(kw)
        u = NS(input_tokens=120, output_tokens=900, cache_read_input_tokens=6000, cache_creation_input_tokens=0)
        if kw.get("tools"):
            nome = kw["tools"][0]["name"]
            dado = {"telas": [{"titulo": "Bom *dia*", "frases": ["Toddy veio dar oi"]}], "modelo": "Saudação"} if nome == "montar_telas" \
                else {"modelos": [{"nome": "Teste", "telas": [{"fundo": "fundo", "camadas": [{"tipo": "titulo", "x": 8, "y": 15, "w": 84, "h": 12}]}]}], "faltou": []}
            return NS(content=[NS(type="tool_use", input=dado)], usage=u, stop_reason="tool_use")
        return NS(content=[NS(type="text", text="sleeping kitten sticker")], usage=u, stop_reason="end_turn")


def subir(cfg, cli=None):
    sv = Servico(cfg, cli)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), criar_handler(sv))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return sv, srv, "http://127.0.0.1:%d" % srv.server_address[1]


def chamar(url, corpo=None, token="t1"):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 method="POST" if corpo is not None else "GET",
                                 headers={"Content-Type": "application/json", "X-Miau-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def foto():
    img = Image.new("RGB", (300, 400), (236, 240, 244))
    ImageDraw.Draw(img).ellipse((80, 100, 220, 320), fill=(150, 95, 50))
    b = io.BytesIO()
    img.save(b, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


class Testes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.makedirs(cls.tmp + "/pc1", exist_ok=True)
        os.makedirs(cls.tmp + "/pc2", exist_ok=True)
        cls.sv2, cls.srv2, cls.u2 = subir(Config(token="t2", simular=True, escutar="0.0.0.0", pasta_dados=cls.tmp + "/pc2"))
        cls.falso = ClaudeFalso()
        cls.sv1, cls.srv1, cls.u1 = subir(Config(token="t1", simular=True, pc2=cls.u2, pc2_token="t2", pasta_dados=cls.tmp + "/pc1",
                                                 teto_mensal_usd=5), cls.falso)

    def test_a_health(self):
        c, d = chamar(self.u1 + "/health", token="")
        self.assertEqual((c, d["servico"], "claude" in d), (200, "miau-ia", False))
        c, d = chamar(self.u1 + "/health")
        self.assertTrue(d["claude"]["configurada"])
        self.assertTrue(d["pc2"]["online"])
        self.assertEqual(d["papel"], "pc1")

    def test_token(self):
        c, d = chamar(self.u1 + "/recorte", {"imagem": foto()}, token="errado")
        self.assertEqual(c, 401)

    def test_recorte(self):
        c, d = chamar(self.u1 + "/recorte", {"imagem": foto()})
        self.assertEqual(c, 200)
        img = Image.open(io.BytesIO(base64.b64decode(d["imagem"].split(",", 1)[1])))
        self.assertEqual(img.getpixel((2, 2))[3], 0)        # fundo transparente
        self.assertEqual(img.getpixel((150, 210))[3], 255)  # pet inteiro

    def test_z_figurinha_pc2_e_volta(self):
        c, d = chamar(self.u1 + "/figurinha", {"prompt": "gatinho dormindo", "n": 2})
        self.assertEqual((c, d["onde"], len(d["imagens"])), (200, "pc2", 2))
        self.assertEqual(d["prompt"], "sleeping kitten sticker")  # traduzido pelo modelo rápido
        self.srv2.shutdown()
        self.srv2.server_close()
        self.sv1._pc2["t"] = 0
        c, d = chamar(self.u1 + "/figurinha", {"prompt": "osso", "n": 1})
        self.assertEqual((c, d["onde"]), (200, "pc1"))

    def test_claude_layouts_cache_e_gasto(self):
        schema = {"type": "object", "properties": {"modelos": {"type": "array"}}, "required": ["modelos"]}
        c, d = chamar(self.u1 + "/claude/layouts", {"empresa": {"id": "c1", "nome": "Pet Miau"}, "sistema": "REGRAS" * 400,
                                                    "empresa_md": "# Pet Miau" * 300, "pedido": "3 layouts", "schema": schema})
        self.assertEqual(c, 200, d)
        self.assertEqual(d["dados"]["modelos"][0]["nome"], "Teste")
        p = self.falso.pedidos[-1]
        self.assertEqual(p["tool_choice"], {"type": "tool", "name": "criar_modelo"})
        self.assertEqual([b.get("cache_control") for b in p["system"]], [{"type": "ephemeral"}] * 2)
        self.assertEqual(p["model"], "claude-sonnet-5-5")
        self.assertGreater(d["uso"]["cache_pct"], 90)
        c, u = chamar(self.u1 + "/claude/uso")
        self.assertIn("c1", u["empresas"])

    def test_claude_dia_e_teto(self):
        schema = {"type": "object", "properties": {"telas": {"type": "array"}}}
        c, d = chamar(self.u1 + "/claude/dia", {"empresa": {"id": "c2"}, "pedido": "telas", "schema": schema})
        self.assertEqual(d["dados"]["telas"][0]["titulo"], "Bom *dia*")
        self.sv1.cfg.teto_mensal_usd = 0.000001
        c, d = chamar(self.u1 + "/claude/dia", {"empresa": {"id": "c2"}, "pedido": "telas", "schema": schema})
        self.sv1.cfg.teto_mensal_usd = 5
        self.assertEqual((c, d.get("teto")), (402, True))

    def test_schema_invalido(self):
        c, d = chamar(self.u1 + "/claude/dia", {"pedido": "x", "schema": "nada"})
        self.assertEqual(c, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
