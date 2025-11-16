// Main Application Logic

let currentPage = 'cameras';

// Show alert message
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const main = document.getElementById('main-content');
    main.insertBefore(alertDiv, main.firstChild);
    
    setTimeout(() => alertDiv.remove(), 5000);
}

// Show loading indicator
function showLoading() {
    return '<div class="loading">Загрузка...</div>';
}

// Page navigation
async function showPage(pageName) {
    currentPage = pageName;
    const main = document.getElementById('main-content');
    main.innerHTML = showLoading();
    
    try {
        switch(pageName) {
            case 'cameras':
                await loadCamerasPage();
                break;
            case 'calibration':
                await loadCalibrationPage();
                break;
            case 'editor':
                await loadEditorPage();
                break;
            case 'monitor':
                await loadMonitorPage();
                break;
            case 'analytics':
                await loadAnalyticsPage();
                break;
            default:
                main.innerHTML = '<h2>Страница не найдена</h2>';
        }
    } catch (error) {
        main.innerHTML = `<div class="alert alert-error">Ошибка загрузки: ${error.message}</div>`;
    }
}

// ============ CAMERAS PAGE ============
async function loadCamerasPage() {
    const main = document.getElementById('main-content');
    
    main.innerHTML = `
        <h2>Управление камерами</h2>
        
        <div class="toolbar">
            <button class="btn" onclick="showAddCameraForm()">+ Добавить камеру</button>
            <button class="btn btn-secondary" onclick="loadCamerasPage()">🔄 Обновить</button>
        </div>
        
        <div id="camera-form-container"></div>
        <div id="cameras-list"></div>
    `;
    
    await refreshCamerasList();
}

