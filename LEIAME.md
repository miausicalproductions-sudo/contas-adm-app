# Contas ADM — programas

- `app/painel.html` — o painel (o mesmo HTML usado no PC e no arquivo "painel" do Apps Script).
- `main.js`, `preload.js`, `timer.html` — programa de PC (Electron): janela própria, cronômetro por cima de tudo, atualização do painel pelo Apps Script.
- `mobile/` + `capacitor.config.json` — app Android (Capacitor).
- `.github/workflows/build.yml` — a cada envio, o GitHub monta o instalador do Windows e o APK do Android e publica em **Releases → programas**. O Mac é montado pelo botão "Run workflow" marcando a opção do Mac.

Para atualizar só o painel, não precisa remontar: troque o arquivo "painel" no Apps Script; os programas baixam a versão nova sozinhos.
