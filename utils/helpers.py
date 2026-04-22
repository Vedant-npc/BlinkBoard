"""
Helper utilities for BlinkBoard system.
Contains common functions used across modules.
"""

import math
import numpy as np


def calculate_distance(point1, point2):
    """
    Calculate Euclidean distance between two 2D points.
    
    Args:
        point1: Tuple (x1, y1)
        point2: Tuple (x2, y2)
    
    Returns:
        float: Distance between points
    """
    return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)


def calculate_eye_aspect_ratio(eye_landmarks):
    """
    Calculate Eye Aspect Ratio (EAR) for blink detection.
    Uses distances between specific eye landmark points.
    
    Args:
        eye_landmarks: List of 6 (x, y) tuples representing eye landmarks
    
    Returns:
        float: Eye aspect ratio
    """
    if len(eye_landmarks) != 6:
        return 0.0
    
    # Vertical distances
    A = calculate_distance(eye_landmarks[1], eye_landmarks[5])
    B = calculate_distance(eye_landmarks[2], eye_landmarks[4])
    
    # Horizontal distance
    C = calculate_distance(eye_landmarks[0], eye_landmarks[3])
    
    # Calculate EAR
    ear = (A + B) / (2.0 * C)
    return ear


def smooth_gaze_direction(current_gaze, previous_gaze, alpha=0.6):
    """
    Apply exponential smoothing to gaze direction for stability.
    Lower alpha = more smoothing, higher alpha = more responsive.
    
    Args:
        current_gaze: Current gaze direction (x, y) coordinates
        previous_gaze: Previous gaze direction (x, y) coordinates
        alpha: Smoothing factor (0.0 to 1.0) - default 0.6 for better stability
    
    Returns:
        tuple: Smoothed gaze direction
    """
    if previous_gaze is None:
        return current_gaze
    
    smoothed_x = alpha * current_gaze[0] + (1 - alpha) * previous_gaze[0]
    smoothed_y = alpha * current_gaze[1] + (1 - alpha) * previous_gaze[1]
    
    return (smoothed_x, smoothed_y)


def smooth_iris_coordinates(iris_coords, previous_coords, alpha=0.5):
    """
    Apply Kalman-like smoothing to iris coordinates to reduce jitter.
    Uses lower alpha for iris coordinates to reduce noise.
    
    Args:
        iris_coords: Current iris (x, y) pixel coordinates
        previous_coords: Previous iris (x, y) pixel coordinates
        alpha: Smoothing factor (0.0 to 1.0) - default 0.5 for heavy smoothing
    
    Returns:
        tuple: Smoothed iris coordinates
    """
    if previous_coords is None or iris_coords is None:
        return iris_coords
    
    smoothed_x = alpha * iris_coords[0] + (1 - alpha) * previous_coords[0]
    smoothed_y = alpha * iris_coords[1] + (1 - alpha) * previous_coords[1]
    
    return (smoothed_x, smoothed_y)


def get_gaze_quadrant(gaze_direction, threshold=0.1):
    """
    Determine gaze quadrant (left, right, up, down, center).
    
    Args:
        gaze_direction: Tuple (gaze_x, gaze_y) normalized between -1 and 1
        threshold: Threshold for center detection
    
    Returns:
        str: Gaze direction ('left', 'right', 'up', 'down', 'center')
    """
    gaze_x, gaze_y = gaze_direction
    
    if abs(gaze_x) < threshold and abs(gaze_y) < threshold:
        return "center"
    elif abs(gaze_x) > abs(gaze_y):
        return "right" if gaze_x > 0 else "left"
    else:
        return "down" if gaze_y > 0 else "up"


def normalize_coordinates(value, min_val, max_val, new_min=0, new_max=1):
    """
    Normalize a value from one range to another.
    
    Args:
        value: Value to normalize
        min_val: Current minimum
        max_val: Current maximum
        new_min: New minimum
        new_max: New maximum
    
    Returns:
        float: Normalized value
    """
    if max_val - min_val == 0:
        return new_min
    
    return new_min + (value - min_val) / (max_val - min_val) * (new_max - new_min)


class GazeBuffer:
    """Buffer for storing and averaging gaze positions."""
    
    def __init__(self, buffer_size=5):
        self.buffer_size = buffer_size
        self.buffer = []
    
    def add(self, gaze_point):
        """Add a gaze point to buffer."""
        self.buffer.append(gaze_point)
        if len(self.buffer) > self.buffer_size:
            self.buffer.pop(0)
    
    def get_average(self):
        """Get average gaze point from buffer."""
        if not self.buffer:
            return None
        
        avg_x = sum(p[0] for p in self.buffer) / len(self.buffer)
        avg_y = sum(p[1] for p in self.buffer) / len(self.buffer)
        
        return (avg_x, avg_y)
    
    def clear(self):
        """Clear the buffer."""
        self.buffer = []
