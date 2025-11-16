# 🚗 Intelligent Parking Monitoring System

Интеллектуальная система мониторинга парковок с ML-детекцией автомобилей, трекингом и определением занятости парковочных мест в реальном времени.

## 🎯 Возможности

### Core Features
- ✅ **ML-детекция автомобилей** - YOLOv11-Seg с сегментацией
- ✅ **ID-consistent tracking** - ByteTrack с Kalman filter
- ✅ **Калибровка камер** - Homography трансформация координат
- ✅ **Point-in-polygon** - Определение занятости парковочных мест
- ✅ **Temporal smoothing** - Debounce фильтр для устойчивости
- ✅ **Multi-camera support** - Обработка нескольких камер одновременно
- ✅ **RTSP/HTTP поддержка** - Универсальный connector для камер
- ✅ **Auto-reconnect** - Автоматическое переподключение при обрыве
- ✅ **Real-time analytics** - Текущая загрузка, средняя длительность, аномалии

### Архитектура

```
┌─────────────┐
│   Camera    │ (RTSP/HTTP/Motion-activated)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Detection  │ YOLOv11-Seg (car, truck, bus, motorcycle)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Tracking   │ ByteTrack (ID-consistent)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Homography  │ Camera → Map coordinates
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Point-in-Poly│ Occupancy detection
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Temporal   │ Smoothing (debounce)
│  Smoothing  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Database   │ Events, Analytics
└─────────────┘
```

## 📁 Структура проекта

```
ParkingSystem/
├── backend/                    # Python backend (ГЛАВНОЕ!)
│   ├── api/                    # FastAPI роутеры
│   │   ├── cameras.py          # Управление камерами
│   │   ├── parking_places.py   # Парковочные места
│   │   ├── zones.py            # Зоны парковки
│   │   ├── analytics.py        # Аналитика
│   │   └── calibration.py      # Калибровка камер
│   ├── ml/                     # ML компоненты
│   │   ├── vehicle_detector.py # YOLOv11 детектор
│   │   └── tracker.py          # ByteTrack трекер
│   ├── services/               # Бизнес-логика
│   │   ├── camera_connector.py # Работа с камерами
│   │   └── processing_pipeline.py # Главный pipeline
│   ├── utils/                  # Утилиты
│   │   ├── homography.py       # Калибровка камер
│   │   └── occupancy.py        # Point-in-polygon + smoothing
│   ├── models/                 # Модели БД (SQLAlchemy)
│   │   └── database.py
│   ├── config/                 # Конфигурация
│   │   └── settings.py
│   ├── main.py                 # FastAPI приложение
│   ├── test_system.py          # Тестовый скрипт
│   ├── requirements.txt        # Python зависимости
│   └── README.md               # Документация backend
├── client/                     # Frontend (опционально, для тестирования)
├── drizzle/                    # Database schema (старая версия, не используется)
├── server/                     # Node.js backend (старая версия, не используется)
├── TODO_PYTHON.md              # TODO список для Python версии
└── README.md                   # Этот файл
```

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
cd backend

# Создать виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt
```

### 2. Конфигурация

Создать файл `backend/.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/parking_db

# ML Models
YOLO_MODEL_PATH=yolov11n-seg.pt
YOLO_CONFIDENCE_THRESHOLD=0.5
YOLO_DEVICE=cuda  # или cpu

# Tracking
MAX_AGE=30
MIN_HITS=3
IOU_THRESHOLD=0.3

# Temporal Smoothing
MIN_FRAMES_OCCUPIED=5
MIN_FRAMES_FREE=5

# Camera Processing
FRAME_SKIP=2
MAX_CAMERAS=10

DEBUG=True
```

### 3. Запуск

```bash
cd backend
python main.py
```

Или с uvicorn:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Проверка работы

**API документация:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

**Health check:**
```bash
curl http://localhost:8000/api/health
```

**Запуск тестов:**
```bash
cd backend
python test_system.py
```

## 📖 Использование

### Добавить камеру

```bash
curl -X POST http://localhost:8000/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Parking Camera 1",
    "rtsp_url": "rtsp://camera_ip:554/stream",
    "connection_type": "rtsp",
    "floor": 0
  }'
```

### Калибровать камеру

```bash
curl -X POST http://localhost:8000/api/calibration/1/calibrate \
  -H "Content-Type: application/json" \
  -d '{
    "camera_points": [[100, 200], [300, 200], [300, 400], [100, 400]],
    "map_points": [[50, 100], [150, 100], [150, 200], [50, 200]]
  }'
```

### Получить текущую загрузку

```bash
curl http://localhost:8000/api/analytics/current
```

## 🧪 Тестирование

### Тест с видеофайлом

```python
from backend.services.camera_connector import CameraConnector, CameraType
from backend.ml.vehicle_detector import VehicleDetector

# Создать детектор
detector = VehicleDetector(model_path="yolov11n-seg.pt", device="cpu")

