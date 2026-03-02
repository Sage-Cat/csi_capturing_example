# Опис експерименту static_sign_v1 (UA)

## 1) Мета експерименту

Експеримент `static_sign_v1` призначений для бінарної класифікації статичного жесту людини за CSI-даними ESP32:

- `baseline` — нейтральна поза
- `hands_up` — руки вгору

Кінцева мета: навчити просту базову модель (лінійний SVM або логістична регресія), яка розрізняє ці два стани на основі статистичних ознак CSI.

---

## 2) Сетап (2 ноутбуки + 2 ESP32)

- **Ноутбук A (TX/AP)**: запускає ESP32 `csi_send` (джерело Wi‑Fi/CSI трафіку).
- **Ноутбук B (RX)**: запускає ESP32 `csi_recv` і виконує захоплення CSI у датасет.
- **Людина**: стоїть між TX і RX, **спиною до приймача**, показує статичний знак.

Рекомендація: не змінювати геометрію (позиції TX/RX/людини) в межах одного датасету.

---

## 3) Команди для запуску

### 3.1 Ноутбук A (TX/AP)

Перший запуск (зі збіркою/прошивкою):

```bash
cd ~/Projects/csi_capture
./scripts/run_tx_laptop.sh --port /dev/ttyACM0
```

Повторні запуски (без rebuild/reflash):

```bash
cd ~/Projects/csi_capture
./scripts/run_tx_laptop.sh --port /dev/ttyACM0 --skip-build --skip-flash
```

### 3.2 Ноутбук B (RX + capture)

1. Підготувати RX-плату (`csi_recv`):

```bash
cd ~/Projects/csi_capture
./scripts/run_rx_csi_node.sh --port /dev/esp32_csi
```

Повторні запуски:

```bash
cd ~/Projects/csi_capture
./scripts/run_rx_csi_node.sh --port /dev/esp32_csi --skip-build --skip-flash
```

2. Перевірити, що серійний пристрій доступний і є потік CSI:

```bash
cd ~/Projects/csi_capture
./tools/exp --list-devices
./tools/exp capture --experiment static_sign_v1 --dry-run-packets 5 --dry-run-timeout 10s --device /dev/esp32_csi
```

Для macOS зазвичай порти мають вигляд `/dev/cu.usbmodem*` або `/dev/tty.usbmodem*`, наприклад:

```bash
./tools/exp capture --experiment static_sign_v1 --dry-run-packets 5 --dry-run-timeout 10s --device /dev/cu.usbmodem1101
```

3. Зібрати датасет (інтерактивно `baseline` → `hands_up`):

```bash
cd ~/Projects/csi_capture
./scripts/run_static_sign_protocol.sh \
  --device /dev/esp32_csi \
  --dataset-id 20260302_subject01_labA \
  --runs 5 \
  --duration 20s \
  --subject-id subject01 \
  --environment-id labA \
  --notes "back-to-rx posture, fixed feet marker"
```

4. Навчити та оцінити модель:

```bash
cd ~/Projects/csi_capture
./scripts/run_static_sign_train_eval.sh \
  --dataset-id 20260302_subject01_labA \
  --model svm_linear \
  --window 1s \
  --overlap 0.5
```

---

## 4) Що відбувається всередині pipeline

1. **Capture**: сирі CSI-пакети зчитуються через `/dev/esp32_csi`.
2. **Dataset layout**: створюється структура `data/experiments/static_sign_v1/<dataset_id>/<label>/run_<run_id>/`.
3. **Metadata**: для кожного run зберігаються `metadata.json` та `frames.jsonl`.
4. **Feature extraction**: віконні ознаки амплітуди CSI (mean, variance, RMS, entropy).
5. **Train**: тренується базова модель (`svm_linear` або `logreg`).
6. **Eval**: обчислюються метрики `accuracy`, `precision`, `recall`, `F1`, матриця помилок і підсумок по run.

---

## 5) Вихідні артефакти

- **Датасет**:
  - `data/experiments/static_sign_v1/<dataset_id>/...`
- **Модель**:
  - `artifacts/static_sign_v1/<dataset_id>/*.pkl`
- **Train metrics**:
  - поряд із моделлю `*.metrics.json`
- **Eval report**:
  - `out/static_sign_v1/<dataset_id>/eval_report.json`

---

## 6) Практичні поради для стабільності якості

- Балансуй дані: однакова кількість run для `baseline` і `hands_up`.
- Тримай фіксовану позу й орієнтацію людини (спиною до RX).
- Мінімізуй сторонні рухи людей під час запису.
- При зміні умов кімнати/розстановки створюй новий `dataset_id`.
