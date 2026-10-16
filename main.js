// Studios Miau — programa de PC (Windows / Mac) (antes chamado Contas ADM)
// Abre o painel numa janela própria. O painel conversa com o Apps Script como sempre.
// Atualização: o programa baixa do Apps Script a versão nova do painel (arquivo "painel") e usa na próxima abertura.
const { app, BrowserWindow, ipcMain, dialog, shell, Menu, Tray, nativeImage } = require('electron');
const path = require('path'), fs = require('fs');
// o nome mudou para Studios Miau, mas a pasta de dados continua a mesma: não perde a configuração, a chave nem o cronômetro
try { app.setPath('userData', path.join(app.getPath('appData'), 'Contas ADM')); } catch (e) { }
const NOME = 'Studios Miau';

const BUNDLED = path.join(__dirname, 'app', 'painel.html');
const CACHE = () => path.join(app.getPath('userData'), 'painel-atual.html');
const ver = h => { const m = String(h).match(/PANELV:(\d+)/) || String(h).match(/const PV=(\d+)/); return m ? +m[1] : 0; };
const inteiro = h => ver(h) > 0 && String(h).length > 100000 && /<\/html>\s*$/i.test(String(h));   // painel completo (não cortado no meio)
// de onde vem o painel novo: direto do GitHub (sem colar nada no Apps Script); se falhar, do Apps Script
const GH_PAINEL = 'https://raw.githubusercontent.com/miausicalproductions-sudo/contas-adm-app/main/app/painel.html';
const GH_API = 'https://api.github.com/repos/miausicalproductions-sudo/contas-adm-app/contents/app/painel.html?ref=main';
const read = f => { try { return fs.readFileSync(f, 'utf8'); } catch (e) { return ''; } };
const pick = () => (ver(read(CACHE())) > ver(read(BUNDLED)) ? CACHE() : BUNDLED);

let win = null, timerWin = null, tray = null, quitting = false;
const HIDDEN = process.argv.includes('--oculto');            // aberto junto com o Windows: começa perto do relógio
const PREFS = () => path.join(app.getPath('userData'), 'prefs.json');
const prefs = () => { try { return JSON.parse(read(PREFS()) || '{}'); } catch (e) { return {}; } };
const savePrefs = o => { try { fs.writeFileSync(PREFS(), JSON.stringify(Object.assign(prefs(), o))); } catch (e) {} };
app.setAppUserModelId('com.studiosmiau.contasadm');          // avisos do Windows com o nome e o ícone do programa
if (!app.requestSingleInstanceLock()) app.quit();
app.on('second-instance', () => showMain());
function showMain() { if (!win) return createWindow(true); if (win.isMinimized()) win.restore(); win.show(); win.focus(); if (Date.now() - lastCheck > 10 * 60 * 1000) setTimeout(() => checkUpdate(), 1500); }

function createWindow(forceShow) {
  win = new BrowserWindow({
    width: 1440, height: 920, minWidth: 380, minHeight: 500, title: NOME,
    icon: path.join(__dirname, 'build', 'icon.png'), backgroundColor: '#f6f5fa', autoHideMenuBar: true, show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, spellcheck: true, backgroundThrottling: false }
  });
  win.once('ready-to-show', () => { if (HIDDEN && !forceShow) return; if (splashWin && !splashWin.isDestroyed()) { splashWin.once('closed', () => { if (win) { win.maximize(); win.show(); } }); return; } win.maximize(); win.show(); });
  win.loadFile(pick());
  // links de fora (chat da IA, Instagram, Drive, WhatsApp) abrem no navegador do computador
  win.webContents.setWindowOpenHandler(({ url }) => { if (/^(https?:|mailto:)/.test(url)) shell.openExternal(url); return { action: 'deny' }; });
  win.webContents.on('will-navigate', (e, url) => { if (/^https?:/.test(url)) { e.preventDefault(); shell.openExternal(url); } });
  win.webContents.once('did-finish-load', () => setTimeout(() => checkUpdate(), 6000));
  win.on('focus', () => { if (Date.now() - lastCheck > 10 * 60 * 1000) checkUpdate(); });
  // fechar = continuar perto do relógio para avisar a hora de postar (Sair de verdade: menu do ícone perto do relógio)
  win.on('close', e => {
    if (quitting || process.platform === 'darwin') return;
    e.preventDefault(); win.hide();
    if (!prefs().avisouBandeja && tray) { tray.displayBalloon && tray.displayBalloon({ title: NOME + ' continua aberto', content: 'Fico aqui perto do relógio para avisar a hora de postar. Para sair de vez: clique com o botão direito no ícone → Sair.' }); savePrefs({ avisouBandeja: 1 }); }
  });
  win.on('closed', () => { win = null; if (timerWin) timerWin.close(); });
}