async function refreshCamerasList() {
    const container = document.getElementById('cameras-list');
    container.innerHTML = showLoading();
    
    try {
        const cameras = await api.getCameras();
        
        if (cameras.length === 0) {
            container.innerHTML = '<p>Камеры не добавлены</p>';
            return;
        }
        
        let html = `
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Название</th>
                        <th>RTSP URL</th>
                        <th>Зона</th>
                        <th>Статус</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        for (const camera of cameras) {
            const status = camera.is_active ? 
                '<span class="status-online">●  Online</span>' : 
                '<span class="status-offline">● Offline</span>';
            
            html += `
                <tr>
                    <td>${camera.id}</td>
                    <td>${camera.name}</td>
                    <td><code>${camera.rtsp_url}</code></td>
                    <td>${camera.zone_id || '-'}</td>
                    <td>${status}</td>
                    <td>
                        <button class="btn btn-secondary" onclick="viewCameraFrame(${camera.id})">👁️ Просмотр</button>
                        <button class="btn btn-danger" onclick="deleteCamera(${camera.id})">🗑️ Удалить</button>
                    </td>
                </tr>
            `;
        }
        
        html += '</tbody></table>';
        container.innerHTML = html;
        
    } catch (error) {
        container.innerHTML = `<div class="alert alert-error">Ошибка загрузки камер: ${error.message}</div>`;
    }
}

function showAddCameraForm() {
    const container = document.getElementById('camera-form-container');
    
    container.innerHTML = `
        <div style="background: #ecf0f1; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
            <h3>Добавить камеру</h3>
            <form id="add-camera-form" onsubmit="handleAddCamera(event)">
                <div class="form-group">
                    <label>Название:</label>
                    <input type="text" name="name" required placeholder="Камера 1">
                </div>
                <div class="form-group">
                    <label>RTSP URL:</label>
                    <input type="text" name="rtsp_url" required placeholder="rtsp://username:password@ip:port/stream">
                </div>
                <div class="form-group">
                    <label>Тип:</label>
                    <select name="camera_type">
                        <option value="rtsp">RTSP</option>
                        <option value="http">HTTP</option>
                        <option value="motion_activated">Motion Activated</option>
                    </select>
                </div>
                <button type="submit" class="btn">Добавить</button>
                <button type="button" class="btn btn-secondary" onclick="hideAddCameraForm()">Отмена</button>
            </form>
        </div>
    `;
}

function hideAddCameraForm() {
    document.getElementById('camera-form-container').innerHTML = '';
}

async function handleAddCamera(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const data = {
        name: formData.get('name'),
        rtsp_url: formData.get('rtsp_url'),
        camera_type: formData.get('camera_type'),
        is_active: true
    };
    
    try {
        await api.createCamera(data);
        showAlert('Камера успешно добавлена', 'success');
        hideAddCameraForm();
        await refreshCamerasList();
    } catch (error) {
        showAlert(`Ошибка добавления камеры: ${error.message}`, 'error');
    }
}

async function deleteCamera(id) {
    if (!confirm('Удалить камеру?')) return;
    
    try {
        await api.deleteCamera(id);
        showAlert('Камера удалена', 'success');
        await refreshCamerasList();
    } catch (error) {
        showAlert(`Ошибка удаления: ${error.message}`, 'error');
    }
}

async function viewCameraFrame(id) {
    try {
        const frame = await api.getCameraFrame(id);
        
        // Open in new window
        const win = window.open('', '_blank', 'width=800,height=600');
        win.document.write(`
            <html>
                <head><title>Camera ${id} Frame</title></head>
                <body style="margin:0; background:#000;">
                    <img src="data:image/jpeg;base64,${frame.frame}" style="width:100%; height:auto;">
                </body>
            </html>
        `);
    } catch (error) {
        showAlert(`Ошибка получения кадра: ${error.message}`, 'error');
    }
}

// ============ CALIBRATION PAGE ============
let calibrationState = {
    cameraId: null,
    cameraFrame: null,
    parkingMap: null,
    cameraPoints: [],
    mapPoints: [],
    currentMode: 'camera' // 'camera' or 'map'
};

async function loadCalibrationPage() {
    const main = document.getElementById('main-content');
    
    main.innerHTML = `
        <h2>Калибровка камер</h2>
        
        <div class="form-group">
            <label>Выберите камеру:</label>
            <select id="calibration-camera-select" onchange="selectCameraForCalibration()">
                <option value="">-- Выберите камеру --</option>
            </select>
        </div>
        
        <div id="calibration-content"></div>
    `;
    
    // Load cameras list
    try {
        const cameras = await api.getCameras();
        const select = document.getElementById('calibration-camera-select');
        
        cameras.forEach(camera => {
            const option = document.createElement('option');
            option.value = camera.id;
            option.textContent = `${camera.name} (ID: ${camera.id})`;
            select.appendChild(option);
        });
    } catch (error) {
        showAlert(`Ошибка загрузки камер: ${error.message}`, 'error');
    }
}

async function selectCameraForCalibration() {
    const select = document.getElementById('calibration-camera-select');
    const cameraId = parseInt(select.value);
    
    if (!cameraId) return;
    
    calibrationState.cameraId = cameraId;
    calibrationState.cameraPoints = [];
    calibrationState.mapPoints = [];
    
    const content = document.getElementById('calibration-content');
    content.innerHTML = showLoading();
    
    try {
        // Get camera frame
        const frameData = await api.getCameraFrame(cameraId);
        calibrationState.cameraFrame = frameData.frame;
        
        showCalibrationInterface();
    } catch (error) {
        content.innerHTML = `<div class="alert alert-error">Ошибка: ${error.message}</div>`;
    }
}

function showCalibrationInterface() {
    const content = document.getElementById('calibration-content');
    
    content.innerHTML = `
        <div class="alert alert-info">
            <strong>Инструкция:</strong> Выберите 4-8 контрольных точек на кадре камеры, 
            затем выберите соответствующие точки на схеме парковки.
        </div>
        
        <div class="calibration-grid">
            <div class="image-panel">
                <h3>Кадр с камеры (кликните для выбора точек)</h3>
                <div class="canvas-container">
                    <canvas id="camera-canvas"></canvas>
                </div>
                <div class="points-list" id="camera-points-list"></div>
            </div>
            
            <div class="image-panel">
                <h3>Схема парковки</h3>
                <div class="form-group">
                    <input type="file" id="map-upload" accept="image/*" onchange="loadParkingMap()">
                </div>
                <div class="canvas-container" id="map-canvas-container" style="display:none;">
                    <canvas id="map-canvas"></canvas>
                </div>
                <div class="points-list" id="map-points-list"></div>
            </div>
        </div>
        
        <div style="margin-top: 20px;">
            <button class="btn" onclick="calculateHomography()" id="calc-btn" disabled>
                Вычислить калибровку
            </button>
            <button class="btn btn-secondary" onclick="resetCalibration()">
                Сбросить точки
            </button>
        </div>
        
        <div id="calibration-result"></div>
    `;
    
    // Draw camera frame
    const canvas = document.getElementById('camera-canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    
    img.onload = () => {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
    };
    
    img.src = `data:image/jpeg;base64,${calibrationState.cameraFrame}`;
    
    // Add click handler
    canvas.addEventListener('click', (e) => handleCanvasClick(e, 'camera'));
}

function loadParkingMap() {
    const input = document.getElementById('map-upload');
    const file = input.files[0];
    
    if (!file) return;
    
    const reader = new FileReader();
    
    reader.onload = (e) => {
        const img = new Image();
        
        img.onload = () => {
            const canvas = document.getElementById('map-canvas');
            const ctx = canvas.getContext('2d');
            
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
            
            calibrationState.parkingMap = e.target.result;
            document.getElementById('map-canvas-container').style.display = 'block';
            
            // Add click handler
            canvas.addEventListener('click', (ev) => handleCanvasClick(ev, 'map'));
        };
        
        img.src = e.target.result;
    };
    
    reader.readAsDataURL(file);
}

function handleCanvasClick(event, mode) {
    const canvas = event.target;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    
    // Add point
    if (mode === 'camera') {
        calibrationState.cameraPoints.push([x, y]);
        updatePointsList('camera');
        drawPoints(canvas, calibrationState.cameraPoints);
    } else {
        calibrationState.mapPoints.push([x, y]);
        updatePointsList('map');
        drawPoints(canvas, calibrationState.mapPoints);
    }
    
    // Enable calculate button if enough points
    const minPoints = 4;
    if (calibrationState.cameraPoints.length >= minPoints && 
        calibrationState.mapPoints.length >= minPoints &&
        calibrationState.cameraPoints.length === calibrationState.mapPoints.length) {
        document.getElementById('calc-btn').disabled = false;
    }
}

function drawPoints(canvas, points) {
    const ctx = canvas.getContext('2d');
    
    // Redraw image first
    const img = new Image();
    img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        
        // Draw points
        points.forEach((point, idx) => {
            ctx.fillStyle = 'red';
            ctx.strokeStyle = 'white';
            ctx.lineWidth = 2;
            
            ctx.beginPath();
            ctx.arc(point[0], point[1], 5, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
            
            // Draw number
            ctx.fillStyle = 'white';
            ctx.font = 'bold 14px Arial';
            ctx.fillText(idx + 1, point[0] + 10, point[1] - 10);
        });
    };
    
    if (canvas.id === 'camera-canvas') {
        img.src = `data:image/jpeg;base64,${calibrationState.cameraFrame}`;
    } else {
        img.src = calibrationState.parkingMap;
    }
}

function updatePointsList(mode) {
    const listId = mode === 'camera' ? 'camera-points-list' : 'map-points-list';
    const points = mode === 'camera' ? calibrationState.cameraPoints : calibrationState.mapPoints;
    const list = document.getElementById(listId);
    
    list.innerHTML = '<strong>Точки:</strong><br>' + 
        points.map((p, i) => `${i + 1}. (${Math.round(p[0])}, ${Math.round(p[1])})`).join('<br>');
}

function resetCalibration() {
    calibrationState.cameraPoints = [];
    calibrationState.mapPoints = [];
    
    const cameraCanvas = document.getElementById('camera-canvas');
    const mapCanvas = document.getElementById('map-canvas');
    
    if (cameraCanvas) drawPoints(cameraCanvas, []);
    if (mapCanvas) drawPoints(mapCanvas, []);
    
    document.getElementById('camera-points-list').innerHTML = '';
    document.getElementById('map-points-list').innerHTML = '';
    document.getElementById('calc-btn').disabled = true;
    document.getElementById('calibration-result').innerHTML = '';
}

async function calculateHomography() {
    const resultDiv = document.getElementById('calibration-result');
    resultDiv.innerHTML = showLoading();
    
    try {
        const data = {
            camera_points: calibrationState.cameraPoints,
            map_points: calibrationState.mapPoints
        };
        
        const result = await api.calibrateCamera(calibrationState.cameraId, data);
        
        resultDiv.innerHTML = `
            <div class="alert alert-success">
                <strong>✓ Калибровка успешно выполнена!</strong><br>
                Reprojection error: ${result.reprojection_error?.toFixed(4) || 'N/A'}<br>
                Homography матрица сохранена в базе данных.
            </div>
        `;
        
        showAlert('Калибровка завершена успешно!', 'success');
        
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="alert alert-error">
                <strong>Ошибка калибровки:</strong> ${error.message}
            </div>
        `;
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    showPage('cameras');
});


