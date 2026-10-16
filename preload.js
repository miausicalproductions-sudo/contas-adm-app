// Ponte mínima entre o painel e o programa (sem acesso ao computador além disso)
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('desktop', {
  timer: on => ipcRenderer.send('timer', !!on),
  focus: () => ipcRenderer.send('focus-main'),
  tmState: () => ipcRenderer.invoke('tm-state'),
  tmCmd: k => ipcRenderer.send('tm-cmd', k),
  tmCos: () => ipcRenderer.invoke('tm-cos'),
  tmFit: h => ipcRenderer.send('tm-fit', h),
  checkUpdate: () => ipcRenderer.invoke('check-update'),
  iaInstalar: papel => ipcRenderer.invoke('ia-instalar', papel),
  fontes: () => ipcRenderer.invoke('fontes-lista'),
  fonteLer: p => ipcRenderer.invoke('fonte-ler', p),
  platform: process.platform
});
