"""JSON-lines Python backend for the Electron autoclicker."""

from __future__ import annotations

import importlib
import json
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

pyautogui = importlib.import_module("pyautogui") if importlib.util.find_spec("pyautogui") else None
if importlib.util.find_spec("pynput"):
    keyboard = importlib.import_module("pynput.keyboard")
    mouse = importlib.import_module("pynput.mouse")
else:
    keyboard = None
    mouse = None

DATA_DIR = Path(__file__).resolve().parent / "data"
MACROS_FILE = DATA_DIR / "macros.json"
ALLOWED_ACTIONS = {"click", "doubleClick", "press", "move", "wait"}
ALLOWED_BUTTONS = {"left", "middle", "right"}
STOP_ALL_HOTKEY = "<ctrl>+<alt>+<esc>"

if pyautogui is not None:
    pyautogui.FAILSAFE = True


class ValidationError(ValueError):
    """Raised when a macro or action has an invalid shape."""


def emit(event: str, payload: dict[str, Any] | None = None) -> None:
    print(json.dumps({"event": event, "payload": payload or {}}, ensure_ascii=False), flush=True)


def require_int(value: Any, field_name: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field_name}: ожидается целое число")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{field_name}: значение должно быть не меньше {minimum}")
    return value


def validate_action(action: Any, index: int) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ValidationError(f"Действие #{index + 1}: ожидается объект")
    action_type = action.get("type")
    if action_type not in ALLOWED_ACTIONS:
        allowed = ", ".join(sorted(ALLOWED_ACTIONS))
        raise ValidationError(f"Действие #{index + 1}: неизвестный type '{action_type}', допустимо: {allowed}")

    normalized: dict[str, Any] = {"type": action_type}
    if action_type in {"click", "doubleClick"}:
        button = action.get("button", "left")
        if button not in ALLOWED_BUTTONS:
            raise ValidationError(f"Действие #{index + 1}: button должен быть left, middle или right")
        normalized["button"] = button
    elif action_type == "move":
        if "x" not in action or "y" not in action:
            raise ValidationError(f"Действие #{index + 1}: для move обязательны x и y")
        normalized["x"] = require_int(action.get("x"), f"Действие #{index + 1}.x")
        normalized["y"] = require_int(action.get("y"), f"Действие #{index + 1}.y")
    elif action_type == "wait":
        normalized["durationMs"] = require_int(action.get("durationMs"), f"Действие #{index + 1}.durationMs", 0)
    elif action_type == "press":
        key = action.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ValidationError(f"Действие #{index + 1}: для press обязательна непустая key")
        normalized["key"] = key.strip()
    return normalized


def validate_macro(macro: Any) -> dict[str, Any]:
    if not isinstance(macro, dict):
        raise ValidationError("Макрос должен быть объектом")
    name = macro.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name: обязательное непустое поле")
    repeat = require_int(macro.get("repeat"), "repeat", 1)
    interval = require_int(macro.get("intervalMs"), "intervalMs", 0)
    actions = macro.get("actions")
    if not isinstance(actions, list):
        raise ValidationError("actions: ожидается массив")
    if not actions:
        raise ValidationError("actions: добавьте хотя бы одно действие")
    macro_id = macro.get("id")
    if macro_id is not None and not isinstance(macro_id, str):
        raise ValidationError("id: ожидается строка")
    hotkey = macro.get("hotkey", "")
    if hotkey is None:
        hotkey = ""
    if not isinstance(hotkey, str):
        raise ValidationError("hotkey: ожидается строка")
    return {
        "id": macro_id.strip() if isinstance(macro_id, str) else "",
        "name": name.strip(),
        "hotkey": hotkey.strip(),
        "repeat": repeat,
        "intervalMs": interval,
        "actions": [validate_action(action, index) for index, action in enumerate(actions)],
    }
    

