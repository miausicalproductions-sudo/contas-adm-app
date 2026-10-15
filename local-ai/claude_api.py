"""ClaudeAPIManager: o painel pede, este módulo chama a API da Anthropic (SDK oficial `anthropic`).

- Roteamento: tarefas de layout/roteiro vão para o modelo principal; classificação, tradução
  e chat leve vão para o modelo rápido (nomes no config.toml).
- Prompt caching: o `system` vai em 2 blocos com cache_control: (1) regras + vocabulário do editor,
  iguais para todas as empresas; (2) o empresa.md (voz, paleta, modelos, biblioteca, aprendizados).
  Só o pedido do dia vai sem cache.
- Saída estruturada: uma ferramenta forçada (tool_choice) cujo schema vem do painel (gerado do VOCAB).
- Gasto: cada chamada é registrada em dados/uso.json (por mês e por empresa); acima do teto mensal
  a chamada é recusada e o painel volta ao copiar e colar.
"""
import base64
import json
import os
import re
import threading
import time


class LimiteAtingido(Exception):
    pass


class ErroClaude(Exception):
    pass


TAREFAS_RAPIDAS = {"classificar", "traduzir", "chat", "resumir"}


class ClaudeAPIManager:
    def __init__(self, cfg, cliente=None):
        self.cfg = cfg
        self.trava = threading.Lock()
        self.arq = os.path.join(cfg.pasta_dados, "uso.json")
        self.cli = cliente
        if self.cli is None and cfg.chave:
            import anthropic
            self.cli = anthropic.Anthropic(api_key=cfg.chave, max_retries=3, timeout=240)

    # ---------- estado ----------
    @property
    def configurada(self):
        return self.cli is not None

    def modelo_de(self, tarefa):
        return self.cfg.modelo_rapido if tarefa in TAREFAS_RAPIDAS else self.cfg.modelo

    def _ler(self):
        try:
            with open(self.arq, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def resumo(self):
        mes = time.strftime("%Y-%m")
        d = self._ler().get(mes, {})
        return {"mes": mes, "gasto_usd": round(d.get("total_usd", 0.0), 4), "teto_usd": self.cfg.teto_mensal_usd,
                "chamadas": d.get("chamadas", 0), "empresas": d.get("empresas", {}),
                "cache_economia_usd": round(d.get("economia_usd", 0.0), 4)}

    # ---------- montagem ----------
    def _cache(self):
        return {"type": "ephemeral", "ttl": "1h"} if self.cfg.cache_ttl == "1h" else {"type": "ephemeral"}

    def _sistema(self, fixo, empresa_md):
        blocos = []
        if fixo:
            blocos.append({"type": "text", "text": fixo, "cache_control": self._cache()})
        if empresa_md:
            blocos.append({"type": "text", "text": empresa_md, "cache_control": self._cache()})
        return blocos

    @staticmethod
    def _imagens(imgs):
        out = []
        for s in (imgs or [])[:5]:
            m = re.match(r"^data:(image/(?:png|jpeg|webp|gif));base64,(.+)$", str(s), re.S)
            if not m:
                continue
            if len(m.group(2)) > 6_500_000:
                raise ErroClaude("imagem grande demais para mandar ao Claude (máx. ~5 MB)")
            out.append({"type": "image", "source": {"type": "base64", "media_type": m.group(1), "data": m.group(2)}})
        return out

    def _checar_teto(self):
        r = self.resumo()
        if self.cfg.teto_mensal_usd and r["gasto_usd"] >= self.cfg.teto_mensal_usd:
            raise LimiteAtingido("O gasto do mês com a API chegou ao teto (US$ %.2f). Use o copiar e colar ou aumente o teto no config.toml." % self.cfg.teto_mensal_usd)

    def _registrar(self, empresa, tarefa, modelo, u):
        ent = getattr(u, "input_tokens", 0) or 0
        sai = getattr(u, "output_tokens", 0) or 0
        lido = getattr(u, "cache_read_input_tokens", 0) or 0
        grav = getattr(u, "cache_creation_input_tokens", 0) or 0
        pe, ps = self.cfg.precos.get(modelo, [3.0, 15.0])
        mult_grav = 2.0 if self.cfg.cache_ttl == "1h" else 1.25
        usd = (ent * pe + grav * pe * mult_grav + lido * pe * 0.1 + sai * ps) / 1e6
        economia = lido * pe * 0.9 / 1e6
        mes = time.strftime("%Y-%m")
        emp = empresa or {}
        with self.trava:
            d = self._ler()
            m = d.setdefault(mes, {"total_usd": 0.0, "chamadas": 0, "economia_usd": 0.0, "empresas": {}})
            m["total_usd"] += usd
            m["chamadas"] += 1
            m["economia_usd"] = m.get("economia_usd", 0.0) + economia
            e = m["empresas"].setdefault(str(emp.get("id") or "-"), {"nome": emp.get("nome") or "", "usd": 0.0, "chamadas": 0})
            e["usd"] += usd
            e["chamadas"] += 1
            e.setdefault("tarefas", {}).setdefault(tarefa, 0)
            e["tarefas"][tarefa] += 1
            tmp = self.arq + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.arq)
        tot = ent + lido + grav
        return {"modelo": modelo, "entrada": ent, "saida": sai, "cache_lido": lido, "cache_gravado": grav,
                "custo_usd": round(usd, 5), "cache_pct": round(100 * lido / tot) if tot else 0}

    # ---------- chamadas ----------
    def ferramenta(self, tarefa, empresa, fixo, empresa_md, pedido, nome, descricao, schema, imagens=None, max_tokens=12000):
        """Chama o Claude obrigando a resposta a vir só no schema. Devolve (dados, uso)."""
        if not self.configurada:
            raise ErroClaude("A chave da API não está no config.toml deste PC.")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ErroClaude("schema inválido (precisa ser um objeto JSON Schema)")
        self._checar_teto()
        modelo = self.modelo_de(tarefa)
        conteudo = self._imagens(imagens) + [{"type": "text", "text": str(pedido or "")}]
        r = self.cli.messages.create(
            model=modelo, max_tokens=max_tokens, system=self._sistema(fixo, empresa_md),
            tools=[{"name": nome, "description": descricao, "input_schema": schema}],
            tool_choice={"type": "tool", "name": nome},
            messages=[{"role": "user", "content": conteudo}])
        uso = self._registrar(empresa, tarefa, modelo, r.usage)
        if getattr(r, "stop_reason", "") == "max_tokens":
            raise ErroClaude("A resposta do Claude foi cortada (grande demais). Peça menos telas ou modelos.")
        bloco = next((b for b in r.content if getattr(b, "type", "") == "tool_use"), None)
        if bloco is None:
            raise ErroClaude("O Claude não devolveu o formato pedido.")
        return bloco.input, uso

    def texto(self, tarefa, empresa, fixo, empresa_md, pedido, max_tokens=1500):
        if not self.configurada:
            raise ErroClaude("A chave da API não está no config.toml deste PC.")
        self._checar_teto()
        modelo = self.modelo_de(tarefa)
        r = self.cli.messages.create(model=modelo, max_tokens=max_tokens, system=self._sistema(fixo, empresa_md),
                                     messages=[{"role": "user", "content": str(pedido or "")}])
        uso = self._registrar(empresa, tarefa, modelo, r.usage)
        return "".join(getattr(b, "text", "") for b in r.content).strip(), uso

    def prompt_figurinha(self, descricao):
        """Português -> prompt curto em inglês para o gerador de imagens (modelo rápido, centavos)."""
        if not self.configurada or not descricao:
            return descricao
        try:
            t, _ = self.texto("traduzir", {"id": "-", "nome": "figurinhas"}, "", "",
                              "Translate to a short English image prompt (max 20 words, only the subject and style, no quotes): " + descricao, 120)
            return t.splitlines()[0][:200] or descricao
        except Exception:
            return descricao