// ============ PARKING EDITOR PAGE ============
let editorState = {
    cameraId: null,
    parkingMap: null,
    places: [],
    currentTool: 'select', // 'select', 'rectangle', 'polygon'
    currentPolygon: [],
    selectedPlace: null,
    placeType: 'standard'
};

async function loadEditorPage() {
    const main = document.getElementById('main-content');
    
    main.innerHTML = `
        <h2>Редактор парковочных мест</h2>
        
        <div class="form-group">
            <label>Выберите камеру:</label>
            <select id="editor-camera-select" onchange="selectCameraForEditor()">
                <option value="">-- Выберите камеру --</option>
            </select>
        </div>
        
        <div id="editor-content"></div>
    `;
    
    // Load cameras
    try {
        const cameras = await api.getCameras();
        const select = document.getElementById('editor-camera-select');
        
        cameras.forEach(camera => {
            const option = document.createElement('option');
            option.value = camera.id;
            option.textContent = `${camera.name} (ID: ${camera.id})`;
            select.appendChild(option);
        });
    } catch (error) {
        showAlert(`Ошибка загрузки камер: ${error.message}`, 'error');
    }
}

async function selectCameraForEditor() {
    const select = document.getElementById('editor-camera-select');
    const cameraId = parseInt(select.value);
    
    if (!cameraId) return;
    
    editorState.cameraId = cameraId;
    editorState.places = [];
    editorState.currentPolygon = [];
    
    const content = document.getElementById('editor-content');
    content.innerHTML = showLoading();
    
    try {
        // Load existing places
        const places = await api.getParkingPlaces(cameraId);
        editorState.places = places;
        
        showEditorInterface();
    } catch (error) {
        content.innerHTML = `<div class="alert alert-error">Ошибка: ${error.message}</div>`;
    }
}

