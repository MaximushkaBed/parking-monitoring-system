"""
Image preprocessing module for extreme weather conditions
Handles: night, snow, rain, fog, overexposure
"""

import cv2
import numpy as np
from typing import Tuple, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class WeatherCondition(Enum):
    """Weather/lighting conditions"""
    NORMAL = "normal"
    NIGHT = "night"
    SNOW = "snow"
    RAIN = "rain"
    FOG = "fog"
    OVEREXPOSED = "overexposed"


class ImagePreprocessor:
    """
    Adaptive image preprocessing for parking monitoring
    
    Handles various weather and lighting conditions to improve detection quality
    """
    
    def __init__(
        self,
        auto_detect: bool = True,
        target_brightness: int = 128,
        clahe_clip_limit: float = 2.0,
        clahe_tile_size: int = 8
    ):
        """
        Initialize preprocessor
        
        Args:
            auto_detect: Automatically detect weather conditions
            target_brightness: Target mean brightness (0-255)
            clahe_clip_limit: CLAHE contrast limit
            clahe_tile_size: CLAHE tile grid size
        """
        self.auto_detect = auto_detect
        self.target_brightness = target_brightness
        self.clahe_clip_limit = clahe_clip_limit
        self.clahe_tile_size = clahe_tile_size
        
        # Create CLAHE object for contrast enhancement
        self.clahe = cv2.createCLAHE(
            clipLimit=clahe_clip_limit,
            tileGridSize=(clahe_tile_size, clahe_tile_size)
        )
    
    def detect_condition(self, frame: np.ndarray) -> WeatherCondition:
        """
        Auto-detect weather/lighting condition from frame
        
        Args:
            frame: Input image (BGR)
            
        Returns:
            Detected weather condition
        """
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate statistics
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)
        
        # Detect overexposure (too bright)
        if mean_brightness > 200:
            return WeatherCondition.OVEREXPOSED
        
        # Detect night (too dark)
        if mean_brightness < 60:
            return WeatherCondition.NIGHT
        
        # Detect fog (low contrast)
        if std_brightness < 30 and 80 < mean_brightness < 180:
            return WeatherCondition.FOG
        
        # Detect snow/rain (high frequency noise)
        # Use Laplacian variance as sharpness measure
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if laplacian_var < 100:  # Blurry image
            # Check if it's uniformly bright (snow) or dark (rain)
            if mean_brightness > 140:
                return WeatherCondition.SNOW
            else:
                return WeatherCondition.RAIN
        
        return WeatherCondition.NORMAL
    
    def preprocess(
        self,
        frame: np.ndarray,
        condition: Optional[WeatherCondition] = None
    ) -> Tuple[np.ndarray, WeatherCondition]:
        """
        Preprocess frame based on weather condition
        
        Args:
            frame: Input image (BGR)
            condition: Weather condition (auto-detect if None)
            
        Returns:
            Tuple of (preprocessed_frame, detected_condition)
        """
        if condition is None and self.auto_detect:
            condition = self.detect_condition(frame)
        elif condition is None:
            condition = WeatherCondition.NORMAL
        
        # Apply condition-specific preprocessing
        if condition == WeatherCondition.NIGHT:
            processed = self._process_night(frame)
        elif condition == WeatherCondition.SNOW:
            processed = self._process_snow(frame)
        elif condition == WeatherCondition.RAIN:
            processed = self._process_rain(frame)
        elif condition == WeatherCondition.FOG:
            processed = self._process_fog(frame)
        elif condition == WeatherCondition.OVEREXPOSED:
            processed = self._process_overexposed(frame)
        else:
            processed = self._process_normal(frame)
        
        return processed, condition
    
    def _process_normal(self, frame: np.ndarray) -> np.ndarray:
        """Process normal conditions - minimal processing"""
        # Light brightness adjustment if needed
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)
        
        if abs(mean_brightness - self.target_brightness) > 20:
            # Adjust brightness
            alpha = self.target_brightness / mean_brightness
            frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=0)
        
        return frame
    
    def _process_night(self, frame: np.ndarray) -> np.ndarray:
        """
        Process night conditions
        - Increase brightness
        - Reduce noise
        - Enhance contrast
        """
        logger.debug("Applying night preprocessing")
        
        # Convert to LAB color space
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L channel
        l = self.clahe.apply(l)
        
        # Merge back
        lab = cv2.merge([l, a, b])
        frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        # Denoise
        frame = cv2.fastNlMeansDenoisingColored(frame, None, 10, 10, 7, 21)
        
        # Gamma correction (brighten)
        gamma = 1.5
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
        frame = cv2.LUT(frame, table)
        
        return frame
    
    def _process_snow(self, frame: np.ndarray) -> np.ndarray:
        """
        Process snow conditions
        - Reduce brightness
        - Denoise
        - Enhance contrast
        """
        logger.debug("Applying snow preprocessing")
        
        # Reduce overall brightness
        frame = cv2.convertScaleAbs(frame, alpha=0.9, beta=-10)
        
        # Bilateral filter to reduce noise while preserving edges
        frame = cv2.bilateralFilter(frame, 9, 75, 75)
        
        # Enhance contrast
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        lab = cv2.merge([l, a, b])
        frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return frame
    
    def _process_rain(self, frame: np.ndarray) -> np.ndarray:
        """
        Process rain conditions
        - Denoise
        - Deblur
        - Enhance contrast
        """
        logger.debug("Applying rain preprocessing")
        
        # Gaussian blur to reduce rain streaks
        frame = cv2.GaussianBlur(frame, (5, 5), 0)
        
        # Median filter to remove salt-and-pepper noise
        frame = cv2.medianBlur(frame, 5)
        
        # Enhance contrast
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        lab = cv2.merge([l, a, b])
        frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        # Sharpen
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        frame = cv2.filter2D(frame, -1, kernel)
        
        return frame
    
    def _process_fog(self, frame: np.ndarray) -> np.ndarray:
        """
        Process fog conditions
        - Dehaze
        - Enhance contrast
        - Increase saturation
        """
        logger.debug("Applying fog preprocessing")
        
        # Dark channel prior dehazing (simplified)
        # Convert to float
        frame_float = frame.astype(np.float64) / 255.0
        
        # Estimate atmospheric light
        dark_channel = np.min(frame_float, axis=2)
        atmospheric_light = np.percentile(frame_float, 95, axis=(0, 1))
        
        # Transmission map
        omega = 0.95
        transmission = 1 - omega * dark_channel
        transmission = np.maximum(transmission, 0.1)
        
        # Recover scene radiance
        transmission = transmission[:, :, np.newaxis]
        frame_float = (frame_float - atmospheric_light) / transmission + atmospheric_light
        frame_float = np.clip(frame_float, 0, 1)
        
        frame = (frame_float * 255).astype(np.uint8)
        
        # Enhance contrast with CLAHE
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        lab = cv2.merge([l, a, b])
        frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        # Increase saturation
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        s = cv2.convertScaleAbs(s, alpha=1.3, beta=0)
        hsv = cv2.merge([h, s, v])
        frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        return frame
    
    def _process_overexposed(self, frame: np.ndarray) -> np.ndarray:
        """
        Process overexposed conditions
        - Reduce brightness
        - Recover highlights
        """
        logger.debug("Applying overexposure correction")
        
        # Reduce brightness
        frame = cv2.convertScaleAbs(frame, alpha=0.8, beta=-20)
        
        # Tone mapping to recover highlights
        frame_float = frame.astype(np.float32) / 255.0
        tonemap = cv2.createTonemapDrago(gamma=1.0, saturation=1.0, bias=0.85)
        frame_float = tonemap.process(frame_float)
        frame = np.clip(frame_float * 255, 0, 255).astype(np.uint8)
        
        return frame
    
    def get_stats(self, frame: np.ndarray) -> dict:
        """
        Get frame statistics for debugging
        
        Args:
            frame: Input image
            
        Returns:
            Dictionary with statistics
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        return {
            'mean_brightness': float(np.mean(gray)),
            'std_brightness': float(np.std(gray)),
            'min_brightness': int(np.min(gray)),
            'max_brightness': int(np.max(gray)),
            'sharpness': float(cv2.Laplacian(gray, cv2.CV_64F).var())
        }


def create_preprocessor(config: dict = None) -> ImagePreprocessor:
    """
    Factory function to create preprocessor with config
    
    Args:
        config: Configuration dictionary
        
    Returns:
        ImagePreprocessor instance
    """
    if config is None:
        config = {}
    
    return ImagePreprocessor(
        auto_detect=config.get('auto_detect', True),
        target_brightness=config.get('target_brightness', 128),
        clahe_clip_limit=config.get('clahe_clip_limit', 2.0),
        clahe_tile_size=config.get('clahe_tile_size', 8)
    )