@dataclass
class MacroStore:
    path: Path = MACROS_FILE
    macros: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def load(self) -> list[dict[str, Any]]:
        with self._lock:
            if self.path.exists():
                try:
                    loaded = json.loads(self.path.read_text(encoding="utf-8"))
                    if not isinstance(loaded, list):
                        raise ValidationError("Файл макросов должен содержать массив")
                    self.macros = [validate_macro(item) for item in loaded]
                except Exception as exc:
                    backup = self.path.with_suffix(f".corrupt.{int(time.time())}.json")
                    self.path.replace(backup)
                    self.macros = [demo_macro()]
                    self.save_unlocked()
                    emit("error", {"message": f"Файл макросов повреждён и сохранён как {backup.name}: {exc}"})
            else:
                self.macros = [demo_macro()]
                self.save_unlocked()
            return list(self.macros)

    def save_unlocked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self.macros, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.path)

    def save(self) -> None:
        with self._lock:
            self.save_unlocked()

    def upsert(self, macro: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        validated = validate_macro(macro)
        with self._lock:
            if not validated.get("id"):
                validated["id"] = f"macro-{int(time.time() * 1000)}"
            self.macros = [item for item in self.macros if item.get("id") != validated["id"]]
            self.macros.append(validated)
            self.save_unlocked()
            return list(self.macros), validated

    def replace_all(self, macros: list[dict[str, Any]]) -> list[dict[str, Any]]:
        validated = [validate_macro(macro) for macro in macros]
        seen: set[str] = set()
        for macro in validated:
            if not macro.get("id"):
                macro["id"] = f"macro-{int(time.time() * 1000)}-{len(seen)}"
            if macro["id"] in seen:
                raise ValidationError(f"Дублирующийся id макроса: {macro['id']}")
            seen.add(macro["id"])
        with self._lock:
            self.macros = validated
            self.save_unlocked()
            return list(self.macros)

    def delete(self, macro_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self.macros = [item for item in self.macros if item.get("id") != macro_id]
            self.save_unlocked()
            return list(self.macros)

    def by_id(self, macro_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next((item for item in self.macros if item.get("id") == macro_id), None)


def demo_macro() -> dict[str, Any]:
    return {
        "id": "demo-left-click",
        "name": "Быстрый левый клик",
        "hotkey": "ctrl+alt+1",
        "repeat": 5,
        "intervalMs": 120,
        "actions": [{"type": "click", "button": "left"}],
    }


class MacroRunner:
    def __init__(self, store: MacroStore) -> None:
        self.store = store
        self._running: set[str] = set()
        self._stop_events: dict[str, threading.Event] = {}
        self._hotkey_listener: Any = None
        self._recording: MacroRecorder | None = None

    def start_macro(self, macro_id: str) -> None:
        macro = self.store.by_id(macro_id)
        if not macro:
            emit("error", {"message": "Макрос не найден"})
            return
        if macro_id in self._running:
            emit("status", {"message": f"Макрос '{macro['name']}' уже выполняется"})
            return
        stop_event = threading.Event()
        self._running.add(macro_id)
        self._stop_events[macro_id] = stop_event
        threading.Thread(target=self._run_macro, args=(macro, stop_event), daemon=True).start()

    def stop_macro(self, macro_id: str | None = None) -> None:
        targets = [macro_id] if macro_id else list(self._stop_events)
        for target in targets:
            if target in self._stop_events:
                self._stop_events[target].set()
                emit("status", {"message": f"Остановка макроса: {target}"})
        if not targets:
            emit("status", {"message": "Нет запущенных макросов"})

    def _run_macro(self, macro: dict[str, Any], stop_event: threading.Event) -> None:
        macro_id = macro["id"]
        emit("macro-started", {"id": macro_id})
        try:
            repeat = max(1, int(macro.get("repeat", 1)))
            interval = max(0, int(macro.get("intervalMs", 0))) / 1000
            for iteration in range(repeat):
                if stop_event.is_set():
                    break
                emit("macro-progress", {"id": macro_id, "current": iteration + 1, "total": repeat})
                for action_index, action in enumerate(macro.get("actions", [])):
                    if stop_event.is_set():
                        break
                    emit("macro-action", {"id": macro_id, "index": action_index, "action": action})
                    self._run_action(action, stop_event)
                if interval and not stop_event.is_set():
                    stop_event.wait(interval)
        except Exception as exc:  # pragma: no cover - runtime hardware failures
            emit("error", {"message": str(exc)})
        finally:
            self._running.discard(macro_id)
            self._stop_events.pop(macro_id, None)
            emit("macro-finished", {"id": macro_id, "stopped": stop_event.is_set()})

    def _run_action(self, action: dict[str, Any], stop_event: threading.Event) -> None:
        action_type = action.get("type")
        if action_type == "wait":
            stop_event.wait(max(0, int(action.get("durationMs", 500))) / 1000)
            return
        if pyautogui is None:
            emit("error", {"message": "Установите pyautogui: pip install -r requirements.txt"})
            return
        if action_type == "click":
            pyautogui.click(button=action.get("button", "left"))
        elif action_type == "doubleClick":
            pyautogui.doubleClick(button=action.get("button", "left"))
        elif action_type == "press":
            pyautogui.press(str(action.get("key", "space")))
        elif action_type == "move":
            pyautogui.moveTo(int(action.get("x", 0)), int(action.get("y", 0)))

    def refresh_hotkeys(self) -> None:
        if self._hotkey_listener:
            self._hotkey_listener.stop()
            self._hotkey_listener = None
        if keyboard is None:
            emit("status", {"message": "Глобальные хоткеи недоступны: установите pynput"})
            return
        mapping: dict[str, Callable[[], None]] = {STOP_ALL_HOTKEY: lambda: self.stop_macro(None)}
        for macro in self.store.macros:
            hotkey = normalize_hotkey(macro.get("hotkey", ""))
            if hotkey:
                mapping[hotkey] = lambda macro_id=macro["id"]: self.start_macro(macro_id)
        self._hotkey_listener = keyboard.GlobalHotKeys(mapping)
        self._hotkey_listener.start()

    def start_recording(self) -> None:
        if self._recording and self._recording.is_recording:
            emit("error", {"message": "Запись уже идёт"})
            return
        if keyboard is None or mouse is None:
            emit("error", {"message": "Запись недоступна: установите pynput"})
            return
        self._recording = MacroRecorder()
        self._recording.start()

    def stop_recording(self) -> None:
        if not self._recording or not self._recording.is_recording:
            emit("error", {"message": "Запись не запущена"})
            return
        actions = self._recording.stop()
        emit("recording-finished", {"actions": actions})


class MacroRecorder:
    def __init__(self) -> None:
        self.actions: list[dict[str, Any]] = []
        self.is_recording = False
        self._last_time = 0.0
        self._mouse_listener: Any = None
        self._keyboard_listener: Any = None

    def start(self) -> None:
        self.is_recording = True
        self._last_time = time.monotonic()
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._keyboard_listener = keyboard.Listener(on_press=self._on_press)
        self._mouse_listener.start()
        self._keyboard_listener.start()
        emit("recording-started", {})

    def stop(self) -> list[dict[str, Any]]:
        self.is_recording = False
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        return self.actions

    def _append_wait(self) -> None:
        now = time.monotonic()
        duration = int((now - self._last_time) * 1000)
        self._last_time = now
        if duration >= 50:
            self.actions.append({"type": "wait", "durationMs": duration})

    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        if not self.is_recording or not pressed:
            return
        self._append_wait()
        button_name = getattr(button, "name", "left")
        if button_name not in ALLOWED_BUTTONS:
            button_name = "left"
        self.actions.append({"type": "move", "x": int(x), "y": int(y)})
        self.actions.append({"type": "click", "button": button_name})
        emit("recording-updated", {"actions": self.actions})

    def _on_press(self, key: Any) -> None:
        if not self.is_recording:
            return
        name = getattr(key, "char", None) or getattr(key, "name", None)
        if not name:
            return
        if name in {"esc"}:
            return
        self._append_wait()
        self.actions.append({"type": "press", "key": str(name)})
        emit("recording-updated", {"actions": self.actions})


def normalize_hotkey(hotkey: str) -> str:
    aliases = {"control": "ctrl", "command": "cmd", "super": "cmd", "win": "cmd", "meta": "cmd"}
    parts = [part.strip().lower() for part in hotkey.replace(" ", "").split("+") if part.strip()]
    converted = []
    for part in parts:
        part = aliases.get(part, part)
        converted.append(f"<{part}>" if part in {"ctrl", "alt", "shift", "cmd"} else part)
    return "+".join(converted)


def main() -> None:
    store = MacroStore()
    store.load()
    runner = MacroRunner(store)
    runner.refresh_hotkeys()
    emit("ready", {"macros": store.macros, "stopAllHotkey": "ctrl+alt+esc"})

    for line in sys.stdin:
        try:
            message = json.loads(line)
            command = message.get("command")
            payload = message.get("payload", {})
            if command == "list":
                emit("macros", {"macros": store.macros})
            elif command == "save":
                macros, saved = store.upsert(payload)
                emit("macros", {"macros": macros, "selectedId": saved["id"]})
                runner.refresh_hotkeys()
            elif command == "delete":
                emit("macros", {"macros": store.delete(payload.get("id", ""))})
                runner.refresh_hotkeys()
            elif command == "run":
                runner.start_macro(payload.get("id", ""))
            elif command == "stop":
                runner.stop_macro(payload.get("id") or None)
            elif command == "record:start":
                runner.start_recording()
            elif command == "record:stop":
                runner.stop_recording()
            elif command == "import":
                emit("macros", {"macros": store.replace_all(payload.get("macros", []))})
                runner.refresh_hotkeys()
            elif command == "reset-demo":
                emit("macros", {"macros": store.replace_all([demo_macro()]), "selectedId": "demo-left-click"})
                runner.refresh_hotkeys()
            else:
                emit("error", {"message": f"Неизвестная команда: {command}"})
        except Exception as exc:
            emit("error", {"message": str(exc)})


if __name__ == "__main__":
    main()