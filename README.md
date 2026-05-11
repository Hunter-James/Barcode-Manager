# Barcode Manager

Десктопный сканер штрих- и QR-кодов для Windows — клон интерфейса
*Barcode Manager for Windows* с принципиально лучшим распознаванием.

Оригинал часто промахивается на фотографиях с телефона (размытие, низкий
контраст, мелкий код в большом кадре). Эта версия читает такие изображения
за счёт мультидвижкового каскада и агрессивной предобработки.

## Возможности

- **Reader** — распознавание из:
  - Screen Snip — встроенный в Windows инструмент «Ножницы» (`Win+Shift+S`),
    корректно работает на нескольких мониторах
  - открытия файла + drag-and-drop
  - живой камеры
  - изображения из буфера обмена
- **Create** — генерация QR Code, Data Matrix, Aztec, PDF417, Code 128/39/93,
  Codabar, EAN-13/8, UPC-A/E, ITF
- **History** — журнал сканирований/генераций в `%APPDATA%\BarcodeManager\history.json`
- **Settings** — звук, автокопирование результата, выбор камеры, интервал
  декода в режиме камеры

## Чем распознавание отличается от оригинала

Стандартные библиотеки (zxing-cpp, pyzbar, OpenCV QR detector) хорошо
читают чистые сканы и плохо — реальные фото. Здесь применён каскад:

1. Прогон трёх движков параллельно на исходном изображении.
2. Если пусто — конвейер предобработки:
   grayscale → CLAHE → unsharp mask → Otsu/adaptive threshold → инверсия →
   morph close → апскейл ×1.5/×2/×3 → денойз.
3. Поиск регионов через `cv2.QRCodeDetector` и `cv2.barcode.BarcodeDetector`,
   повторный прогон конвейера на найденных кропах.
4. Финальный fallback — брутфорс по углам (15/30/45/60/90/135/180/225/270/315°).

На синтетических кейсах с сильным размытием, низким контрастом и мелким
QR на сложном фоне голые движки возвращают пусто, а каскад читает код.

## Запуск

### Готовый EXE

После сборки (см. ниже) запустите `dist\BarcodeManager.exe`. Зависимостей не требует.

### Из исходников

Нужен Python 3.10+:

```powershell
py -3 -m pip install -r requirements.txt
py -3 main.py
```

## Сборка собственного EXE

```powershell
build.bat
```

Скрипт сначала перерисует иконку (`tools\make_icon.py`), затем соберёт
single-file `dist\BarcodeManager.exe` через PyInstaller. EXE ~90 МБ —
обычный размер для PyQt6 + OpenCV в onefile-режиме.

## Структура проекта

```
BarcodeManager/
├── main.py                  # точка входа
├── decoder/
│   ├── engine.py            # мультидвижковый декодер
│   └── preprocessing.py     # конвейер предобработки
├── ui/
│   ├── main_window.py       # главное окно (табы + нижняя панель)
│   ├── reader_tab.py        # Reader: превью + декод + камера
│   ├── create_tab.py        # генерация кодов
│   ├── settings_tab.py
│   ├── history_view.py
│   ├── snip_overlay.py      # обёртка над Windows Snipping Tool
│   ├── widgets.py           # верхние/нижние табы
│   ├── icons.py             # иконки, нарисованные QPainter
│   └── style.py             # тёмная QSS-тема
├── camera/capture.py        # поток захвата с веб-камеры
├── storage/history.py       # JSON-история
├── tools/make_icon.py       # генерация .ico из QPainter-иконки
├── tests/                   # стресс-тесты декодера
├── resources/
│   ├── app_icon.ico
│   └── app_icon.png
├── BarcodeManager.spec      # PyInstaller spec
└── build.bat                # одна кнопка для сборки EXE
```

## Горячие клавиши

| Сочетание      | Действие             |
|----------------|----------------------|
| `Ctrl+Shift+S` | Screen Snip          |
| `Ctrl+O`       | Открыть файл         |
| `Ctrl+H`       | История              |
| `Esc`          | Сброс Reader         |

## Зависимости

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — GUI
- [zxing-cpp](https://github.com/zxing-cpp/zxing-cpp) — основной декодер
- [pyzbar](https://github.com/NaturalHistoryMuseum/pyzbar) — резервный декодер (особенно для 1D)
- [OpenCV](https://opencv.org/) — предобработка + детекция регионов
- [Pillow](https://python-pillow.org/) — генерация .ico

## Лицензия

[MIT](LICENSE)
