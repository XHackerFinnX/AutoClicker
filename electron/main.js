const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("node:path");
const { spawn } = require("node:child_process");

let win;
let python;
let stdoutBuffer = "";
const pendingEvents = [];

function sendPythonEvent(message) {
    if (win && !win.isDestroyed() && !win.webContents.isLoading()) {
        win.webContents.send("python:event", message);
        return;
    }
    pendingEvents.push(message);
}

function flushPendingEvents() {
    if (!win || win.isDestroyed()) return;
    while (pendingEvents.length) {
        win.webContents.send("python:event", pendingEvents.shift());
    }
}

function createWindow() {
    win = new BrowserWindow({
        width: 1120,
        height: 760,
        minWidth: 900,
        minHeight: 640,
        title: "Python Electron AutoClicker",
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });

    win.loadFile(path.join(__dirname, "..", "renderer", "index.html"));
    win.webContents.on("did-finish-load", flushPendingEvents);
}

function handleStdoutChunk(chunk) {
    stdoutBuffer += chunk;
    const lines = stdoutBuffer.split("\n");
    stdoutBuffer = lines.pop() || "";
    lines.filter(Boolean).forEach((line) => {
        try {
            sendPythonEvent(JSON.parse(line));
        } catch (error) {
            sendPythonEvent({
                event: "error",
                payload: { message: line },
            });
        }
    });
}

function startPython() {
    if (python && !python.killed) return true;
    stdoutBuffer = "";
    const script = path.join(__dirname, "..", "main.py");
    const executable =
        process.env.PYTHON ||
        (process.platform === "win32" ? "python" : "python3");
    python = spawn(executable, [script], { cwd: path.join(__dirname, "..") });

    python.stdout.setEncoding("utf8");
    python.stdout.on("data", handleStdoutChunk);

    python.stderr.setEncoding("utf8");
    python.stderr.on("data", (chunk) => {
        sendPythonEvent({
            event: "error",
            payload: { message: chunk.trim() },
        });
    });

    python.on("error", (error) => {
        sendPythonEvent({
            event: "error",
            payload: {
                message: `Не удалось запустить Python backend: ${error.message}`,
            },
        });
    });

    python.on("exit", (code) => {
        sendPythonEvent({
            event: "status",
            payload: { message: `Python backend stopped (${code})` },
        });
    });
    return true;
}

app.whenReady().then(() => {
    createWindow();
    startPython();

    app.on("activate", () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

ipcMain.handle("python:command", (_event, command, payload = {}) => {
    if (!python || python.killed) return false;
    python.stdin.write(`${JSON.stringify({ command, payload })}\n`);
    return true;
});

ipcMain.handle("python:restart", () => {
    if (python && !python.killed) python.kill();
    return startPython();
});

app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
    python?.kill();
});