function showEditorInterface() {
    const content = document.getElementById('editor-content');
    
    content.innerHTML = `
        <div class="toolbar">
            <label>Инструмент:</label>
            <button class="btn" onclick="setEditorTool('select')">👆 Выбор</button>
            <button class="btn" onclick="setEditorTool('rectangle')">▭ Прямоугольник</button>
            <button class="btn" onclick="setEditorTool('polygon')">⬡ Полигон</button>
            
            <label style="margin-left: 20px;">Тип места:</label>
            <select id="place-type-select" onchange="editorState.placeType = this.value">
                <option value="standard">Обычное</option>
                <option value="disabled">Инвалид</option>
                <option value="family">Семейное</option>
                <option value="vip">VIP</option>
                <option value="electric">Электро</option>
                <option value="short_term">Краткосрочная</option>
            </select>
            
            <button class="btn btn-secondary" onclick="saveAllPlaces()" style="margin-left: 20px;">
                💾 Сохранить все
            </button>
            <button class="btn btn-danger" onclick="deleteSelectedPlace()">
                🗑️ Удалить выбранное
            </button>
        </div>
        
        <div class="form-group">
            <label>Загрузите схему парковки:</label>
            <input type="file" id="editor-map-upload" accept="image/*" onchange="loadEditorMap()">
        </div>
        
        <div id="editor-canvas-container" style="display:none;">
            <canvas id="editor-canvas"></canvas>
        </div>
        
        <div id="places-list" style="margin-top: 20px;"></div>
    `;
    
    updatePlacesList();
}

function loadEditorMap() {
    const input = document.getElementById('editor-map-upload');
    const file = input.files[0];
    
    if (!file) return;
    
    const reader = new FileReader();
    
    reader.onload = (e) => {
        const img = new Image();
        
        img.onload = () => {
            const canvas = document.getElementById('editor-canvas');
            const ctx = canvas.getContext('2d');
            
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
            
            editorState.parkingMap = e.target.result;
            document.getElementById('editor-canvas-container').style.display = 'block';
            
            // Add event listeners
            canvas.addEventListener('click', handleEditorClick);
            canvas.addEventListener('mousemove', handleEditorMouseMove);
            
            redrawEditor();
        };
        
        img.src = e.target.result;
    };
    
    reader.readAsDataURL(file);
}

