# Barcode Manager

Десктопный сканер штрих- и QR-кодов для Windows с упором на изображения,
которые обычно отказываются распознаваться: фотографии с телефона, размытые
кадры, низкоконтрастные этикетки, мелкие коды на сложном фоне.

## Возможности

- **Reader** — распознавание из:
  - **Screen Snip** — собственный оверлей через `PIL.ImageGrab.grab(all_screens=True)`,
    корректно работает на нескольких мониторах и не пишет в буфер обмена;
  - открытия файла + drag-and-drop;
  - живой камеры (декод раз в ~250 мс в отдельном потоке);
  - изображения из буфера обмена.
- **Несколько кодов в одном кадре**. Каждый размечается на превью красным
  бейджем с цифрой, а в баннере появляется нумерованный список в порядке
  чтения (сверху вниз, слева направо).
- **GS1-aware**. Для Data Matrix / GS1-128 / DataBar-семейства декодер
  восстанавливает ведущий FNC1 (0x1d), который zxing-cpp в `TextMode.Plain`
  выбрасывает как метаданные. Внутренние FNC1-разделители полей также
  сохраняются в сыром виде — то, что нужно для строго типизированных
  баз данных и логов.
- **Create** — генерация QR Code, Data Matrix, Aztec, PDF417, Code 128/39/93,
  Codabar, EAN-13/8, UPC-A/E, ITF.
- **History** — журнал сканирований и генераций в
  `%APPDATA%\BarcodeManager\history.json` с миниатюрами, поиском и копированием
  сырого payload по двойному клику.
- **Settings** — звук, авто-копирование результата, выбор камеры, интервал
  декода в режиме камеры.

## Распознавание

Standard decoders (zxing-cpp, pyzbar, OpenCV) хорошо читают чистые сканы и
плохо — реальные фото. Здесь применён каскад:

1. Параллельный прогон трёх движков на исходном изображении.
2. Если пусто — конвейер предобработки: grayscale → CLAHE → unsharp mask →
   Otsu / adaptive threshold → bilateral filter → морфологическая
   дилатация (для inkjet-точечных кодов) → инверсия → апскейл ×1.5 / ×2 / ×3 →
   directional sharpen (для 1D-кодов) → денойз.
3. Поиск регионов через `cv2.QRCodeDetector` и `cv2.barcode.BarcodeDetector`,
   повторный прогон конвейера на найденных кропах.
4. Брутфорс по углам поворота (15° / 30° / 45° / 60° / 90° / 135° / 180° /
   225° / 270° / 315°).
5. Финальный проход с альтернативными бинаризаторами zxing
   (`GlobalHistogram`, `FixedThreshold`, `BoolCast`).

На стресс-тестах с сильным размытием, низким контрастом, мелким QR на
сложном фоне и точечной inkjet-печатью пайплайн вытягивает кейсы, где
сырые движки возвращают пусто.

## Запуск

### Готовый EXE

После сборки запустите `dist\BarcodeManager.exe`. Зависимостей не требует.

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
│   ├── engine.py            # мультидвижковый декодер + восстановление GS1
│   └── preprocessing.py     # конвейер предобработки
├── ui/
│   ├── main_window.py       # главное окно (табы + нижняя панель)
│   ├── reader_tab.py        # Reader: превью, декод, камера, нумерация
│   ├── create_tab.py        # генерация кодов
│   ├── settings_tab.py
│   ├── history_view.py      # история с миниатюрами
│   ├── snip_overlay.py      # снип через PIL.ImageGrab (multi-monitor)
│   ├── widgets.py           # верхние/нижние табы
│   ├── icons.py             # иконки, нарисованные QPainter
│   ├── text_util.py         # обработка FNC1 для display и хранения
│   └── style.py             # тёмная QSS-тема
├── camera/capture.py        # поток захвата с веб-камеры
├── storage/history.py       # JSON-история
├── tools/make_icon.py       # генерация .ico из QPainter-иконки
├── tests/                   # стресс-тесты декодера и снимки UI
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
- [OpenCV](https://opencv.org/) — предобработка и детекция регионов
- [Pillow](https://python-pillow.org/) — мультимониторный screen-grab и генерация .ico

## Лицензия

[MIT](LICENSE)
