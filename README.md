# Python Electron AutoClicker

Десктопное приложение-автокликер на Electron с Python-бэкендом. В нём можно создавать макросы, задавать список действий и назначать горячую клавишу для запуска.

## Возможности

- создание, редактирование и удаление макросов;
- запуск макроса из интерфейса;
- глобальные хоткеи через `pynput`;
- выполнение кликов, двойных кликов, нажатий клавиш, перемещения мыши и пауз через `pyautogui`;
- хранение макросов в `data/macros.json`.

## Установка

```bash
npm install
python3 -m pip install pyautogui pynput
npm start
```

> На Linux для `pyautogui`/`pynput` могут понадобиться системные зависимости и доступ к X11/Wayland permissions.

## Формат действий

```json
[
  { "type": "move", "x": 400, "y": 300 },
  { "type": "click", "button": "left" },
  { "type": "wait", "durationMs": 500 },
  { "type": "press", "key": "space" }
]
```

Поддерживаемые типы: `click`, `doubleClick`, `press`, `move`, `wait`.