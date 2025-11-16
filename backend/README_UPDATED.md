# Parking System - Python Backend

Полнофункциональная система мониторинга парковок на Python с ML-пайплайном.

## 🎯 Ключевые возможности

### ML Pipeline
- **YOLOv11-Seg** - детекция и сегментация автомобилей
- **ByteTrack** - ID-consistent tracking с Kalman filter
- **IoU-based occupancy** - точное определение занятости через Intersection over Union
- **Preprocessing** - адаптивная обработка для экстремальных условий (ночь, снег, дождь, туман)
- **Multi-camera fusion** - объединение данных с нескольких камер
- **Temporal smoothing** - устойчивость к ложным срабатываниям

### Backend
- **FastAPI** - современный async веб-фреймворк
- **SQLAlchemy** - ORM для работы с БД
- **RTSP/HTTP support** - универсальный connector для камер
- **Homography calibration** - калибровка камер для проекции координат
- **Advanced analytics** - heatmap, статистика, аномалии

## 📁 Структура проекта

```
backend/
├── ml/
│   ├── vehicle_detector.py    # YOLOv11-Seg детектор
│   └── tracker.py              # ByteTrack трекер
├── services/
│   ├── camera_connector.py     # Универсальный connector для камер
│   ├── processing_pipeline.py  # Главный processing pipeline
│   ├── multi_camera_fusion.py  # Multi-camera fusion
│   └── analytics.py            # Расширенная аналитика
├── utils/
│   ├── homography.py           # Калибровка камер
│   ├── occupancy_iou.py        # IoU-based occupancy detection
│   └── preprocessing.py        # Preprocessing для экстремальных условий
├── models/
│   └── database.py             # SQLAlchemy модели
├── api/
│   ├── cameras.py              # API для камер
│   ├── parking_places.py       # API для парковочных мест
│   ├── zones.py                # API для зон
│   ├── analytics.py            # API для аналитики
│   └── calibration.py          # API для калибровки
├── config/
│   └── settings.py             # Конфигурация
├── main.py                     # FastAPI приложение
├── requirements.txt            # Python зависимости
└── test_system.py              # Тестовый скрипт
```

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
cd backend
pip install -r requirements.txt
```

### 2. Настройка базы данных

Создайте файл `.env`:

```env
DATABASE_URL=sqlite:///./parking.db
# или для PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/parking_db
```

### 3. Запуск сервера

```bash
python main.py
```

API будет доступен на `http://localhost:8000`

Swagger документация: `http://localhost:8000/docs`

## 📊 ML Pipeline

### Preprocessing для экстремальных условий

```python
from utils.preprocessing import ImagePreprocessor, WeatherCondition

preprocessor = ImagePreprocessor(auto_detect=True)

# Автоматическая обработка
processed_frame, condition = preprocessor.preprocess(frame)

# Ручная обработка
processed_frame, _ = preprocessor.preprocess(frame, WeatherCondition.NIGHT)
```

**Поддерживаемые условия:**
- `NORMAL` - обычные условия
- `NIGHT` - ночь (CLAHE + шумоподавление + gamma correction)
- `SNOW` - снег (bilateral filter + contrast enhancement)
- `RAIN` - дождь (Gaussian blur + median filter + sharpening)
- `FOG` - туман (dark channel prior dehazing + CLAHE)
- `OVEREXPOSED` - пересвет (tone mapping)

### IoU-based Occupancy Detection

```python
from utils.occupancy_iou import IoUOccupancyDetector

detector = IoUOccupancyDetector(
    iou_threshold=0.25,  # 25% пересечения
    min_frames_occupied=5,
    min_frames_free=5
)

# Добавить парковочные места
detector.add_place(place_id=1, polygon=[(x1,y1), (x2,y2), ...])

# Обновить с детекциями
detections = [
    {
        'mask': vehicle_mask,  # Binary mask (H x W)
        'track_id': 123,
        'confidence': 0.95
    }
]
events = detector.update(detections)

# Получить статус
summary = detector.get_occupancy_summary()
# {'total': 100, 'occupied': 45, 'free': 55, 'occupancy_rate': 45.0}
```

### Multi-camera Fusion

```python
from services.multi_camera_fusion import MultiCameraFusion

fusion = MultiCameraFusion(
    max_time_diff_seconds=2.0,
    stale_threshold_seconds=10.0
)

# Добавить камеры с полями зрения
fusion.add_camera(
    camera_id=1,
    fov_polygon=[(x1,y1), (x2,y2), ...],  # На глобальной схеме
    priority=1
)

# Добавить парковочные места
fusion.add_place(
    place_id=1,
    global_polygon=[(x1,y1), (x2,y2), ...]
)

# Обновить данные с камеры
fusion.update_camera_data(
    camera_id=1,
    place_statuses={
        1: {'status': 'occupied', 'track_id': 123, 'confidence': 0.95}
    }
)

# Получить объединенные данные
fused = fusion.get_fused_occupancy()
```

### Расширенная аналитика

