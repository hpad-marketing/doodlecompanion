const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('bunny',{
  send:(ch,data)=>ipcRenderer.send(ch,data),
  invoke:(ch,data)=>ipcRenderer.invoke(ch,data),
  on:(ch,fn)=>ipcRenderer.on(ch,(_e,data)=>fn(data))
});
