"""
Advanced Selection Module
Implements dwell time selection and improved blink detection.
"""

import time
from collections import deque
from collections import Counter


class AdvancedSelection:
    """
    Confirmation-based selection system.
    Track stable focus on keys, require explicit confirmation (blink) to select.
    No auto-selection via dwell time - must confirm with blink or key press.
    """
    
    def __init__(
        self,
        stable_frames=5,
        long_blink_duration_ms=400,
        time_fn=None,
    ):
        """
        Initialize confirmation-based selection.
        
        Args:
            stable_frames: Number of frames gaze must stay on same key (default 5)
            long_blink_duration_ms: Duration for blink-based confirmation
            time_fn: Optional time provider for testing
        """
        self.stable_frames = max(2, int(stable_frames))
        self.long_blink_duration_ms = long_blink_duration_ms / 1000.0
        self._time_fn = time_fn or time.time
        
        # Key tracking for stability
        self.current_key = None
        self.stable_key = None  # Key that has been stable
        self.stability_counter = 0  # Frames on same key
        
        # Key history for consensus
        self.key_history = deque(maxlen=5)
        
        # Blink tracking for confirmation
        self.blink_start_time = None
        self.eyes_closed_duration = 0.0
        self.can_confirm = False  # User can confirm selection
    
    def update_gaze_position(self, key_name):
        """
        Track gaze position and build stability on a key.
        Does NOT auto-select - waits for confirmation via blink.
        
        Args:
            key_name: Name of key being looked at, or None
            
        Returns:
            dict: Status with current_key, is_stable, stability_progress
        """
        status = {
            'current_key': None,
            'is_stable': False,
            'stability_progress': 0.0,
            'ready_to_confirm': False
        }
        
        # Handle no key
        if key_name is None or not str(key_name).strip():
            self.key_history.clear()
            self.current_key = None
            self.stable_key = None
            self.stability_counter = 0
            return status
        
        key_name = str(key_name).strip()
        self.key_history.append(key_name)
        
        # Check if key changed
        if key_name != self.current_key:
            self.current_key = key_name
            self.stability_counter = 1
            self.stable_key = None
        else:
            # Same key - increment stability
            self.stability_counter = min(self.stability_counter + 1, self.stable_frames + 1)
        
        # Return current tracking key
        status['current_key'] = key_name
        status['stability_progress'] = min(1.0, self.stability_counter / self.stable_frames)
        
        # Check if stable
        if self.stability_counter >= self.stable_frames:
            status['is_stable'] = True
            status['ready_to_confirm'] = True
            self.stable_key = self.current_key
            self.can_confirm = True
        
        return status
    
    def detect_confirmation_blink(self, ear, ear_threshold=0.2):
        """
        Detect blink for confirmation of selection.
        Must have stable key ready before confirmation works.
        
        Args:
            ear: Eye Aspect Ratio
            ear_threshold: Threshold for closed eyes
            
        Returns:
            dict: Status with 'confirmed' key and selection
        """
        current_time = self._time_fn()
        status = {
            'eyes_closed': ear < ear_threshold,
            'blink_duration': 0.0,
            'confirmed': False,
            'confirmed_key': None
        }
        
        if ear < ear_threshold:
            # Eyes closing
            if self.blink_start_time is None:
                self.blink_start_time = current_time
            
            self.eyes_closed_duration = current_time - self.blink_start_time
            status['blink_duration'] = self.eyes_closed_duration
            
            # Check if blink long enough for confirmation
            if self.eyes_closed_duration >= self.long_blink_duration_ms:
                if self.can_confirm and self.stable_key:
                    status['confirmed'] = True
                    status['confirmed_key'] = self.stable_key
                    # Reset for next selection
                    self._reset_selection()
        else:
            # Eyes opening - reset blink tracking
            self.eyes_closed_duration = 0.0
            self.blink_start_time = None
        
        return status
    
    def _reset_selection(self):
        """Reset selection state after confirmation."""
        self.key_history.clear()
        self.current_key = None
        self.stable_key = None
        self.stability_counter = 0
        self.can_confirm = False
    
    def reset_dwell(self):
        """Reset selection state."""
        self._reset_selection()
    
    def reset_blink(self):
        """Reset blink tracking."""
        self.blink_start_time = None
        self.eyes_closed_duration = 0.0
    
    def get_stable_key(self):
        """Get the currently stable key, or None."""
        return self.stable_key


