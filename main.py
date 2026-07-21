#!/usr/bin/env python3
"""JSON-lines Python backend for the Electron autoclicker.

The backend stores macro definitions, registers global hotkeys when pynput is
available, and executes click/key/wait actions. The protocol is intentionally
small so the Electron process can talk to Python over stdin/stdout.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    import pyautogui
except ImportError:  # pragma: no cover - depends on user's desktop env
    pyautogui = None

try:
    from pynput import keyboard
except ImportError:  # pragma: no cover - depends on user's desktop env
    keyboard = None

DATA_DIR = Path(__file__).resolve().parent / "data"
MACROS_FILE = DATA_DIR / "macros.json"


def emit(event: str, payload: dict[str, Any] | None = None) -> None:
    print(json.dumps({"event": event, "payload": payload or {}}, ensure_ascii=False), flush=True)


@dataclass
class MacroStore:
    path: Path = MACROS_FILE
    macros: list[dict[str, Any]] = field(default_factory=list)

    def load(self) -> list[dict[str, Any]]:
        if self.path.exists():
            self.macros = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.macros = [
                {
                    "id": "demo-left-click",
                    "name": "Быстрый левый клик",
                    "hotkey": "ctrl+alt+1",
                    "repeat": 5,
                    "intervalMs": 120,
                    "actions": [{"type": "click", "button": "left"}],
                }
            ]
            self.save()
        return self.macros

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.macros, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert(self, macro: dict[str, Any]) -> list[dict[str, Any]]:
        if not macro.get("id"):
            macro["id"] = f"macro-{int(time.time() * 1000)}"
        self.macros = [item for item in self.macros if item.get("id") != macro["id"]]
        self.macros.append(macro)
        self.save()
        return self.macros

    def delete(self, macro_id: str) -> list[dict[str, Any]]:
        self.macros = [item for item in self.macros if item.get("id") != macro_id]
        self.save()
        return self.macros

    def by_id(self, macro_id: str) -> dict[str, Any] | None:
        return next((item for item in self.macros if item.get("id") == macro_id), None)


class MacroRunner:
    def __init__(self, store: MacroStore) -> None:
        self.store = store
        self._running: set[str] = set()
        self._stop_events: dict[str, threading.Event] = {}
        self._hotkey_listener: Any = None

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

    def _run_macro(self, macro: dict[str, Any], stop_event: threading.Event) -> None:
        macro_id = macro["id"]
        emit("macro-started", {"id": macro_id})
        try:
            repeat = max(1, int(macro.get("repeat", 1)))
            interval = max(0, int(macro.get("intervalMs", 0))) / 1000
            for _ in range(repeat):
                if stop_event.is_set():
                    break
                for action in macro.get("actions", []):
                    if stop_event.is_set():
                        break
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
            emit("error", {"message": "Установите pyautogui: pip install pyautogui"})
            return
        if action_type == "click":
            pyautogui.click(button=action.get("button", "left"))
        elif action_type == "doubleClick":
            pyautogui.doubleClick(button=action.get("button", "left"))
        elif action_type == "press":
            key = str(action.get("key", "space"))
            pyautogui.press(key)
        elif action_type == "move":
            pyautogui.moveTo(int(action.get("x", 0)), int(action.get("y", 0)))

    def refresh_hotkeys(self) -> None:
        if self._hotkey_listener:
            self._hotkey_listener.stop()
            self._hotkey_listener = None
        if keyboard is None:
            emit("status", {"message": "Глобальные хоткеи недоступны: установите pynput"})
            return
        mapping: dict[str, Callable[[], None]] = {}
        for macro in self.store.macros:
            hotkey = normalize_hotkey(macro.get("hotkey", ""))
            if hotkey:
                mapping[hotkey] = lambda macro_id=macro["id"]: self.start_macro(macro_id)
        if mapping:
            self._hotkey_listener = keyboard.GlobalHotKeys(mapping)
            self._hotkey_listener.start()


def normalize_hotkey(hotkey: str) -> str:
    parts = [part.strip().lower() for part in hotkey.replace(" ", "").split("+") if part.strip()]
    converted = []
    for part in parts:
        converted.append(f"<{part}>" if part in {"ctrl", "alt", "shift", "cmd"} else part)
    return "+".join(converted)


def main() -> None:
    store = MacroStore()
    store.load()
    runner = MacroRunner(store)
    runner.refresh_hotkeys()
    emit("ready", {"macros": store.macros})

    for line in sys.stdin:
        try:
            message = json.loads(line)
            command = message.get("command")
            payload = message.get("payload", {})
            if command == "list":
                emit("macros", {"macros": store.macros})
            elif command == "save":
                emit("macros", {"macros": store.upsert(payload)})
                runner.refresh_hotkeys()
            elif command == "delete":
                emit("macros", {"macros": store.delete(payload.get("id", ""))})
                runner.refresh_hotkeys()
            elif command == "run":
                runner.start_macro(payload.get("id", ""))
            elif command == "stop":
                runner.stop_macro(payload.get("id") or None)
            else:
                emit("error", {"message": f"Неизвестная команда: {command}"})
        except Exception as exc:
            emit("error", {"message": str(exc)})


if __name__ == "__main__":
    main()