const state = {
    macros: [],
    selectedId: null,
    actions: [{ type: "click", button: "left" }],
    running: new Set(),
    recording: false,
};
const buttons = ["left", "middle", "right"];
const types = ["click", "doubleClick", "press", "move", "wait"];

const elements = {
    list: document.querySelector("#macroList"),
    form: document.querySelector("#macroForm"),
    id: document.querySelector("#macroId"),
    name: document.querySelector("#name"),
    hotkey: document.querySelector("#hotkey"),
    repeat: document.querySelector("#repeat"),
    intervalMs: document.querySelector("#intervalMs"),
    actionsList: document.querySelector("#actionsList"),
    actionsPreview: document.querySelector("#actionsPreview"),
    status: document.querySelector("#status"),
    newMacro: document.querySelector("#newMacro"),
    runMacro: document.querySelector("#runMacro"),
    stopMacro: document.querySelector("#stopMacro"),
    stopAll: document.querySelector("#stopAll"),
    deleteMacro: document.querySelector("#deleteMacro"),
    addAction: document.querySelector("#addAction"),
    recordMacro: document.querySelector("#recordMacro"),
    restartBackend: document.querySelector("#restartBackend"),
    exportSelected: document.querySelector("#exportSelected"),
    exportAll: document.querySelector("#exportAll"),
    importMacros: document.querySelector("#importMacros"),
    resetDemo: document.querySelector("#resetDemo"),
};

function setStatus(message) {
    elements.status.textContent = `${new Date().toLocaleTimeString()} — ${message}`;
}
function cloneActions(actions) {
    return JSON.parse(JSON.stringify(actions));
}
function defaultAction(type = "click") {
    return type === "move"
        ? { type, x: 0, y: 0 }
        : type === "wait"
          ? { type, durationMs: 500 }
          : type === "press"
            ? { type, key: "space" }
            : { type, button: "left" };
}

function validateMacro(macro) {
    if (!macro.name) throw new Error("Название обязательно");
    if (!Number.isInteger(macro.repeat) || macro.repeat < 1)
        throw new Error("Повторы должны быть положительным целым числом");
    if (!Number.isInteger(macro.intervalMs) || macro.intervalMs < 0)
        throw new Error("Пауза должна быть неотрицательным целым числом");
    if (!Array.isArray(macro.actions) || macro.actions.length === 0)
        throw new Error("Добавьте хотя бы одно действие");
    macro.actions.forEach((action, index) => {
        if (!types.includes(action.type))
            throw new Error(`Действие #${index + 1}: неизвестный тип`);
        if (
            ["click", "doubleClick"].includes(action.type) &&
            !buttons.includes(action.button)
        )
            throw new Error(`Действие #${index + 1}: некорректная кнопка мыши`);
        if (
            action.type === "move" &&
            (!Number.isInteger(action.x) || !Number.isInteger(action.y))
        )
            throw new Error(
                `Действие #${index + 1}: x/y должны быть целыми числами`,
            );
        if (
            action.type === "wait" &&
            (!Number.isInteger(action.durationMs) || action.durationMs < 0)
        )
            throw new Error(
                `Действие #${index + 1}: durationMs должен быть неотрицательным целым числом`,
            );
        if (action.type === "press" && !String(action.key || "").trim())
            throw new Error(`Действие #${index + 1}: key обязательна`);
    });
}

function renderList() {
    elements.list.innerHTML = "";
    state.macros.forEach((macro) => {
        const card = document.createElement("article");
        card.className = `macro-card ${macro.id === state.selectedId ? "active" : ""} ${state.running.has(macro.id) ? "running" : ""}`;
        card.innerHTML = `<strong></strong><span></span>`;
        card.querySelector("strong").textContent = macro.name;
        card.querySelector("span").textContent =
            `${macro.hotkey || "без хоткея"} · ${macro.actions?.length || 0} действий${state.running.has(macro.id) ? " · выполняется" : ""}`;
        card.addEventListener("click", () => selectMacro(macro.id));
        elements.list.appendChild(card);
    });
}

function selectMacro(id) {
    const macro = state.macros.find((item) => item.id === id);
    if (!macro) return;
    state.selectedId = id;
    elements.id.value = macro.id;
    elements.name.value = macro.name || "";
    elements.hotkey.value = macro.hotkey || "";
    elements.repeat.value = macro.repeat || 1;
    elements.intervalMs.value = macro.intervalMs || 0;
    state.actions = cloneActions(macro.actions || [defaultAction()]);
    renderList();
    renderActions();
}

