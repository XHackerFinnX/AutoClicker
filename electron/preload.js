const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("autoclicker", {
    send(command, payload) {
        return ipcRenderer.invoke("python:command", command, payload);
    },
    onEvent(callback) {
        const listener = (_event, message) => callback(message);
        ipcRenderer.on("python:event", listener);
        return () => ipcRenderer.removeListener("python:event", listener);
    },
});