# Подключить видео
camera = CameraConnector(
    camera_id=1,
    source="test_video.mp4",
    camera_type=CameraType.FILE
)
camera.start()

# Получить кадр и детектировать
frame_data = camera.get_frame()
if frame_data:
    frame, frame_num, timestamp = frame_data
    detections = detector.detect(frame)
    print(f"Found {len(detections)} vehicles")

camera.stop()
```

### Полный тест системы

```bash
cd backend
python test_system.py
```

Тесты покрывают:
1. Vehicle detection (YOLOv11)
2. Vehicle tracking (ByteTrack)
3. Homography calibration
4. Occupancy detection
5. Full pipeline integration

## ⚙️ Конфигурация

### Производительность

**CPU режим (для тестирования):**
```env
YOLO_DEVICE=cpu
YOLO_MODEL_PATH=yolov11n-seg.pt  # Самая легкая модель
FRAME_SKIP=5  # Обрабатывать каждый 5-й кадр
```

**GPU режим (production):**
```env
YOLO_DEVICE=cuda
YOLO_MODEL_PATH=yolov11m-seg.pt  # Более точная модель
FRAME_SKIP=2  # Обрабатывать каждый 2-й кадр
```

### Temporal Smoothing

Настройка чувствительности определения занятости:

```env
MIN_FRAMES_OCCUPIED=5  # Кадров для подтверждения занятости
MIN_FRAMES_FREE=5      # Кадров для подтверждения освобождения
```

- Больше значение = меньше ложных срабатываний, но медленнее реакция
- Меньше значение = быстрее реакция, но больше ложных срабатываний

## 📊 API Endpoints

### Cameras
- `GET /api/cameras` - список камер
- `POST /api/cameras` - добавить камеру
- `GET /api/cameras/{id}` - информация о камере
- `PUT /api/cameras/{id}` - обновить камеру
- `DELETE /api/cameras/{id}` - удалить камеру
- `POST /api/cameras/{id}/start` - запустить камеру
- `POST /api/cameras/{id}/stop` - остановить камеру

### Parking Places
- `GET /api/parking-places` - список парковочных мест
- `POST /api/parking-places` - создать место
- `GET /api/parking-places/{id}` - информация о месте
- `PUT /api/parking-places/{id}` - обновить место
- `DELETE /api/parking-places/{id}` - удалить место
- `POST /api/parking-places/bulk-create` - массовое создание

### Calibration
- `POST /api/calibration/{camera_id}/calibrate` - калибровать камеру
- `GET /api/calibration/{camera_id}/calibration` - получить калибровку
- `POST /api/calibration/{camera_id}/test-transform` - тест трансформации

### Analytics
- `GET /api/analytics/current` - текущая загрузка
- `GET /api/analytics/history` - история загрузки
- `GET /api/analytics/anomalies` - аномалии (долгостоящие авто)
- `GET /api/analytics/average-duration` - средняя длительность
- `GET /api/analytics/turnover` - оборачиваемость мест

## 🔧 Troubleshooting

### CUDA not available

```bash
# Проверить CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Установить PyTorch с CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### RTSP connection failed

- Проверить доступность: `ffplay rtsp://camera_url`
- Проверить firewall/network
- Увеличить timeout: `RTSP_TIMEOUT_SEC=30`

### Low FPS

- Увеличить `FRAME_SKIP`
- Использовать меньшую модель (yolov11n)
- Уменьшить разрешение кадров
- Использовать GPU

## 📝 Технические детали

### ML Models

**YOLOv11-Seg:**
- Модель: yolov11n-seg.pt (nano), yolov11s-seg.pt (small), yolov11m-seg.pt (medium)
- Классы: car (2), motorcycle (3), bus (5), truck (7) из COCO dataset
- Сегментация: Polygon masks для точного определения границ

**ByteTrack:**
- Kalman filter для предсказания позиций
- IoU matching для ассоциации детекций
- Re-identification при пропущенных кадрах
- Сохранение траекторий (history)

### Homography

Трансформация координат из camera view в map view (bird's eye):

```
[x_map]       [x_camera]
[y_map]  = H  [y_camera]
[  1  ]       [   1    ]
```

Где H - 3x3 homography matrix, вычисляемая по контрольным точкам.

### Point-in-Polygon

Алгоритм определения, находится ли центроид автомобиля внутри полигона парковочного места. Используется библиотека Shapely для точных геометрических вычислений.

### Temporal Smoothing

State machine для каждого парковочного места:

```
FREE ──(N кадров с авто)──> OCCUPIED ──(N кадров без авто)──> FREE
```

Где N = MIN_FRAMES_OCCUPIED или MIN_FRAMES_FREE

## 📄 Лицензия

MIT

## 👥 Авторы

Разработано для системы мониторинга парковок с использованием современных ML технологий.

## 🔗 Ссылки

- [YOLOv11 Documentation](https://docs.ultralytics.com/)
- [ByteTrack Paper](https://arxiv.org/abs/2110.06864)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenCV Documentation](https://docs.opencv.org/)
