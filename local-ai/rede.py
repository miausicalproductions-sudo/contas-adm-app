"""Abre o miau-ia do PC 1 para a equipe na rede local (Mac da Thaís, notebook...).

Muda escutar para "0.0.0.0" no config.toml (o código do PC continua obrigatório) e mostra o endereço e o código
para colocar no painel do outro computador. Uso: rede.py abrir | rede.py fechar
"""
import os
import re
import socket
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQ = os.path.join(AQUI, "config.toml")


def ips():
    out = set()
    try:
        for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            out.add(i[4][0])
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        out.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(x for x in out if not x.startswith("127.") and not x.startswith("169.254."))


def main():
    abrir = (sys.argv[1:] or ["abrir"])[0] != "fechar"
    t = open(ARQ, encoding="utf-8").read()
    tok = (re.search(r'^\s*token\s*=\s*"([^"]*)"', t, re.M) or [None, ""])[1]
    if abrir and not tok:
        sys.exit("O config.toml não tem token (código do PC). Rode o instalar.bat de novo.")
    novo = re.sub(r'^(\s*escutar\s*=\s*)"[^"]*"', r'\1"%s"' % ("0.0.0.0" if abrir else "127.0.0.1"), t, count=1, flags=re.M)
    if novo == t and not re.search(r'^\s*escutar\s*=', t, re.M):
        novo = t.replace("[servico]", '[servico]\nescutar = "%s"' % ("0.0.0.0" if abrir else "127.0.0.1"), 1)
    open(ARQ, "w", encoding="utf-8").write(novo)
    if not abrir:
        print("Pronto: o miau-ia voltou a atender só este computador.")
        return
    print("\nPronto: o miau-ia agora atende a equipe na rede local (com o código do PC).\n")
    print("No painel do outro computador (Mac): Config → IA local e Claude API")
    for ip in ips():
        print("   Endereço: http://%s:8765" % ip)
    print("   Código do PC: %s\n" % tok)
    print("Dica: peça no roteador um IP fixo para este PC; se o endereço mudar, é só trocar no painel do Mac.")


if __name__ == "__main__":
    main()