class GazeSmoothing:
    """
    Apply strong smoothing to gaze coordinates using dual-stage filtering.
    Combines exponential smoothing + moving average for maximum stability.
    Reduces jitter and improves selection accuracy.
    """
    
    def __init__(self, alpha=0.5, buffer_size=8, dead_zone_threshold=0.01):
        """
        Initialize smoothing filter with multiple stages.
        
        Args:
            alpha: Exponential smoothing factor (0 to 1)
                   0.5 = strong smoothing (stable, slower response)
                   0.7 = balanced (default was 0.7)
                   0.9 = light smoothing (responsive but noisy)
            buffer_size: Number of samples for moving average (default 8)
                        Higher = smoother but more lag
            dead_zone_threshold: Ignore movements smaller than this (0-1 normalized)
                                Default 0.01 = ~6-10 pixels at 640x480
        """
        self.alpha = alpha
        self.buffer_size = buffer_size
        self.dead_zone_threshold = dead_zone_threshold
        
        # Multiple smoothing stages
        self.prev_x = None
        self.prev_y = None
        
        # Moving average buffer for second stage filtering
        self.x_buffer = deque(maxlen=buffer_size)
        self.y_buffer = deque(maxlen=buffer_size)
        
        # Track last "real" movement to apply dead zone
        self.last_reported_x = None
        self.last_reported_y = None
    
    def smooth(self, gaze_x, gaze_y):
        """
        Apply two-stage smoothing: exponential + moving average + dead zone.
        Produces very stable gaze tracking with minimal jitter.
        
        Args:
            gaze_x: Current normalized gaze X (0 to 1)
            gaze_y: Current normalized gaze Y (0 to 1)
            
        Returns:
            tuple: (smoothed_x, smoothed_y)
        """
        if gaze_x is None or gaze_y is None:
            return gaze_x, gaze_y
        
        # STAGE 1: Exponential smoothing
        if self.prev_x is None:
            self.prev_x = gaze_x
            self.prev_y = gaze_y
        else:
            # Heavy exponential smoothing to reduce rapid jitter
            gaze_x = self.alpha * gaze_x + (1 - self.alpha) * self.prev_x
            gaze_y = self.alpha * gaze_y + (1 - self.alpha) * self.prev_y
            self.prev_x = gaze_x
            self.prev_y = gaze_y
        
        # STAGE 2: Moving average for second-layer stability
        self.x_buffer.append(gaze_x)
        self.y_buffer.append(gaze_y)
        
        avg_x = sum(self.x_buffer) / len(self.x_buffer) if self.x_buffer else gaze_x
        avg_y = sum(self.y_buffer) / len(self.y_buffer) if self.y_buffer else gaze_y
        
        # STAGE 3: Dead zone - ignore micro-movements
        if self.last_reported_x is None:
            self.last_reported_x = avg_x
            self.last_reported_y = avg_y
        else:
            # Only update if movement exceeds dead zone threshold
            delta_x = abs(avg_x - self.last_reported_x)
            delta_y = abs(avg_y - self.last_reported_y)
            
            if delta_x > self.dead_zone_threshold or delta_y > self.dead_zone_threshold:
                self.last_reported_x = avg_x
                self.last_reported_y = avg_y
            else:
                # Stay with last reported value (dead zone active)
                avg_x = self.last_reported_x
                avg_y = self.last_reported_y
        
        # Clamp to valid range
        avg_x = max(0.0, min(1.0, avg_x))
        avg_y = max(0.0, min(1.0, avg_y))
        
        return avg_x, avg_y
    
    def reset(self):
        """Reset smoothing state."""
        self.prev_x = None
        self.prev_y = None
        self.x_buffer.clear()
        self.y_buffer.clear()
        self.last_reported_x = None
        self.last_reported_y = None


