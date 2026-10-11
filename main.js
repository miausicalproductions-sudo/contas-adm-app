// Contas ADM — programa de PC (Windows / Mac)
// Abre o painel numa janela própria. O painel conversa com o Apps Script como sempre.
// Atualização: o programa baixa do Apps Script a versão nova do painel (arquivo "painel") e usa na próxima abertura.
const { app, BrowserWindow, ipcMain, dialog, shell, Menu, Tray, nativeImage } = require('electron');
const path = require('path'), fs = require('fs');

const BUNDLED = path.join(__dirname, 'app', 'painel.html');
const CACHE = () => path.join(app.getPath('userData'), 'painel-atual.html');
const ver = h => { const m = String(h).match(/PANELV:(\d+)/); return m ? +m[1] : 0; };
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
    width: 1440, height: 920, minWidth: 380, minHeight: 500, title: 'Contas ADM',
    icon: path.join(__dirname, 'build', 'icon.png'), backgroundColor: '#f6f5fa', autoHideMenuBar: true, show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, spellcheck: true, backgroundThrottling: false }
  });
  win.once('ready-to-show', () => { if (HIDDEN && !forceShow) return; win.maximize(); win.show(); });
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
    if (!prefs().avisouBandeja && tray) { tray.displayBalloon && tray.displayBalloon({ title: 'Contas ADM continua aberto', content: 'Fico aqui perto do relógio para avisar a hora de postar. Para sair de vez: clique com o botão direito no ícone → Sair.' }); savePrefs({ avisouBandeja: 1 }); }
  });
  win.on('closed', () => { win = null; if (timerWin) timerWin.close(); });
}

// Atualização do painel: procura ao abrir, a cada 30 min, ao voltar para a janela e no botão "Procurar atualização" do painel
let lastCheck = 0, checking = false;
async function checkUpdate(manual) {
  if (!win || checking) return { msg: 'procurando…' };
  checking = true; lastCheck = Date.now();
  try {
    const url = await win.webContents.executeJavaScript("(()=>{try{return (JSON.parse(localStorage.adm2||'{}').cfg||{}).url||''}catch(e){return ''}})()");
    if (!/^https:\/\/script\.google\.com\/.+\/exec$/.test(url)) return { err: 'O endereço do Apps Script em Config não termina em /exec.' };
    const r = await fetch(url + '?src=1', { redirect: 'follow' }), t = await r.text();
    const cur = ver(read(pick())), novo = ver(t);
    if (!novo || !t.includes('</html>')) return { err: 'O Apps Script não entregou o painel (confira se o arquivo "painel" existe e se a Nova versão foi implantada). Resposta: ' + r.status };
    if (novo <= cur) return { ok: 1, cur, novo, msg: 'Já está na versão mais nova (painel v' + cur + ').' };
    fs.writeFileSync(CACHE(), t, 'utf8');
    if (!win.isVisible()) { win.loadFile(CACHE()); return { ok: 1, cur, novo, up: 1 }; }      // programa perto do relógio: atualiza sem perguntar
    const { response } = await dialog.showMessageBox(win, { type: 'info', buttons: ['Atualizar agora', 'Depois'], defaultId: 0, title: 'Contas ADM', message: 'Chegou uma versão nova do painel (v' + novo + ').', detail: 'Atualizar agora recarrega a tela (nada se perde). Se escolher "Depois", ela entra na próxima vez que abrir o programa.' });
    if (response === 0 && win) win.loadFile(CACHE());
    return { ok: 1, cur, novo, up: response === 0 ? 1 : 0 };
  } catch (e) { return { err: 'Sem conexão com o Apps Script agora (' + (e && e.message || e) + ').' }; }
  finally { checking = false; }
}
ipcMain.handle('check-update', () => checkUpdate(true));
setInterval(() => checkUpdate(), 30 * 60 * 1000);

// cronômetro por cima de todos os programas
ipcMain.on('timer', (e, on) => {
  if (!on) { if (timerWin) timerWin.close(); return; }
  if (timerWin) { timerWin.show(); timerWin.focus(); return; }
  timerWin = new BrowserWindow({
    width: 260, height: 132, minWidth: 190, minHeight: 90, frame: false, transparent: true, resizable: true, alwaysOnTop: true,
    skipTaskbar: false, title: 'Cronômetro', icon: path.join(__dirname, 'build', 'icon.png'), hasShadow: true,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false }
  });
  timerWin.setAlwaysOnTop(true, 'screen-saver'); timerWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  timerWin.loadFile(path.join(__dirname, 'timer.html'));
  timerWin.on('closed', () => { timerWin = null; });
});
ipcMain.handle('tm-state', async () => { try { return win ? JSON.parse(await win.webContents.executeJavaScript('window.__tmInfo?__tmInfo():"{}"')) : {}; } catch (e) { return {}; } });
ipcMain.on('tm-cmd', (e, k) => { if (win && /^(pause|fin|start|add\d{1,3})$/.test(k)) win.webContents.executeJavaScript('window.__tmCmd&&__tmCmd(' + JSON.stringify(k) + ')').catch(() => {}); });
ipcMain.on('focus-main', () => showMain());

app.whenReady().then(() => {
  Menu.setApplicationMenu(process.platform === 'darwin' ? Menu.buildFromTemplate([{ role: 'appMenu' }, { role: 'editMenu' }, { role: 'viewMenu' }, { role: 'windowMenu' }]) : null);
  createWindow();
  makeTray();
  if (prefs().iniciar === undefined) setStart(true);         // primeira vez: já abre junto com o Windows (dá para desligar no ícone)
  app.on('activate', () => { if (!BrowserWindow.getAllWindows().length) createWindow(true); else showMain(); });
});
app.on('before-quit', () => { quitting = true; });
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });

// ícone perto do relógio
function setStart(on) {
  savePrefs({ iniciar: on ? 1 : 0 });
  try { app.setLoginItemSettings({ openAtLogin: !!on, args: ['--oculto'] }); } catch (e) {}
  if (tray) tray.setContextMenu(trayMenu());
}
function trayMenu() {
  return Menu.buildFromTemplate([
    { label: 'Abrir o Contas ADM', click: showMain },
    { label: 'Procurar atualização', click: async () => { showMain(); const r = await checkUpdate(true); if (r && (r.err || r.msg) && win) dialog.showMessageBox(win, { type: r.err ? 'warning' : 'info', message: r.err || r.msg, title: 'Contas ADM' }); } },
    { label: 'Cronômetro', click: () => { showMain(); if (win) win.webContents.executeJavaScript('window.__tmCmd&&__tmCmd("start")').catch(() => {}); } },
    { type: 'separator' },
    { label: 'Abrir junto com o Windows', type: 'checkbox', checked: prefs().iniciar !== 0, click: m => setStart(m.checked) },
    { type: 'separator' },
    { label: 'Sair', click: () => { quitting = true; app.quit(); } }
  ]);
}
function makeTray() {
  if (process.platform === 'darwin') return;
  try {
    const img = nativeImage.createFromPath(path.join(__dirname, 'build', 'icon.png')).resize({ width: 32, height: 32 });
    tray = new Tray(img); tray.setToolTip('Contas ADM — avisos na hora de postar');
    tray.setContextMenu(trayMenu()); tray.on('click', showMain);
  } catch (e) { tray = null; }
}