// Atualização do painel: procura ao abrir, a cada 30 min, ao voltar para a janela e no botão "Procurar atualização" do painel
let lastCheck = 0, checking = false;
async function checkUpdate(manual) {
  if (!win || checking) return { msg: 'procurando…' };
  checking = true; lastCheck = Date.now();
  try {
    let t = ''; const notas = [];
    const pega = (h, de) => { if (!h) return; if (!inteiro(h)) { notas.push(de + ': veio incompleto (' + Math.round(String(h).length / 1024) + ' KB)'); return; } if (ver(h) > ver(t)) t = h; };
    try { const r = await fetch(GH_API, { cache: 'no-store', headers: { Accept: 'application/vnd.github.raw', 'User-Agent': 'StudiosMiau' } }); if (r.ok) pega(await r.text(), 'GitHub'); else notas.push('GitHub API: ' + r.status); }   // 1º: GitHub (sem atraso de cache)
    catch (e) { notas.push('GitHub API: sem conexão'); }
    try { const r = await fetch(GH_PAINEL + '?t=' + Date.now(), { cache: 'no-store' }); if (r.ok) pega(await r.text(), 'GitHub'); else notas.push('GitHub: ' + r.status); }   // 2º: GitHub (cópia rápida, pode atrasar 5 min)
    catch (e) { notas.push('GitHub: sem conexão'); }
    if (!t) {                                            // 2º: o Apps Script (mesmo caminho da sincronização)
      try {
        const j = await win.webContents.executeJavaScript('window.__painelSrc?__painelSrc().catch(e=>({err:String(e)})):null');
        if (j && j.html) pega(j.html, 'Apps Script'); else if (j && j.err) notas.push('Apps Script: ' + j.err);
      } catch (e) { }
    }
    const cur = ver(read(pick())), novo = ver(t);
    if (!t) return { err: 'Não consegui baixar o painel novo agora (' + notas.join(' · ') + '). Tento de novo sozinho em 30 min.' };
    if (novo <= cur) return { ok: 1, cur, novo, msg: 'Já está na versão mais nova (painel v' + cur + ').' };
    fs.writeFileSync(CACHE(), t, 'utf8');
    if (!win.isVisible()) { win.loadFile(CACHE()); return { ok: 1, cur, novo, up: 1 }; }      // programa perto do relógio: atualiza sem perguntar
    const { response } = await dialog.showMessageBox(win, { type: 'info', buttons: ['Atualizar agora', 'Depois'], defaultId: 0, title: NOME, message: 'Chegou uma versão nova do painel (v' + novo + ').', detail: 'Atualizar agora recarrega a tela (nada se perde). Se escolher "Depois", ela entra na próxima vez que abrir o programa.' });
    if (response === 0 && win) win.loadFile(CACHE());
    return { ok: 1, cur, novo, up: response === 0 ? 1 : 0 };
  } catch (e) { return { err: 'Não consegui procurar a atualização (' + (e && e.message || e) + ').' }; }
  finally { checking = false; }
}
ipcMain.handle('check-update', () => checkUpdate(true));
setInterval(() => checkUpdate(), 30 * 60 * 1000);

