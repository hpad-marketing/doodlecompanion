const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('DoodleDesktop3D', {
  checkForUpdates: () => ipcRenderer.invoke('ds3d:check-updates'),
  closeWindow: () => ipcRenderer.send('ds3d:close-window'),
});
