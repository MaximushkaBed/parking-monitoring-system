// API Client for Parking System Backend

class API {
    constructor(baseURL) {
        this.baseURL = baseURL;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    // Cameras
    async getCameras() {
        return this.request('/cameras');
    }

    async getCamera(id) {
        return this.request(`/cameras/${id}`);
    }

    async createCamera(data) {
        return this.request('/cameras', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updateCamera(id, data) {
        return this.request(`/cameras/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async deleteCamera(id) {
        return this.request(`/cameras/${id}`, {
            method: 'DELETE'
        });
    }

    async getCameraStatus(id) {
        return this.request(`/cameras/${id}/status`);
    }

    async getCameraFrame(id) {
        return this.request(`/cameras/${id}/frame`);
    }

    // Calibration
    async calibrateCamera(id, data) {
        return this.request(`/calibration/${id}`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async getCalibration(id) {
        return this.request(`/calibration/${id}`);
    }

    // Parking Places
    async getParkingPlaces(cameraId = null) {
        const query = cameraId ? `?camera_id=${cameraId}` : '';
        return this.request(`/parking-places${query}`);
    }

    async createParkingPlace(data) {
        return this.request('/parking-places', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updateParkingPlace(id, data) {
        return this.request(`/parking-places/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async deleteParkingPlace(id) {
        return this.request(`/parking-places/${id}`, {
            method: 'DELETE'
        });
    }

    async bulkCreateParkingPlaces(data) {
        return this.request('/parking-places/bulk', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    // Zones
    async getZones() {
        return this.request('/zones');
    }

    async createZone(data) {
        return this.request('/zones', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updateZone(id, data) {
        return this.request(`/zones/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async deleteZone(id) {
        return this.request(`/zones/${id}`, {
            method: 'DELETE'
        });
    }

    // Analytics
    async getCurrentOccupancy() {
        return this.request('/analytics/current');
    }

    async getOccupancyHistory(period = 'day') {
        return this.request(`/analytics/history?period=${period}`);
    }

    async getAnomalies() {
        return this.request('/analytics/anomalies');
    }

    async getHeatmap() {
        return this.request('/analytics/heatmap');
    }

    async exportReport(format = 'pdf', period = 'day') {
        const response = await fetch(
            `${this.baseURL}/analytics/export?format=${format}&period=${period}`
        );
        
        if (!response.ok) {
            throw new Error(`Export failed: ${response.status}`);
        }

        const blob = await response.blob();
        return blob;
    }

    // Detections
    async getLatestDetections(cameraId = null) {
        const query = cameraId ? `?camera_id=${cameraId}` : '';
        return this.request(`/detections/latest${query}`);
    }
}

// Create global API instance
const api = new API(CONFIG.API_BASE_URL);
