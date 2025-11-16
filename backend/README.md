# Parking Monitoring System - Backend

Интеллектуальная система мониторинга парковок с ML-детекцией автомобилей на Python.

## Архитектура

```
Camera (RTSP/HTTP) 
  ↓
Detection (YOLOv11-Seg)
  ↓
Tracking (ByteTrack)
  ↓
Homography Transform
  ↓
Point-in-Polygon
  ↓
Temporal Smoothing
  ↓
Database
```

## Установка

### 1. Создать виртуальное окружение

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

### 3. Настроить переменные окружения

Создать файл `.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/parking_db
YOLO_MODEL_PATH=yolov11n-seg.pt
YOLO_DEVICE=cuda  # или cpu
DEBUG=True
```

### 4. Инициализировать базу данных

```bash
# Создать миграции
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## Запуск

### Development режим

```bash
python main.py
```

Или с uvicorn:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production режим

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Документация

После запуска доступна по адресу:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Основные endpoints

### Cameras
- `GET /api/cameras` - список камер
- `POST /api/cameras` - добавить камеру
- `GET /api/cameras/{id}` - информация о камере
- `POST /api/cameras/{id}/start` - запустить камеру
- `POST /api/cameras/{id}/stop` - остановить камеру

### Parking Places
- `GET /api/parking-places` - список парковочных мест
- `POST /api/parking-places` - создать место
- `GET /api/parking-places/{id}/occupancy` - статус занятости

### Calibration
- `POST /api/calibration/{camera_id}/calibrate` - калибровать камеру
- `POST /api/calibration/{camera_id}/test-transform` - тест трансформации

### Analytics
- `GET /api/analytics/current` - текущая загрузка
- `GET /api/analytics/history` - история загрузки
- `GET /api/analytics/anomalies` - аномалии (долгостоящие авто)

## Тестирование

### Тест с видеофайлом

```python
from backend.services.camera_connector import CameraConnector, CameraType
from backend.ml.vehicle_detector import VehicleDetector
import cv2

# Создать детектор
detector = VehicleDetector(model_path="yolov11n-seg.pt", device="cpu")

# Подключить видео
camera = CameraConnector(
    camera_id=1,
    source="test_video.mp4",
    camera_type=CameraType.FILE
)
camera.start()

# Получить кадр
frame_data = camera.get_frame()
if frame_data:
    frame, frame_num, timestamp = frame_data
    
    # Детекция
    detections = detector.detect(frame)
    print(f"Found {len(detections)} vehicles")
    
    # Визуализация
    annotated = detector.visualize(frame, detections)
    cv2.imshow("Detections", annotated)
    cv2.waitKey(0)

camera.stop()
```

### Тест калибровки

```python
from backend.utils.homography import HomographyCalibrator

calibrator = HomographyCalibrator()

# Точки на кадре камеры и на схеме
camera_points = [(100, 200), (300, 200), (300, 400), (100, 400)]
map_points = [(50, 100), (150, 100), (150, 200), (50, 200)]

success = calibrator.calibrate(camera_points, map_points)
if success:
    print(f"Calibration successful! Error: {calibrator.reprojection_error:.2f}")
    
    # Трансформировать точку
    test_point = (200, 300)
    transformed = calibrator.transform_point(test_point)
    print(f"Camera {test_point} -> Map {transformed}")
```

### Тест occupancy detection

```python
from backend.utils.occupancy import ParkingMonitorManager

manager = ParkingMonitorManager()

# Добавить парковочное место
polygon = [(100, 100), (200, 100), (200, 200), (100, 200)]
manager.add_place(place_id=1, polygon=polygon)

# Симуляция детекций
detections = [
    {'centroid': [150, 150], 'track_id': 1, 'class_name': 'car', 'confidence': 0.95}
]

events = manager.update_all(detections)
print(f"Events: {events}")

summary = manager.get_occupancy_summary()
print(f"Occupancy: {summary['occupied']}/{summary['total']}")
```

## Структура проекта

```
backend/
├── api/                    # FastAPI роутеры
│   ├── cameras.py
│   ├── parking_places.py
│   ├── zones.py
│   ├── analytics.py
│   └── calibration.py
├── ml/                     # ML компоненты
│   ├── vehicle_detector.py  # YOLOv11 детектор
│   └── tracker.py           # ByteTrack трекер
├── services/               # Бизнес-логика
│   ├── camera_connector.py  # Работа с камерами
│   └── processing_pipeline.py  # Главный pipeline
├── utils/                  # Утилиты
│   ├── homography.py       # Калибровка камер
│   └── occupancy.py        # Point-in-polygon + temporal smoothing
├── models/                 # Модели БД
│   └── database.py
├── config/                 # Конфигурация
│   └── settings.py
├── main.py                 # Главный файл приложения
└── requirements.txt        # Зависимости
```

## Производительность

### Рекомендуемые требования

**Минимальные (CPU):**
- CPU: 4 cores
- RAM: 8 GB
- 1-2 камеры одновременно
- YOLOv11n-seg
- ~5-10 FPS per camera

**Рекомендуемые (GPU):**
- GPU: NVIDIA RTX 3060 или выше
- RAM: 16 GB
- VRAM: 6 GB+
- 5-10 камер одновременно
- YOLOv11m-seg
- ~20-30 FPS per camera

### Оптимизация

1. **Frame skipping**: Обрабатывать каждый N-й кадр (`FRAME_SKIP=2`)
2. **Модель**: Использовать YOLOv11n для скорости, YOLOv11m для точности
3. **Batch processing**: Обрабатывать несколько камер батчами
4. **Resolution**: Уменьшить разрешение кадров (640x480 вместо 1920x1080)

## Troubleshooting

### CUDA not available

```bash
# Проверить CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Установить PyTorch с CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### RTSP connection failed

- Проверить доступность камеры: `ffplay rtsp://camera_url`
- Проверить firewall/network
- Увеличить timeout: `RTSP_TIMEOUT_SEC=30`

### Low FPS

- Увеличить `FRAME_SKIP`
- Использовать меньшую модель (yolov11n)
- Уменьшить разрешение кадров
- Использовать GPU

## Лицензия

MIT