function newMacro() {
    state.selectedId = null;
    elements.form.reset();
    elements.id.value = "";
    elements.repeat.value = 1;
    elements.intervalMs.value = 100;
    state.actions = [defaultAction()];
    renderList();
    renderActions();
}

function readForm() {
    const macro = {
        id: elements.id.value,
        name: elements.name.value.trim(),
        hotkey: elements.hotkey.value.trim(),
        repeat: Number(elements.repeat.value),
        intervalMs: Number(elements.intervalMs.value),
        actions: cloneActions(state.actions),
    };
    validateMacro(macro);
    return macro;
}

function input(type, value, onInput) {
    const el = document.createElement("input");
    el.type = type;
    el.value = value;
    el.addEventListener("input", () => onInput(el));
    return el;
}
function select(options, value, onChange) {
    const el = document.createElement("select");
    options.forEach((option) => {
        const opt = document.createElement("option");
        opt.value = option;
        opt.textContent = option;
        el.appendChild(opt);
    });
    el.value = value;
    el.addEventListener("change", () => onChange(el));
    return el;
}

function renderActionParams(action, index, container) {
    if (["click", "doubleClick"].includes(action.type))
        container.append(
            label(
                "Кнопка",
                select(buttons, action.button || "left", (el) => {
                    state.actions[index].button = el.value;
                    updatePreview();
                }),
            ),
        );
    if (action.type === "press")
        container.append(
            label(
                "Клавиша",
                input("text", action.key || "space", (el) => {
                    state.actions[index].key = el.value;
                    updatePreview();
                }),
            ),
        );
    if (action.type === "wait")
        container.append(
            label(
                "Длительность, мс",
                input("number", action.durationMs ?? 500, (el) => {
                    state.actions[index].durationMs = Number(el.value);
                    updatePreview();
                }),
            ),
        );
    if (action.type === "move") {
        container.append(
            label(
                "X",
                input("number", action.x ?? 0, (el) => {
                    state.actions[index].x = Number(el.value);
                    updatePreview();
                }),
            ),
        );
        container.append(
            label(
                "Y",
                input("number", action.y ?? 0, (el) => {
                    state.actions[index].y = Number(el.value);
                    updatePreview();
                }),
            ),
        );
    }
}
function label(text, child) {
    const wrapper = document.createElement("label");
    wrapper.textContent = text;
    wrapper.appendChild(child);
    return wrapper;
}

function renderActions() {
    elements.actionsList.innerHTML = "";
    state.actions.forEach((action, index) => {
        const row = document.createElement("article");
        row.className = "action-row";
        row.draggable = true;
        row.dataset.index = String(index);
        const handle = document.createElement("span");
        handle.className = "drag-handle";
        handle.textContent = "☰";
        const typeSelect = select(types, action.type, (el) => {
            state.actions[index] = defaultAction(el.value);
            renderActions();
        });
        const params = document.createElement("div");
        params.className = "action-params";
        renderActionParams(action, index, params);
        const controls = document.createElement("div");
        controls.className = "mini-actions";
        [
            ["↑", () => moveAction(index, index - 1)],
            ["↓", () => moveAction(index, index + 1)],
            [
                "Дубль",
                () => {
                    state.actions.splice(
                        index + 1,
                        0,
                        cloneActions([action])[0],
                    );
                    renderActions();
                },
            ],
            [
                "Удалить",
                () => {
                    state.actions.splice(index, 1);
                    if (!state.actions.length)
                        state.actions.push(defaultAction());
                    renderActions();
                },
            ],
        ].forEach(([text, fn]) => {
            const b = document.createElement("button");
            b.type = "button";
            b.textContent = text;
            b.addEventListener("click", fn);
            controls.appendChild(b);
        });
        row.addEventListener("dragstart", (event) =>
            event.dataTransfer.setData("text/plain", String(index)),
        );
        row.addEventListener("dragover", (event) => event.preventDefault());
        row.addEventListener("drop", (event) => {
            event.preventDefault();
            moveAction(Number(event.dataTransfer.getData("text/plain")), index);
        });
        row.append(handle, typeSelect, params, controls);
        elements.actionsList.appendChild(row);
    });
    updatePreview();
}
function moveAction(from, to) {
    if (to < 0 || to >= state.actions.length || from === to) return;
    const [item] = state.actions.splice(from, 1);
    state.actions.splice(to, 0, item);
    renderActions();
}
function updatePreview() {
    elements.actionsPreview.value = JSON.stringify(state.actions, null, 2);
}

function downloadJson(filename, data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
}