// cronômetro por cima de todos os programas (abre sem mostrar o programa inteiro)
function openTimer(pick) {
  const h = pick ? Math.min(440, 74 + Math.max(1, (lastCos || []).length) * 34) : 132;
  if (timerWin) { if (pick) timerWin.setSize(Math.max(260, timerWin.getSize()[0]), h); timerWin.show(); timerWin.focus(); return; }
  const wa = require('electron').screen.getPrimaryDisplay().workArea;
  timerWin = new BrowserWindow({
    width: 260, height: h, minWidth: 190, minHeight: 90, frame: false, transparent: true, resizable: true, alwaysOnTop: true,
    x: wa.x + wa.width - 280, y: wa.y + wa.height - h - 20,
    skipTaskbar: false, title: 'Cronômetro', icon: path.join(__dirname, 'build', 'icon.png'), hasShadow: true,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false }
  });
  timerWin.setAlwaysOnTop(true, 'screen-saver'); timerWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  timerWin.loadFile(path.join(__dirname, 'timer.html'));
  timerWin.on('closed', () => { timerWin = null; });
}
ipcMain.on('timer', (e, on) => { if (!on) { if (timerWin) timerWin.close(); return; } openTimer(false); });
ipcMain.on('tm-fit', (e, h) => { if (timerWin && h > 80 && h < 600) { const [w] = timerWin.getSize(); timerWin.setSize(Math.max(190, w), Math.round(h)); } });
// lista de empresas para o cronômetro (lida do painel, que fica aberto escondido perto do relógio)
let lastCos = [];
async function loadCos() {
  if (!win) return lastCos;
  try { const L = JSON.parse(await win.webContents.executeJavaScript('window.__tmCos?__tmCos():"[]"')); if (Array.isArray(L)) lastCos = L; } catch (e) { }
  return lastCos;
}
async function tmRunning() { try { return win ? JSON.parse(await win.webContents.executeJavaScript('window.__tmInfo?__tmInfo():"{}"')) : {}; } catch (e) { return {}; } }
async function refreshTray() { await loadCos(); const t = await tmRunning(); if (tray && process.platform === 'linux') tray.setContextMenu(trayMenu(t)); return t; }
function tmStartCo(id) {                                   // escolhe a empresa no menu → o cronômetro começa e aparece por cima
  if (!win) { createWindow(false); win.webContents.once('did-finish-load', () => setTimeout(() => tmStartCo(id), 1500)); return; }
  win.webContents.executeJavaScript('window.__tmCmd&&__tmCmd(' + JSON.stringify('start:' + id) + ')').catch(() => {});
  openTimer(false); setTimeout(refreshTray, 800);
}
ipcMain.handle('tm-cos', () => loadCos());
ipcMain.handle('tm-state', async () => { try { return win ? JSON.parse(await win.webContents.executeJavaScript('window.__tmInfo?__tmInfo():"{}"')) : {}; } catch (e) { return {}; } });
ipcMain.on('tm-cmd', (e, k) => {
  if (!win || !/^(pause|fin|start|add\d{1,3}|start:[\w-]{1,64})$/.test(k)) return;
  win.webContents.executeJavaScript('window.__tmCmd&&__tmCmd(' + JSON.stringify(k) + ')').catch(() => {});
  setTimeout(refreshTray, 800);
});
ipcMain.on('focus-main', () => showMain());

/* ---------- IA interna (miau-ia) instalada pelo próprio programa: sem .bat ----------
 * O instalador do Windows pergunta se este PC vai rodar a IA (arquivo instalar-ia.flag na pasta do programa);
 * na primeira abertura o programa pergunta se é o PC 1 (principal) ou o PC 2 (apoio) e instala tudo sozinho.
 * Também dá para instalar depois pelo painel: Config → IA local → Instalar a IA interna. */
