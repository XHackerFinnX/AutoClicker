const state = { macros: [], selectedId: null };

const elements = {
    list: document.querySelector("#macroList"),
    form: document.querySelector("#macroForm"),
    id: document.querySelector("#macroId"),
    name: document.querySelector("#name"),
    hotkey: document.querySelector("#hotkey"),
    repeat: document.querySelector("#repeat"),
    intervalMs: document.querySelector("#intervalMs"),
    actions: document.querySelector("#actions"),
    status: document.querySelector("#status"),
    newMacro: document.querySelector("#newMacro"),
    runMacro: document.querySelector("#runMacro"),
    stopMacro: document.querySelector("#stopMacro"),
    deleteMacro: document.querySelector("#deleteMacro"),
};

const defaultActions = [{ type: "click", button: "left" }];

function setStatus(message) {
    elements.status.textContent = `${new Date().toLocaleTimeString()} — ${message}`;
}

function renderList() {
    elements.list.innerHTML = "";
    state.macros.forEach((macro) => {
        const card = document.createElement("article");
        card.className = `macro-card ${macro.id === state.selectedId ? "active" : ""}`;
        card.innerHTML = `<strong></strong><span></span>`;
        card.querySelector("strong").textContent = macro.name;
        card.querySelector("span").textContent =
            `${macro.hotkey || "без хоткея"} · ${macro.actions?.length || 0} действий`;
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
    elements.actions.value = JSON.stringify(
        macro.actions || defaultActions,
        null,
        2,
    );
    renderList();
}

function newMacro() {
    state.selectedId = null;
    elements.form.reset();
    elements.id.value = "";
    elements.repeat.value = 1;
    elements.intervalMs.value = 100;
    elements.actions.value = JSON.stringify(defaultActions, null, 2);
    renderList();
}

function readForm() {
    return {
        id: elements.id.value,
        name: elements.name.value.trim(),
        hotkey: elements.hotkey.value.trim(),
        repeat: Number(elements.repeat.value || 1),
        intervalMs: Number(elements.intervalMs.value || 0),
        actions: JSON.parse(elements.actions.value || "[]"),
    };
}

elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
        const macro = readForm();
        await window.autoclicker.send("save", macro);
        state.selectedId = macro.id;
        setStatus("Макрос сохранён");
    } catch (error) {
        setStatus(`Ошибка JSON в действиях: ${error.message}`);
    }
});

elements.newMacro.addEventListener("click", newMacro);
elements.runMacro.addEventListener("click", () => {
    const id = elements.id.value;
    if (id) window.autoclicker.send("run", { id });
});
elements.stopMacro.addEventListener("click", () => {
    const id = elements.id.value;
    if (id) window.autoclicker.send("stop", { id });
});

elements.deleteMacro.addEventListener("click", () => {
    const id = elements.id.value;
    if (id) window.autoclicker.send("delete", { id });
    newMacro();
});

window.autoclicker.onEvent((message) => {
    const { event, payload } = message;
    if (event === "ready" || event === "macros") {
        state.macros = payload.macros || [];
        const currentExists = state.macros.some(
            (macro) => macro.id === state.selectedId,
        );
        if (!currentExists && state.macros[0]) {
            selectMacro(state.macros[state.macros.length - 1].id);
        } else {
            renderList();
        }
        setStatus("Готово");
    }
    if (event === "macro-started") setStatus(`Макрос запущен: ${payload.id}`);
    if (event === "macro-finished")
        setStatus(
            payload.stopped
                ? `Макрос остановлен: ${payload.id}`
                : `Макрос завершён: ${payload.id}`,
        );
    if (event === "status" || event === "error") setStatus(payload.message);
});

newMacro();
window.autoclicker.send("list");
