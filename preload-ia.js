const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('ia', { on: f => ipcRenderer.on('ia-linha', (e, l) => f(l)), done: f => ipcRenderer.on('ia-fim', (e, ok, papel) => f(ok, papel)) });
