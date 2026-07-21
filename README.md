Десктопное приложение-автокликер на Electron с Python-бэкендом. В нём можно создавать макросы, задавать список действий, записывать действия мыши/клавиатуры и назначать горячую клавишу для запуска.

## Возможности

- создание, редактирование и удаление макросов;
- визуальный редактор действий без обязательного ручного JSON;
- drag-and-drop сортировка, дублирование и удаление действий;
- запись макросов через `pynput`;
- запуск макроса из интерфейса;
- глобальные хоткеи через `pynput`;
- аварийная остановка всех макросов кнопкой в UI или хоткеем `ctrl+alt+esc`;
- выполнение кликов, двойных кликов, нажатий клавиш, перемещения мыши и пауз через `pyautogui`;
- хранение макросов в `data/macros.json`.
- импорт и экспорт макросов в JSON;
- хранение макросов в `data/macros.json` с резервным сохранением повреждённого файла.

## Установка

```bash
npm install
python3 -m pip install pyautogui pynput
python3 -m pip install -r requirements.txt
npm start
```

> На Linux для `pyautogui`/`pynput` могут понадобиться системные зависимости и доступ к X11/Wayland permissions.

## Проверки

```bash
npm run check:electron
npm run check:python
npm run test:python
npm test
```

## Сборка приложения

В `package.json` добавлена конфигурация `electron-builder` и скрипты:

```bash
npm run package
npm run dist
```

Если `electron-builder` ещё не установлен в окружении, установите dev-зависимости через `npm install`.

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
Поддерживаемые типы: `click`, `doubleClick`, `press`, `move`, `wait`.

## Валидация макросов

Каждый макрос должен содержать:

- `name` — непустая строка;
- `repeat` — положительное целое число;
- `intervalMs` — неотрицательное целое число;
- `actions` — непустой массив действий.

Действия валидируются и в renderer, и в Python-бэкенде.