function setEditorTool(tool) {
    editorState.currentTool = tool;
    editorState.currentPolygon = [];
    showAlert(`Инструмент: ${tool}`, 'info');
}

function handleEditorClick(event) {
    const canvas = event.target;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    
    if (editorState.currentTool === 'rectangle') {
        if (editorState.currentPolygon.length === 0) {
            editorState.currentPolygon.push([x, y]);
        } else {
            const [x1, y1] = editorState.currentPolygon[0];
            const polygon = [
                [x1, y1],
                [x, y1],
                [x, y],
                [x1, y]
            ];
            
            createPlace(polygon);
            editorState.currentPolygon = [];
        }
    } else if (editorState.currentTool === 'polygon') {
        editorState.currentPolygon.push([x, y]);
        
        // Double-click or right-click to finish
        if (event.detail === 2 && editorState.currentPolygon.length >= 3) {
            createPlace([...editorState.currentPolygon]);
            editorState.currentPolygon = [];
        }
    } else if (editorState.currentTool === 'select') {
        // Check if clicked on existing place
        const clickedPlace = findPlaceAtPoint(x, y);
        if (clickedPlace) {
            editorState.selectedPlace = clickedPlace;
            showAlert(`Выбрано место ID: ${clickedPlace.id || 'новое'}`, 'info');
        }
    }
    
    redrawEditor();
}

function handleEditorMouseMove(event) {
    if (editorState.currentTool !== 'rectangle' || editorState.currentPolygon.length === 0) {
        return;
    }
    
    const canvas = event.target;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    
    // Preview rectangle
    redrawEditor();
    
    const ctx = canvas.getContext('2d');
    const [x1, y1] = editorState.currentPolygon[0];
    
    ctx.strokeStyle = 'blue';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.strokeRect(x1, y1, x - x1, y - y1);
    ctx.setLineDash([]);
}

function createPlace(polygon) {
    const place = {
        id: null,
        camera_id: editorState.cameraId,
        polygon: polygon,
        place_type: editorState.placeType,
        is_active: true
    };
    
    editorState.places.push(place);
    updatePlacesList();
    showAlert('Место добавлено. Нажмите "Сохранить все" для сохранения в БД.', 'success');
}

function findPlaceAtPoint(x, y) {
    for (const place of editorState.places) {
        if (isPointInPolygon([x, y], place.polygon)) {
            return place;
        }
    }
    return null;
}

function isPointInPolygon(point, polygon) {
    const [x, y] = point;
    let inside = false;
    
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const [xi, yi] = polygon[i];
        const [xj, yj] = polygon[j];
        
        const intersect = ((yi > y) !== (yj > y)) &&
            (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
        
        if (intersect) inside = !inside;
    }
    
    return inside;
}

function redrawEditor() {
    const canvas = document.getElementById('editor-canvas');
    if (!canvas || !editorState.parkingMap) return;
    
    const ctx = canvas.getContext('2d');
    const img = new Image();
    
    img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        
        // Draw all places
        editorState.places.forEach(place => {
            drawPolygon(ctx, place.polygon, place === editorState.selectedPlace);
        });
        
        // Draw current polygon
        if (editorState.currentPolygon.length > 0) {
            ctx.fillStyle = 'rgba(0, 123, 255, 0.3)';
            ctx.strokeStyle = 'blue';
            ctx.lineWidth = 2;
            
            ctx.beginPath();
            editorState.currentPolygon.forEach((point, i) => {
                if (i === 0) {
                    ctx.moveTo(point[0], point[1]);
                } else {
                    ctx.lineTo(point[0], point[1]);
                }
                
                // Draw point markers
                ctx.fillStyle = 'red';
                ctx.fillRect(point[0] - 3, point[1] - 3, 6, 6);
                ctx.fillStyle = 'rgba(0, 123, 255, 0.3)';
            });
            
            ctx.stroke();
        }
    };
    
    img.src = editorState.parkingMap;
}

