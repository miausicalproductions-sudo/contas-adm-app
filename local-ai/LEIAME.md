# miau-ia: a IA local da Studios Miau

Programa que roda no PC 1 (e, se quiser, no PC 2) e faz para o painel:

- **Claude pela API**: Gerar dia, Gerar layouts e Criar modelo, sem copiar e colar. A chave fica só aqui.
- **Recorte de fundo** na placa de vídeo (BiRefNet), melhor e mais rápido que o do navegador.
- **Figurinhas** geradas na placa (SDXL Lightning, 4 passos), já sem fundo, direto para a biblioteca.
- **PC 2**: se estiver ligado, as figurinhas vão para a RTX 5060; desligado, o PC 1 faz tudo.

## Instalar (uma vez em cada PC)
1. Instale o **Python 3.12** em python.org, marcando "Add python.exe to PATH".
2. Baixe esta pasta `local-ai` (do GitHub do painel) para, por exemplo, `C:\miau-ia`.
3. Dê dois cliques em **instalar.bat**. No fim ele mostra o **código do PC**.
4. No painel: **Config → IA local e Claude API**: endereço `http://127.0.0.1:8765` e o código. Clique em **Salvar e testar**.
5. **Só no PC 1**: abra o `config.toml` no Bloco de Notas, cole a chave da API em `chave = "..."` (console.anthropic.com → API Keys) e confira o `teto_mensal_usd`. Rode o `iniciar.bat` ou reinicie o PC.

## PC 2 (opcional)
1. Instale do mesmo jeito.
2. No `config.toml` do PC 2: `escutar = "0.0.0.0"`. Não coloque a chave do Claude.
3. Rode `liberar-rede-pc2.bat` como administrador (libera a porta 8765 na rede local).
4. No `config.toml` do PC 1: `pc2 = "http://IP-DO-PC2:8765"` e `pc2_token = "código do PC 2"`.

## Segurança
- `config.toml` (chave e códigos) nunca vai para o GitHub: está no `.gitignore`.
- O PC 1 só aceita pedidos do próprio computador. O PC 2 só aceita quem tiver o código dele.
- Se a chave vazar: apague-a no console da Anthropic e crie outra.

## Problemas
- Para ver erros: feche o miau-ia escondido (Gerenciador de Tarefas → pythonw) e rode `iniciar.bat`. O registro fica em `dados/miau-ia.log`.
- Sem placa de vídeo (ou para testar o painel): `simular = true` em `[gpu]`.
- Gasto do mês: Config do painel mostra; o detalhe por empresa fica em `dados/uso.json`.
- Testes (sem placa nem chave): `venv\Scripts\python testes\teste_servico.py`.
