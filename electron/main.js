const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("node:path");
const { spawn } = require("node:child_process");

let win;
let python;

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
}

function startPython() {
    const script = path.join(__dirname, "..", "main.py");
    const executable =
        process.env.PYTHON ||
        (process.platform === "win32" ? "python" : "python3");
    python = spawn(executable, [script], { cwd: path.join(__dirname, "..") });

    python.stdout.setEncoding("utf8");
    python.stdout.on("data", (chunk) => {
        chunk
            .split("\n")
            .filter(Boolean)
            .forEach((line) => {
                try {
                    win?.webContents.send("python:event", JSON.parse(line));
                } catch (error) {
                    win?.webContents.send("python:event", {
                        event: "error",
                        payload: { message: line },
                    });
                }
            });
    });

    python.stderr.setEncoding("utf8");
    python.stderr.on("data", (chunk) => {
        win?.webContents.send("python:event", {
            event: "error",
            payload: { message: chunk.trim() },
        });
    });

    python.on("exit", (code) => {
        win?.webContents.send("python:event", {
            event: "status",
            payload: { message: `Python backend stopped (${code})` },
        });
    });
}

app.whenReady().then(() => {
    startPython();
    createWindow();

    app.on("activate", () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

ipcMain.handle("python:command", (_event, command, payload = {}) => {
    if (!python || python.killed) return false;
    python.stdin.write(`${JSON.stringify({ command, payload })}\n`);
    return true;
});

app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
    python?.kill();
});