let iaWin = null;
function iaInstalar(papel) {
  if (process.platform !== 'win32') { dialog.showMessageBox({ type: 'info', title: NOME, message: 'A IA interna só roda no Windows com placa NVIDIA. Neste computador, use as IAs do PC 1 pela rede (Config → IA local).' }); return false; }
  if (iaWin) { iaWin.focus(); return true; }
  const ps = path.join(process.resourcesPath || __dirname, 'local-ai', 'instalar-tudo.ps1'), ps2 = path.join(__dirname, 'local-ai', 'instalar-tudo.ps1'), arq = fs.existsSync(ps) ? ps : ps2;
  iaWin = new BrowserWindow({ width: 760, height: 620, title: 'Instalando a IA interna', icon: path.join(__dirname, 'build', 'icon.png'), autoHideMenuBar: true, webPreferences: { preload: path.join(__dirname, 'preload-ia.js'), contextIsolation: true } });
  iaWin.on('closed', () => { iaWin = null; });
  iaWin.loadFile(path.join(__dirname, 'ia.html'));
  iaWin.webContents.once('did-finish-load', () => {
    const { spawn } = require('child_process');
    const p = spawn('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', arq, '-Papel', papel], { windowsHide: true });
    let buf = '', tok = '';
    const linha = l => { if (/^##TOKEN /.test(l)) tok = l.slice(8).trim(); if (iaWin) iaWin.webContents.send('ia-linha', l); };
    const le = d => { buf += d.toString('utf8'); const L = buf.split(/\r?\n/); buf = L.pop(); L.forEach(linha); };
    p.stdout.on('data', le); p.stderr.on('data', le);
    p.on('close', async code => {
      if (buf) linha(buf);
      const ok = code === 0;
      savePrefs({ iaFeita: ok ? papel : '', iaTentou: Date.now() });
      if (ok && papel === 'pc1' && tok && win) { try { await win.webContents.executeJavaScript(`try{localStorage.miauIA=JSON.stringify({url:'http://127.0.0.1:8765',tok:${JSON.stringify(tok)}});'ok'}catch(e){''}`); } catch (e) { } }
      if (iaWin) iaWin.webContents.send('ia-fim', ok, papel);
    });
  });
  return true;
}
ipcMain.handle('ia-instalar', (e, papel) => iaInstalar(papel === 'pc2' ? 'pc2' : 'pc1'));
async function iaPrimeiraVez() {
  if (process.platform !== 'win32' || prefs().iaFeita || prefs().iaPerguntou) return;
  const flag = path.join(path.dirname(process.execPath), 'instalar-ia.flag');
  if (!fs.existsSync(flag)) return;
  savePrefs({ iaPerguntou: Date.now() });
  const r = await dialog.showMessageBox(win, { type: 'question', title: NOME, message: 'Instalar a IA interna neste computador?', detail: 'Baixa e instala sozinho o Python, as IAs (figurinhas, recorte, transcrição, leitura) e os modelos: uns 15 GB e de 10 a 40 minutos. Precisa de placa de vídeo NVIDIA.\n\nPC 1 = o computador principal (guarda a chave do Claude).\nPC 2 = computador de apoio (ajuda o PC 1 pela rede).', buttons: ['Este é o PC 1 (principal)', 'Este é o PC 2 (apoio)', 'Agora não'], defaultId: 1, cancelId: 2 });
  if (r.response === 0) iaInstalar('pc1'); else if (r.response === 1) iaInstalar('pc2');
}

/* vídeo de abertura (logo animado, fundo verde já retirado): só ao abrir pela pessoa, não quando liga junto com o Windows */
let splashWin = null;
function splash() {
  if (HIDDEN || prefs().abertura === 0) return;
  try {
    splashWin = new BrowserWindow({ width: 720, height: 540, frame: false, resizable: false, center: true, backgroundColor: '#1d1b2c', show: false, skipTaskbar: false, title: NOME, icon: path.join(__dirname, 'build', 'icon.png') });
    splashWin.loadFile(path.join(__dirname, 'splash.html'));
    splashWin.once('ready-to-show', () => splashWin && splashWin.show());
    splashWin.on('closed', () => { splashWin = null; });
  } catch (e) { splashWin = null; }
}

app.whenReady().then(() => {
  splash();
  Menu.setApplicationMenu(process.platform === 'darwin' ? Menu.buildFromTemplate([{ role: 'appMenu' }, { role: 'editMenu' }, { role: 'viewMenu' }, { role: 'windowMenu' }]) : null);
  createWindow();
  makeTray();
  setStart(prefs().iniciar !== 0);                          // abre junto com o Windows (padrão); regrava o caminho caso o programa tenha mudado de pasta
  if (win) win.webContents.on('did-finish-load', () => setTimeout(refreshTray, 3000));
  if (win) win.webContents.once('did-finish-load', () => setTimeout(iaPrimeiraVez, 2500));
  setInterval(refreshTray, 2 * 60 * 1000);
  app.on('activate', () => { if (!BrowserWindow.getAllWindows().length) createWindow(true); else showMain(); });
});
app.on('before-quit', () => { quitting = true; });
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });

// ícone perto do relógio
function setStart(on) {
  savePrefs({ iniciar: on ? 1 : 0 });
  try { app.setLoginItemSettings({ openAtLogin: !!on, args: ['--oculto'] }); } catch (e) {}
  if (tray) refreshTray();
}
function trayMenu(t) {
  t = t || {};
  const fmt = ms => { const m = Math.floor((ms || 0) / 60000); return (m >= 60 ? Math.floor(m / 60) + 'h' : '') + String(m % 60).padStart(m >= 60 ? 2 : 1, '0') + 'min'; };
  const cron = t.on
    ? { label: 'Cronômetro: ' + (t.n || '') + ' · ' + fmt(t.ms) + (t.paused ? ' (pausado)' : ''), click: () => openTimer(false) }
    : { label: 'Cronômetro', submenu: lastCos.length ? [{ label: 'De qual empresa?', enabled: false }, ...lastCos.slice(0, 25).map(c => ({ label: c.n, click: () => tmStartCo(c.id) }))] : [{ label: 'Escolher a empresa…', click: () => openTimer(true) }] };
  return Menu.buildFromTemplate([
    { label: 'Abrir o ' + NOME, click: showMain },
    cron,
    { type: 'separator' },
    { label: 'Procurar atualização', click: async () => { showMain(); const r = await checkUpdate(true); if (r && (r.err || r.msg) && win) dialog.showMessageBox(win, { type: r.err ? 'warning' : 'info', message: r.err || r.msg, title: NOME }); } },
    { label: 'Abrir junto com o Windows', type: 'checkbox', checked: prefs().iniciar !== 0, click: m => setStart(m.checked) },
    { label: 'Vídeo de abertura', type: 'checkbox', checked: prefs().abertura !== 0, click: m => savePrefs({ abertura: m.checked ? 1 : 0 }) },
    { type: 'separator' },
    { label: 'Sair', click: () => { quitting = true; app.quit(); } }
  ]);
}
function makeTray() {
  if (process.platform === 'darwin') return;
  try {
    const img = nativeImage.createFromPath(path.join(__dirname, 'build', 'icon.png')).resize({ width: 32, height: 32 });
    tray = new Tray(img); tray.setToolTip(NOME + ' — avisos na hora de postar');
    tray.on('click', showMain);
    // botão direito: o menu é montado na hora, com as empresas e o cronômetro atualizados
    if (process.platform === 'linux') tray.setContextMenu(trayMenu());
    else tray.on('right-click', async () => { let t = {}; try { t = await Promise.race([refreshTray(), new Promise(ok => setTimeout(() => ok({}), 700))]); } catch (e) { } tray.popUpContextMenu(trayMenu(t)); });
  } catch (e) { tray = null; }
}
