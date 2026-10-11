// Ponte mínima entre o painel e o programa (sem acesso ao computador além disso)
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('desktop', {
  timer: on => ipcRenderer.send('timer', !!on),
  focus: () => ipcRenderer.send('focus-main'),
  tmState: () => ipcRenderer.invoke('tm-state'),
  tmCmd: k => ipcRenderer.send('tm-cmd', k),
  checkUpdate: () => ipcRenderer.invoke('check-update'),
  platform: process.platform
});