function drawPolygon(ctx, polygon, isSelected = false) {
    ctx.fillStyle = isSelected ? 'rgba(255, 255, 0, 0.4)' : 'rgba(0, 255, 0, 0.3)';
    ctx.strokeStyle = isSelected ? 'yellow' : '#333';
    ctx.lineWidth = isSelected ? 3 : 2;
    
    ctx.beginPath();
    polygon.forEach((point, i) => {
        if (i === 0) {
            ctx.moveTo(point[0], point[1]);
        } else {
            ctx.lineTo(point[0], point[1]);
        }
    });
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
}

function updatePlacesList() {
    const listDiv = document.getElementById('places-list');
    if (!listDiv) return;
    
    if (editorState.places.length === 0) {
        listDiv.innerHTML = '<p>Места не добавлены</p>';
        return;
    }
    
    let html = `<h3>Парковочные места (${editorState.places.length})</h3><table><thead><tr><th>ID</th><th>Тип</th><th>Точек</th><th>Статус</th></tr></thead><tbody>`;
    
    editorState.places.forEach((place, idx) => {
        html += `
            <tr>
                <td>${place.id || `новое-${idx}`}</td>
                <td>${place.place_type}</td>
                <td>${place.polygon.length}</td>
                <td>${place.id ? 'Сохранено' : 'Не сохранено'}</td>
            </tr>
        `;
    });
    
    html += '</tbody></table>';
    listDiv.innerHTML = html;
}

async function saveAllPlaces() {
    const unsavedPlaces = editorState.places.filter(p => !p.id);
    
    if (unsavedPlaces.length === 0) {
        showAlert('Все места уже сохранены', 'info');
        return;
    }
    
    try {
        for (const place of unsavedPlaces) {
            const result = await api.createParkingPlace(place);
            place.id = result.id;
        }
        
        showAlert(`Сохранено ${unsavedPlaces.length} мест`, 'success');
        updatePlacesList();
        
    } catch (error) {
        showAlert(`Ошибка сохранения: ${error.message}`, 'error');
    }
}

function deleteSelectedPlace() {
    if (!editorState.selectedPlace) {
        showAlert('Выберите место для удаления', 'info');
        return;
    }
    
    if (!confirm('Удалить выбранное место?')) return;
    
    const place = editorState.selectedPlace;
    
    if (place.id) {
        api.deleteParkingPlace(place.id)
            .then(() => {
                editorState.places = editorState.places.filter(p => p !== place);
                editorState.selectedPlace = null;
                redrawEditor();
                updatePlacesList();
                showAlert('Место удалено', 'success');
            })
            .catch(error => {
                showAlert(`Ошибка удаления: ${error.message}`, 'error');
            });
    } else {
        editorState.places = editorState.places.filter(p => p !== place);
        editorState.selectedPlace = null;
        redrawEditor();
        updatePlacesList();
        showAlert('Место удалено', 'success');
    }
}

// ============ MONITOR PAGE ============
let monitorInterval = null;

async function loadMonitorPage() {
    const main = document.getElementById('main-content');
    
    main.innerHTML = `
        <h2>Мониторинг парковки</h2>
        
        <div class="stats-grid" id="monitor-stats"></div>
        
        <div class="toolbar">
            <button class="btn" onclick="refreshMonitor()">🔄 Обновить</button>
            <button class="btn btn-secondary" onclick="toggleAutoRefresh()">
                <span id="auto-refresh-text">▶️ Авто-обновление</span>
            </button>
        </div>
        
        <div id="monitor-content"></div>
    `;
    
    await refreshMonitor();
}

