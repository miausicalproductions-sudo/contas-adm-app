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

## Já instalou antes? Só complete
- **Gerador de figurinhas** (SDXL Lightning + recorte, ~7 GB): `instalar_gerador_imagens.bat`. Usa o Python e o PyTorch que já estão aqui, baixa só o que falta e gera `dados\teste_figurinha.png` para conferir.
- **Código novo do GitHub + transcrição de áudio**: `atualizar.bat`. Baixa o código, mantém `config.toml`, `venv` e `dados`, instala só o que faltar (faster-whisper) e abre o miau-ia de novo.

## O que cada IA faz
| IA | Modelo | Quando o painel chama |
|---|---|---|
| Recorte de fundo | BiRefNet (rembg) | ✂️ recortar o fundo, figurinhas |
| Figurinhas, elementos e texturas | SDXL Lightning 4 passos, fp16 | figurinha "a criar" do Claude, ⚡ Criar figurinha, ↻ Outras opções |
| Transcrição | faster-whisper medium | 🎙 Ideias por voz, áudios do Telegram, fala dos Stories do celular |
| Leitura de imagem | Florence-2-large (se não carregar: Claude rápido) | Stories postados pelo celular (o que aparece e o texto na tela) |
| Claude (API) | Sonnet / Haiku | ⚡ Gerar dia, layouts, modelo, classificar ideias, traduzir figurinhas |

## Mac da equipe (ou outro computador) usando as IAs do PC 1
O Mac não roda as IAs: ele pede ao PC 1 pela rede local (figurinhas, recorte, transcrição, leitura de vídeo e o Claude pela API).
1. No PC 1: botão direito em **liberar-rede-equipe.bat** → Executar como administrador. Ele libera a porta 8765 no firewall (rede Privada), muda `escutar` para `"0.0.0.0"` no config.toml, reinicia o miau-ia e mostra o **endereço** (ex.: `http://192.168.0.15:8765`) e o **código do PC**.
2. No Mac: painel → Config → IA local e Claude API → cole o endereço e o código → Salvar e testar.
3. Peça no roteador um IP fixo para o PC 1 (se o IP mudar, troque o endereço no Mac).
- O código do PC continua obrigatório: sem ele ninguém na rede usa as IAs nem a chave do Claude.
- As tarefas automáticas (áudios do Telegram, Stories do celular) só rodam no painel do próprio PC 1, para não fazer nada duas vezes.
- Para voltar a atender só o PC 1: `venv\Scripts\python rede.py fechar` e reinicie o miau-ia.

## PC 2 (opcional)
1. Instale do mesmo jeito.
2. No `config.toml` do PC 2: `escutar = "0.0.0.0"`. Não coloque a chave do Claude.
3. Rode `liberar-rede-pc2.bat` como administrador (libera a porta 8765 na rede local).
4. No `config.toml` do PC 1: `pc2 = "http://IP-DO-PC2:8765"` e `pc2_token = "código do PC 2"`.

## Segurança
- `config.toml` (chave e códigos) nunca vai para o GitHub: está no `.gitignore`.
- O PC 1 só aceita pedidos do próprio computador. O PC 2 só aceita quem tiver o código dele.
- Se a chave vazar: apague-a no console da Anthropic e crie outra.

## Ligar e desligar
- O miau-ia tem duas partes: o **serviço** (leve, fica sempre aberto e atende o painel) e a **IA local** (as IAs da placa, num processo separado).
- A IA local **liga sozinha** no primeiro pedido e **desliga sozinha** depois de 10 min parada (`desligar_apos_s` no `config.toml`), liberando a RAM e a placa. Cada modelo sai da placa 90 s depois do último uso.
- No painel: a pílula 🤖 no rodapé mostra qual IA está rodando; clique nela para abrir o **Monitor das IAs** e ligar ou desligar a IA local na hora.
- `parar.bat` fecha o miau-ia inteiro; `ligar.bat` abre de novo (ele também abre sozinho com o Windows).

## Problemas
- Para ver erros: feche o miau-ia escondido (Gerenciador de Tarefas → pythonw) e rode `iniciar.bat`. O registro fica em `dados/miau-ia.log`.
- Sem placa de vídeo (ou para testar o painel): `simular = true` em `[gpu]`.
- Gasto do mês: Config do painel mostra; o detalhe por empresa fica em `dados/uso.json`.
- Testes (sem placa nem chave): `venv\Scripts\python testes\teste_servico.py`.
