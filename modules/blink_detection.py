"""
Blink Detection Module
Detects blinks using Eye Aspect Ratio (EAR) method.
Includes long blink detection for selection functionality.
"""

import time
from collections import deque
from utils.helpers import calculate_eye_aspect_ratio, calculate_distance


class BlinkDetector:
    """
    Detects blinks using Eye Aspect Ratio (EAR) algorithm.
    Supports normal blinks and long blinks (for selection).
    """
    
    # Eye landmark indices for EAR calculation
    LEFT_EYE_INDICES = [362, 382, 381, 380, 374, 373]
    RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
    
    def __init__(self, ear_threshold=0.25, blink_duration=3, long_blink_duration_ms=500):
        """
        Initialize blink detector.
        
        Args:
            ear_threshold: Eye Aspect Ratio threshold for blink detection (default 0.25)
            blink_duration: Minimum frames with closed eyes to register normal blink (default 3)
            long_blink_duration_ms: Duration for long blink selection in ms (default 500ms)
        """
        self.ear_threshold = ear_threshold
        self.blink_duration = blink_duration
        self.long_blink_duration_ms = long_blink_duration_ms / 1000.0  # Convert to seconds
        self.blink_counter = 0
        self.blink_detected = False
        self.total_blinks = 0
        
        # Debounce mechanism: prevent multiple blink selections per actual blink
        self.last_blink_processed_time = 0
        self.blink_cooldown_frames = 20  # ~600ms at 30fps - time between blink selections
        
        # Store recent EAR values for smoothing
        self.ear_history = deque(maxlen=5)
        
        # Long blink tracking for selection
        self.blink_start_time = None
        self.eyes_closed_duration = 0.0
        self.current_ear = 0.0
    
    def detect_blink(self, landmarks, eye_tracker):
        """
        Detect blink from face landmarks with debounce protection.
        
        Args:
            landmarks: Dictionary of face landmarks
            eye_tracker: EyeTracker instance (for getting eye landmarks)
        
        Returns:
            bool: True if blink detected and debounce time elapsed, False otherwise
        """
        if landmarks is None:
            return False
        
        try:
            # Get eye landmarks
            left_eye_points = []
            for idx in self.LEFT_EYE_INDICES:
                if idx in landmarks:
                    left_eye_points.append(landmarks[idx])
            
            right_eye_points = []
            for idx in self.RIGHT_EYE_INDICES:
                if idx in landmarks:
                    right_eye_points.append(landmarks[idx])
            
            if len(left_eye_points) < 6 or len(right_eye_points) < 6:
                return False
            
            # Calculate EAR for both eyes
            left_ear = calculate_eye_aspect_ratio(left_eye_points)
            right_ear = calculate_eye_aspect_ratio(right_eye_points)
            
            # Average EAR
            avg_ear = (left_ear + right_ear) / 2.0
            self.ear_history.append(avg_ear)
            
            # Smooth EAR over recent frames
            smoothed_ear = sum(self.ear_history) / len(self.ear_history)
            
            # Decrease cooldown counter
            if self.last_blink_processed_time > 0:
                self.last_blink_processed_time -= 1
            
            # Blink detection logic
            if smoothed_ear < self.ear_threshold:
                self.blink_counter += 1
            else:
                # Eyes are open - check if we completed a blink
                if self.blink_counter >= self.blink_duration:
                    # Check debounce - only process blink if enough time has passed
                    if self.last_blink_processed_time <= 0:
                        self.blink_detected = True
                        self.total_blinks += 1
                        self.last_blink_processed_time = self.blink_cooldown_frames
                        self.blink_counter = 0
                        return True
                    else:
                        # Still in cooldown - ignore this blink
                        self.blink_counter = 0
                        self.blink_detected = False
                else:
                    self.blink_counter = 0
                    self.blink_detected = False
            
            return False
        
        except Exception as e:
            print(f"Error detecting blink: {e}")
            return False
    
    def get_blink_count(self):
        """Get total number of blinks detected."""
        return self.total_blinks
    
    def reset_blink_count(self):
        """Reset blink counter."""
        self.total_blinks = 0
        self.blink_counter = 0
        self.blink_detected = False
    
    def set_threshold(self, threshold):
        """
        Adjust blink detection threshold.
        Lower values = more sensitive to blinks.
        
        Args:
            threshold: New EAR threshold
        """
        self.ear_threshold = threshold
    
    def get_eye_aspect_ratio(self, landmarks):
        """
        Get current eye aspect ratio for debugging and advanced selection.
        
        Args:
            landmarks: Dictionary of face landmarks
        
        Returns:
            float: Average EAR of both eyes
        """
        if landmarks is None:
            return None
        
        try:
            left_eye_points = [landmarks.get(idx, (0, 0)) for idx in self.LEFT_EYE_INDICES]
            right_eye_points = [landmarks.get(idx, (0, 0)) for idx in self.RIGHT_EYE_INDICES]
            
            left_ear = calculate_eye_aspect_ratio(left_eye_points)
            right_ear = calculate_eye_aspect_ratio(right_eye_points)
            
            self.current_ear = (left_ear + right_ear) / 2.0
            return self.current_ear
        
        except Exception as e:
            print(f"Error calculating EAR: {e}")
            return None
    
    def detect_long_blink(self, ear):
        """
        Detect if eyes are held closed for selection (long blink).
        
        Args:
            ear: Current Eye Aspect Ratio
            
        Returns:
            dict: Status with 'eyes_closed', 'duration', and 'selection' flag
        """
        current_time = time.time()
        
        status = {
            'eyes_closed': ear < self.ear_threshold,
            'duration': 0.0,
            'long_blink': False
        }
        
        if ear < self.ear_threshold:
            # Eyes are closed
            if self.blink_start_time is None:
                self.blink_start_time = current_time
            
            self.eyes_closed_duration = current_time - self.blink_start_time
            status['duration'] = self.eyes_closed_duration
            
            # Check if closed long enough for selection
            if self.eyes_closed_duration >= self.long_blink_duration_ms:
                status['long_blink'] = True
        else:
            # Eyes are open
            self.eyes_closed_duration = 0.0
            self.blink_start_time = None
        
        return status