async function refreshMonitor() {
    try {
        const occupancy = await api.getCurrentOccupancy();
        
        // Update stats
        const statsDiv = document.getElementById('monitor-stats');
        statsDiv.innerHTML = `
            <div class="stat-card">
                <h3>Всего мест</h3>
                <div class="value">${occupancy.total}</div>
            </div>
            <div class="stat-card">
                <h3>Занято</h3>
                <div class="value" style="color: #e74c3c;">${occupancy.occupied}</div>
            </div>
            <div class="stat-card">
                <h3>Свободно</h3>
                <div class="value" style="color: #27ae60;">${occupancy.free}</div>
            </div>
            <div class="stat-card">
                <h3>Загрузка</h3>
                <div class="value">${occupancy.occupancy_rate}%</div>
            </div>
        `;
        
        // Show places list
        const contentDiv = document.getElementById('monitor-content');
        
        if (occupancy.places && occupancy.places.length > 0) {
            let html = '<h3>Статус мест</h3><table><thead><tr><th>ID</th><th>Тип</th><th>Статус</th><th>Последнее обновление</th></tr></thead><tbody>';
            
            occupancy.places.forEach(place => {
                const status = place.is_occupied ? 
                    '<span class="status-offline">Занято</span>' : 
                    '<span class="status-online">Свободно</span>';
                
                html += `
                    <tr>
                        <td>${place.id}</td>
                        <td>${place.place_type}</td>
                        <td>${status}</td>
                        <td>${place.last_updated || '-'}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table>';
            contentDiv.innerHTML = html;
        } else {
            contentDiv.innerHTML = '<p>Нет данных о местах</p>';
        }
        
    } catch (error) {
        showAlert(`Ошибка обновления: ${error.message}`, 'error');
    }
}

function toggleAutoRefresh() {
    if (monitorInterval) {
        clearInterval(monitorInterval);
        monitorInterval = null;
        document.getElementById('auto-refresh-text').textContent = '▶️ Авто-обновление';
    } else {
        monitorInterval = setInterval(refreshMonitor, CONFIG.POLL_INTERVAL);
        document.getElementById('auto-refresh-text').textContent = '⏸️ Остановить';
        showAlert('Авто-обновление включено', 'success');
    }
}

// ============ ANALYTICS PAGE ============
async function loadAnalyticsPage() {
    const main = document.getElementById('main-content');
    
    main.innerHTML = `
        <h2>Аналитика</h2>
        
        <div class="toolbar">
            <label>Период:</label>
            <select id="analytics-period" onchange="refreshAnalytics()">
                <option value="day">День</option>
                <option value="week">Неделя</option>
                <option value="month">Месяц</option>
            </select>
            
            <button class="btn" onclick="refreshAnalytics()">🔄 Обновить</button>
            <button class="btn btn-secondary" onclick="exportReport()">📥 Экспорт PDF</button>
        </div>
        
        <div id="analytics-content"></div>
    `;
    
    await refreshAnalytics();
}

async function refreshAnalytics() {
    const contentDiv = document.getElementById('analytics-content');
    contentDiv.innerHTML = showLoading();
    
    const period = document.getElementById('analytics-period').value;
    
    try {
        const [history, anomalies] = await Promise.all([
            api.getOccupancyHistory(period),
            api.getAnomalies()
        ]);
        
        let html = '<div class="grid-2col">';
        
        // History chart (simplified - just show data)
        html += '<div><h3>История загрузки</h3>';
        if (history && history.length > 0) {
            html += '<table><thead><tr><th>Время</th><th>Занято</th><th>Свободно</th></tr></thead><tbody>';
            history.slice(0, 10).forEach(record => {
                html += `<tr><td>${record.timestamp}</td><td>${record.occupied}</td><td>${record.free}</td></tr>`;
            });
            html += '</tbody></table>';
        } else {
            html += '<p>Нет данных</p>';
        }
        html += '</div>';
        
        // Anomalies
        html += '<div><h3>Аномалии</h3>';
        if (anomalies && anomalies.length > 0) {
            html += '<table><thead><tr><th>ID места</th><th>Тип</th><th>Длительность</th></tr></thead><tbody>';
            anomalies.forEach(anomaly => {
                html += `<tr><td>${anomaly.place_id}</td><td>${anomaly.anomaly_type}</td><td>${anomaly.duration_hours}ч</td></tr>`;
            });
            html += '</tbody></table>';
        } else {
            html += '<p>Аномалий не обнаружено</p>';
        }
        html += '</div>';
        
        html += '</div>';
        contentDiv.innerHTML = html;
        
    } catch (error) {
        contentDiv.innerHTML = `<div class="alert alert-error">Ошибка: ${error.message}</div>`;
    }
}

async function exportReport() {
    const period = document.getElementById('analytics-period').value;
    
    try {
        showAlert('Генерация отчета...', 'info');
        const blob = await api.exportReport('pdf', period);
        
        // Download file
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `parking_report_${period}_${Date.now()}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showAlert('Отчет загружен', 'success');
        
    } catch (error) {
        showAlert(`Ошибка экспорта: ${error.message}`, 'error');
    }
}

// Stop auto-refresh when leaving monitor page
window.addEventListener('beforeunload', () => {
    if (monitorInterval) {
        clearInterval(monitorInterval);
    }
});
