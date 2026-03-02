# Кутовий експеримент (Angle) — інструкція українською

## 1) Що це за експеримент

Це експеримент зі **збору датасету CSI** для кутів навколо точки доступу.

- Тип: `angle`
- Кути: `0, 45, 90, 135, 180, 225, 270, 315`
- Кількість прогонів: `2` (`run_001` і `run_002`)
- Конфіг: `docs/configs/angle_radial_45deg_2runs.sample.json`

## 2) Обладнання

Потрібно 2 ноутбуки і 2 ESP32:

- **Laptop A + ESP32 (TX/AP)**: передавач (`csi_send`)
- **Laptop B + ESP32 (RX/receiver)**: приймач і запис датасету (`csi_recv`)

## 3) Як розмістити у кімнаті (порожня кімната, 2 стільці)

- Постав **стілець №1 у центр кімнати**. На ньому Laptop A + TX ESP32 (це AP).
- Для Laptop B + RX ESP32 використовуй **стілець №2 як рухому позицію**.
- Відміряй фіксований радіус від центру (наприклад 2 м).
- Познач на підлозі 8 точок по колу: `0, 45, 90, 135, 180, 225, 270, 315`.
- Висоту TX і RX тримай приблизно однаковою.
- Орієнтацію плат ESP32 не крути між вимірами (має бути стабільна).

## 4) Підготовка перед запуском

Зроби ці кроки **на обох ноутбуках** (TX і RX).

### 4.1 Системні пакети (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y \
  git wget flex bison gperf python3 python3-pip python3-venv python3-serial \
  cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
```

Додай користувача в `dialout` (доступ до `/dev/ttyACM*`):

```bash
sudo usermod -a -G dialout $USER
```

Після цього вийди з сесії і зайди знову (або перезавантаж ноутбук).

### 4.2 Системні пакети (macOS + Homebrew)

```bash
brew update
brew install python cmake ninja ccache dfu-util libusb
```

Для macOS порти зазвичай мають вигляд:

- `/dev/cu.usbmodem*`
- `/dev/tty.usbmodem*`
- `/dev/cu.usbserial*`
- `/dev/tty.usbserial*`

### 4.3 Встановлення ESP-IDF

```bash
mkdir -p ~/esp
cd ~/esp
git clone -b v5.5.3 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32s3
```

Перевір, що файл існує:

```bash
ls -l ~/esp/esp-idf/export.sh
```

### 4.4 Встановлення esp-csi

```bash
cd ~/esp
git clone https://github.com/espressif/esp-csi.git
```

### 4.5 Python-залежності проєкту

```bash
cd /home/sagecat/Projects/csi_capture
python3 -m pip install -r requirements.txt
```

### 4.6 Перевірка RX-девайсу

На Linux RX-ноуті:

```bash
ls -l /dev/esp32_csi
```

На macOS RX-ноуті:

```bash
ls -1 /dev/cu.usbmodem* /dev/tty.usbmodem* 2>/dev/null
```

Якщо скрипт пише `export.sh not found`, значить ESP-IDF встановлено не в `~/esp/esp-idf`.
У такому разі передай явні шляхи:

```bash
./scripts/run_tx_laptop.sh \
  --idf-path /фактичний/шлях/до/esp-idf \
  --esp-csi-path /фактичний/шлях/до/esp-csi \
  --port /dev/ttyACM0
```

## 5) Запуск експерименту

### Крок A: запусти передавач (Laptop A)

```bash
cd /home/sagecat/Projects/csi_capture
./scripts/run_tx_laptop.sh --skip-build --skip-flash
```

Скрипт сам пробує авто-визначити порт. Якщо потрібно явно (особливо на macOS), передай `--port`:

```bash
./scripts/run_tx_laptop.sh --port /dev/cu.usbmodem2101 --skip-build --skip-flash
```

### Крок B: запусти збір кутового датасету (Laptop B)

```bash
cd /home/sagecat/Projects/csi_capture
python3 -m csi_capture.experiment angle \
  --config docs/configs/angle_radial_45deg_2runs.sample.json \
  --device auto
```

`--device auto` робить авто-вибір порту на Linux/macOS (пріоритет: `/dev/esp32_csi`, далі системні serial-кандидати).

Якщо на macOS підключено кілька USB-пристроїв, краще явно вказати порт:

```bash
python3 -m csi_capture.experiment angle \
  --config docs/configs/angle_radial_45deg_2runs.sample.json \
  --device /dev/cu.usbmodem1101
```

## 6) Протокол проведення під час запису

У конфігу вже задано:

- `run_ids`: `["001", "002"]`
- `inter_trial_pause_s`: `12` секунд

Що це означає на практиці:

1. Піде `run_001`.
2. На кожному куті збираються пакети.
3. Після завершення кута буде пауза 12 с.
4. Під час паузи переставляй стілець №2 на наступну кутову мітку.
5. Після 8 кутів автоматично стартує `run_002` і все повторюється.

Рекомендація:

- Після перестановки відійди від пристрою, не стоячи між TX і RX.

## 7) Де лежать результати

Після завершення:

- `experiments/<exp_id>/angle/run_001/...`
- `experiments/<exp_id>/angle/run_002/...`

В кожному run є:

- `manifest.json`
- папки `trial_angle_*` з `capture.jsonl`

## 8) Як перевірити, що дані записались

Перевір кількість рядків у файлах `capture.jsonl` (має бути > 0):

```bash
find experiments/<exp_id>/angle -name "capture.jsonl" -exec wc -l {} \;
```

Або згенеруй короткий summary:

```bash
python3 tools/analyze_wifi_angle_dataset.py \
  --data_dir experiments/<exp_id>/angle \
  --out_dir out/angle_dataset
```

## 9) Типові проблеми

- `records=0` у trial:
  - TX не передає або не той порт.
  - RX порт вибрано неправильно (на macOS часто треба явний `/dev/cu.usbmodem*`).
  - Неправильна прошивка на одній із плат.
  - Занадто великий шум/перешкоди або слабкий сигнал.

- Немає доступу до порту:
  - Linux: додай користувача в `dialout` і перезайди в сесію.
  - macOS: закрий інші serial-монітори, перепідключи плату, перевір `ls -l /dev/cu.usbmodem*`.

## 10) Швидкий чекліст перед стартом

- TX і RX плати підключені.
- TX скрипт запущений на Laptop A.
- На Laptop B видно serial-порт (`/dev/esp32_csi` або `/dev/cu.usbmodem*`).
- Кути на підлозі розмічені.
- Вибраний фіксований радіус.
- У кімнаті немає зайвого руху під час запису.
