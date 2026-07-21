import json
import tempfile
import unittest
from pathlib import Path

from main import MacroStore, ValidationError, normalize_hotkey, validate_action, validate_macro


class ValidationTests(unittest.TestCase):
    def valid_macro(self):
        return {
            "id": "m1",
            "name": " Test ",
            "hotkey": "control+alt+1",
            "repeat": 2,
            "intervalMs": 100,
            "actions": [{"type": "click", "button": "left"}],
        }

    def test_normalize_hotkey_aliases(self):
        self.assertEqual(normalize_hotkey("control + alt + 1"), "<ctrl>+<alt>+1")
        self.assertEqual(normalize_hotkey("win+shift+x"), "<cmd>+<shift>+x")

    def test_validate_macro_normalizes_values(self):
        macro = validate_macro(self.valid_macro())
        self.assertEqual(macro["name"], "Test")
        self.assertEqual(macro["actions"], [{"type": "click", "button": "left"}])

    def test_validate_macro_rejects_invalid_repeat(self):
        macro = self.valid_macro()
        macro["repeat"] = 0
        with self.assertRaises(ValidationError):
            validate_macro(macro)

    def test_validate_action_rejects_invalid_button(self):
        with self.assertRaises(ValidationError):
            validate_action({"type": "click", "button": "bad"}, 0)

    def test_validate_required_action_fields(self):
        for action in ({"type": "move", "x": 1}, {"type": "wait"}, {"type": "press", "key": ""}):
            with self.assertRaises(ValidationError):
                validate_action(action, 0)


class MacroStoreTests(unittest.TestCase):
    def test_store_load_save_upsert_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "macros.json"
            store = MacroStore(path=path)
            self.assertEqual(store.load()[0]["id"], "demo-left-click")
            macros, saved = store.upsert({
                "id": "custom",
                "name": "Custom",
                "hotkey": "",
                "repeat": 1,
                "intervalMs": 0,
                "actions": [{"type": "wait", "durationMs": 10}],
            })
            self.assertEqual(saved["id"], "custom")
            self.assertTrue(any(item["id"] == "custom" for item in macros))
            self.assertFalse(any(item["id"] == "custom" for item in store.delete("custom")))
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(any(item["id"] == "custom" for item in persisted))

    def test_replace_all_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MacroStore(path=Path(tmp) / "macros.json")
            macro = {
                "id": "dup",
                "name": "Dup",
                "hotkey": "",
                "repeat": 1,
                "intervalMs": 0,
                "actions": [{"type": "click", "button": "left"}],
            }
            with self.assertRaises(ValidationError):
                store.replace_all([macro, dict(macro)])


if __name__ == "__main__":
    unittest.main()