async function importMacros(file) {
    const text = await file.text();
    const parsed = JSON.parse(text);
    const macros = Array.isArray(parsed) ? parsed : parsed.macros;
    if (!Array.isArray(macros))
        throw new Error(
            "Файл должен содержать массив макросов или объект { macros }",
        );
    await window.autoclicker.send("import", { macros });
}

elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
        const macro = readForm();
        await window.autoclicker.send("save", macro);
        setStatus("Макрос отправлен на сохранение");
    } catch (error) {
        setStatus(`Ошибка валидации: ${error.message}`);
    }
});
elements.newMacro.addEventListener("click", newMacro);
elements.addAction.addEventListener("click", () => {
    state.actions.push(defaultAction());
    renderActions();
});
elements.runMacro.addEventListener("click", () => {
    const id = elements.id.value;
    if (id) window.autoclicker.send("run", { id });
});
elements.stopMacro.addEventListener("click", () => {
    const id = elements.id.value;
    if (id) window.autoclicker.send("stop", { id });
});
elements.stopAll.addEventListener("click", () =>
    window.autoclicker.send("stop", {}),
);
elements.restartBackend.addEventListener("click", async () => {
    await window.autoclicker.restartBackend();
    setStatus("Перезапуск backend запрошен");
});
elements.recordMacro.addEventListener("click", () =>
    window.autoclicker.send(
        state.recording ? "record:stop" : "record:start",
        {},
    ),
);
elements.deleteMacro.addEventListener("click", () => {
    const id = elements.id.value;
    if (id) window.autoclicker.send("delete", { id });
    newMacro();
});
elements.exportSelected.addEventListener("click", () => {
    const macro = state.macros.find((item) => item.id === state.selectedId);
    if (macro) downloadJson(`${macro.id}.json`, macro);
});
elements.exportAll.addEventListener("click", () =>
    downloadJson("macros.json", { macros: state.macros }),
);
elements.importMacros.addEventListener("change", async () => {
    try {
        if (elements.importMacros.files[0])
            await importMacros(elements.importMacros.files[0]);
        setStatus("Макросы импортированы");
    } catch (error) {
        setStatus(`Ошибка импорта: ${error.message}`);
    } finally {
        elements.importMacros.value = "";
    }
});
elements.resetDemo.addEventListener("click", () =>
    window.autoclicker.send("reset-demo", {}),
);
elements.actionsPreview.addEventListener("change", () => {
    try {
        const actions = JSON.parse(elements.actionsPreview.value);
        if (!Array.isArray(actions))
            throw new Error("JSON должен быть массивом");
        state.actions = actions;
        validateMacro({
            id: "preview",
            name: "preview",
            hotkey: "",
            repeat: 1,
            intervalMs: 0,
            actions,
        });
        renderActions();
        setStatus("JSON действий применён");
    } catch (error) {
        setStatus(`Ошибка JSON: ${error.message}`);
    }
});

window.autoclicker.onEvent((message) => {
    const { event, payload } = message;
    if (event === "ready" || event === "macros") {
        state.macros = payload.macros || [];
        if (payload.selectedId) state.selectedId = payload.selectedId;
        const currentExists = state.macros.some(
            (macro) => macro.id === state.selectedId,
        );
        if (!currentExists && state.macros[0]) selectMacro(state.macros[0].id);
        else {
            renderList();
            if (state.selectedId) selectMacro(state.selectedId);
        }
        setStatus(
            event === "ready"
                ? `Готово. Аварийный хоткей: ${payload.stopAllHotkey || "ctrl+alt+esc"}`
                : "Список макросов обновлён",
        );
    }
    if (event === "macro-started") {
        state.running.add(payload.id);
        renderList();
        setStatus(`Макрос запущен: ${payload.id}`);
    }
    if (event === "macro-progress")
        setStatus(
            `Макрос ${payload.id}: повтор ${payload.current}/${payload.total}`,
        );
    if (event === "macro-finished") {
        state.running.delete(payload.id);
        renderList();
        setStatus(
            payload.stopped
                ? `Макрос остановлен: ${payload.id}`
                : `Макрос завершён: ${payload.id}`,
        );
    }
    if (event === "recording-started") {
        state.recording = true;
        elements.recordMacro.textContent = "Остановить запись";
        setStatus("Запись началась");
    }
    if (event === "recording-updated" || event === "recording-finished") {
        state.actions = payload.actions || [];
        renderActions();
        if (event === "recording-finished") {
            state.recording = false;
            elements.recordMacro.textContent = "Записать";
            setStatus("Запись завершена и вставлена в редактор");
        }
    }
    if (event === "status" || event === "error") setStatus(payload.message);
});

newMacro();
window.autoclicker.send("list");