```python
from services.analytics import ParkingAnalytics

analytics = ParkingAnalytics()

# Добавить метаданные мест
analytics.add_place_metadata(
    place_id=1,
    zone_id=1,
    row="A",
    place_type="regular"
)

# Записать события
analytics.record_occupancy_event(
    place_id=1,
    track_id=123,
    event_type='occupied',
    timestamp=datetime.utcnow()
)

# Получить heatmap
heatmap = analytics.get_heatmap(group_by='zone')
# {'zone_1': 0.95, 'zone_2': 0.67, ...}

# Средняя длительность
duration = analytics.get_average_duration()
# {'average_hours': 2.5, 'median_seconds': 7200, ...}

# Оборачиваемость
turnover = analytics.get_turnover_rate()
# {'turnover_rate': 3.2, 'period_days': 7, ...}

# Пиковые часы
peak_hours = analytics.get_peak_hours()
# {0: 5, 1: 3, ..., 18: 45, 19: 52, ...}

# Аномалии (>24ч)
anomalies = analytics.detect_anomalies(threshold_hours=24.0)

# Полный отчет
summary = analytics.export_summary()
```

## 🎥 Работа с камерами

### Подключение RTSP камеры

```python
from services.camera_connector import CameraConnector

connector = CameraConnector(
    source="rtsp://username:password@192.168.1.100:554/stream",
    camera_type="rtsp",
    reconnect_delay=5.0
)

connector.start()

while True:
    frame = connector.get_frame()
    if frame is not None:
        # Обработка кадра
        pass
```

### Processing Pipeline

```python
from services.processing_pipeline import ParkingProcessingPipeline

pipeline = ParkingProcessingPipeline(
    detector_config={'model_path': 'yolo11n-seg.pt'},
    tracker_config={},
    occupancy_config={'iou_threshold': 0.25}
)

# Добавить парковочные места
pipeline.add_parking_place(
    place_id=1,
    polygon=[(x1,y1), (x2,y2), ...]
)

# Обработать кадр
frame = connector.get_frame()
result = pipeline.process_frame(frame)

# result содержит:
# - detections: список детекций
# - tracks: список треков
# - occupancy_events: события занятости
# - occupancy_summary: текущая загрузка
```

## 🔧 Калибровка камер

```python
from utils.homography import HomographyCalibrator

calibrator = HomographyCalibrator()

# Добавить контрольные точки
calibrator.add_point_pair(
    camera_point=(x_cam, y_cam),
    map_point=(x_map, y_map)
)

# Вычислить homography (минимум 4 точки)
H = calibrator.compute_homography()

# Трансформировать координаты
map_coords = calibrator.transform_camera_to_map([(x1, y1), (x2, y2)])

# Трансформировать полигоны
map_polygon = calibrator.transform_polygon_to_map(camera_polygon)
```

## 📡 API Endpoints

### Камеры
- `GET /api/cameras` - список камер
- `POST /api/cameras` - добавить камеру
- `PUT /api/cameras/{id}` - обновить камеру
- `DELETE /api/cameras/{id}` - удалить камеру
- `GET /api/cameras/{id}/status` - статус камеры

### Парковочные места
- `GET /api/parking-places` - список мест
- `POST /api/parking-places` - добавить место
- `PUT /api/parking-places/{id}` - обновить место
- `DELETE /api/parking-places/{id}` - удалить место
- `POST /api/parking-places/bulk-create` - массовое создание

### Зоны
- `GET /api/zones` - список зон
- `POST /api/zones` - создать зону
- `PUT /api/zones/{id}` - обновить зону
- `DELETE /api/zones/{id}` - удалить зону

### Аналитика
- `GET /api/analytics/current` - текущая загрузка
- `GET /api/analytics/history` - история загрузки
- `GET /api/analytics/heatmap` - тепловая карта
- `GET /api/analytics/average-duration` - средняя длительность
- `GET /api/analytics/turnover` - оборачиваемость
- `GET /api/analytics/anomalies` - аномалии

### Калибровка
- `POST /api/calibration/{camera_id}/points` - добавить точки
- `POST /api/calibration/{camera_id}/compute` - вычислить homography
- `GET /api/calibration/{camera_id}` - получить калибровку

## 🧪 Тестирование

```bash
python test_system.py
```

Тестовый скрипт проверяет:
- Детектор YOLOv11
- Трекер ByteTrack
- IoU occupancy detection
- Preprocessing
- Multi-camera fusion
- Analytics

## 📝 Конфигурация

### settings.py

```python
DATABASE_URL = "sqlite:///./parking.db"
YOLO_MODEL_PATH = "yolo11n-seg.pt"
CONFIDENCE_THRESHOLD = 0.5
IOU_THRESHOLD = 0.25
MIN_FRAMES_OCCUPIED = 5
MIN_FRAMES_FREE = 5
FRAME_SKIP = 2
MAX_RECONNECT_ATTEMPTS = 5
```

## 🔍 Мониторинг

### Логирование

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Метрики

TODO: Добавить Prometheus метрики для:
- FPS обработки
- Количество детекций
- Загрузка парковки
- Latency API

## 🚧 Roadmap

- [ ] WebSocket для real-time обновлений
- [ ] Экспорт отчетов в PDF/Excel
- [ ] Prometheus метрики
- [ ] Docker контейнеризация
- [ ] Kubernetes deployment
- [ ] Обучение на синтетических данных
- [ ] Детекция неправильной парковки

## 📄 Лицензия

MIT License