class GridSnapping:
    """
    Snap gaze position to nearest keyboard key with magnetic snapping.
    - Uses safe zones (reduced active areas) inside each key
    - Implements magnetic snapping to lock onto nearest key
    - Prevents jitter with hysteresis
    - Minimum 20-40px spacing between keys
    """
    
    def __init__(self, grid_keys):
        """
        Initialize grid snapping with improved accuracy and stability.
        
        Args:
            grid_keys: Dictionary mapping key names to {'x', 'y', 'width', 'height'}
        """
        self.grid_keys = grid_keys
        self.previous_key = None  # For hysteresis
        self.locked_key = None  # For magnetic locking
        self.lock_frames = 0  # Frames locked on current key
        self.safe_zone_padding = 12  # Reduce active area by this amount (pixels) - increased from 8
        self.magnetic_threshold = 50  # Pixels away to start magnetically snapping (reduced from 60)
        self.lock_duration = 10  # Frames to remain locked after gaze leaves (doubled from 5)
    
    def snap_to_nearest_key(self, gaze_norm_x, gaze_norm_y, frame_width, frame_height):
        """
        Find nearest key with magnetic snapping and hysteresis.
        Uses safe zones to reduce false positives from gaze jitter.
        
        Args:
            gaze_norm_x: Normalized gaze X (0 to 1)
            gaze_norm_y: Normalized gaze Y (0 to 1)
            frame_width: Keyboard width in pixels
            frame_height: Keyboard height in pixels
            
        Returns:
            str: Name of snapped key, or None
        """
        if gaze_norm_x is None or gaze_norm_y is None:
            self.lock_frames = 0
            self.locked_key = None
            return None

        # Convert to pixel coordinates
        gaze_px = gaze_norm_x * frame_width
        gaze_py = gaze_norm_y * frame_height

        if not self.grid_keys:
            return None

        # Calculate keyboard bounds
        min_x = min(k['x'] for k in self.grid_keys.values())
        min_y = min(k['y'] for k in self.grid_keys.values())
        max_x = max(k['x'] + k['width'] for k in self.grid_keys.values())
        max_y = max(k['y'] + k['height'] for k in self.grid_keys.values())
        
        # Only use safe zone (40px margin from keyboard edge)
        safe_margin = 40
        if (gaze_px < min_x - safe_margin or gaze_px > max_x + safe_margin or
            gaze_py < min_y - safe_margin or gaze_py > max_y + safe_margin):
            self.lock_frames = 0
            self.locked_key = None
            return None

        # STEP 1: Try exact match in safe zone (90% of key area)
        exact_match = self._find_key_at_safe_zone(gaze_px, gaze_py)
        if exact_match:
            self.locked_key = exact_match
            self.lock_frames = 0
            return exact_match

        # STEP 2: No exact match - find nearest key
        nearest_key, distance = self._find_nearest_key(gaze_px, gaze_py)
        
        if nearest_key is None:
            self.lock_frames = 0
            self.locked_key = None
            return None

        # STEP 3: Apply magnetic snapping
        # If close to a key, snap to it strongly
        if distance < self.magnetic_threshold:
            # Strong magnetic attraction to nearest key
            self.locked_key = nearest_key
            self.lock_frames = 0
            return nearest_key

        # STEP 4: Apply hysteresis (prefer already-locked key)
        if self.locked_key is not None and self.lock_frames < self.lock_duration:
            self.lock_frames += 1
            return self.locked_key
        
        self.locked_key = None
        self.lock_frames = 0
        return nearest_key
    
    def _find_key_at_safe_zone(self, gaze_px, gaze_py):
        """
        Check if gaze is inside a key's safe zone (reduced active area).
        Safe zone = 80% of key size, centered on key.
        
        Args:
            gaze_px: Gaze X in pixels
            gaze_py: Gaze Y in pixels
            
        Returns:
            str: Key name if in safe zone, None otherwise
        """
        for key_name, key_info in self.grid_keys.items():
            x0 = key_info['x']
            y0 = key_info['y']
            w = key_info['width']
            h = key_info['height']
            
            # Define safe zone (80% of key, centered)
            safe_zone_pad = max(self.safe_zone_padding, w * 0.1)  # 10% padding
            
            x1 = x0 + safe_zone_pad
            y1 = y0 + safe_zone_pad
            x2 = x0 + w - safe_zone_pad
            y2 = y0 + h - safe_zone_pad
            
            # Check if gaze is in safe zone
            if x1 <= gaze_px <= x2 and y1 <= gaze_py <= y2:
                return key_name
        
        return None
    
    def _find_nearest_key(self, gaze_px, gaze_py):
        """
        Find the key nearest to gaze position.
        
        Args:
            gaze_px: Gaze X in pixels
            gaze_py: Gaze Y in pixels
            
        Returns:
            tuple: (key_name, distance) or (None, float('inf'))
        """
        min_dist = float('inf')
        nearest_key = None
        
        for key_name, key_info in self.grid_keys.items():
            # Key center
            key_cx = key_info['x'] + key_info['width'] / 2
            key_cy = key_info['y'] + key_info['height'] / 2
            
            # Distance from gaze to key center
            dist = ((gaze_px - key_cx) ** 2 + (gaze_py - key_cy) ** 2) ** 0.5
            
            if dist < min_dist:
                min_dist = dist
                nearest_key = key_name
        
        return nearest_key, min_dist
    
    def update_grid_keys(self, grid_keys):
        """Update grid key positions and reset magnetic lock."""
        self.grid_keys = grid_keys
        self.locked_key = None
        self.lock_frames = 0
    
    def reset_lock(self):
        """Reset magnetic locking state."""
        self.locked_key = None
        self.lock_frames = 0
        self.previous_key = None
