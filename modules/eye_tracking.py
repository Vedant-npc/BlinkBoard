"""
Eye Tracking Module
Detects face and eyes, estimates gaze direction using MediaPipe Face Mesh.
Uses iris detection with improved accuracy and visual debugging.
"""

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.python.solutions import face_mesh
from mediapipe.framework.formats import landmark_pb2

from utils.helpers import calculate_distance, normalize_coordinates, smooth_gaze_direction, smooth_iris_coordinates, GazeBuffer


class EyeTracker:
    """
    Tracks eye position and estimates gaze direction using MediaPipe Face Mesh.
    Detects iris position and provides visual debugging output.
    """
    
    # MediaPipe Face Mesh indices for eye landmarks
    LEFT_EYE_INDICES = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
    RIGHT_EYE_INDICES = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
    
    # Additional eye contour indices for better visualization
    LEFT_EYE_CONTOUR = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
    RIGHT_EYE_CONTOUR = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
    
    # Key eye landmark indices for gaze estimation
    LEFT_IRIS = 468
    RIGHT_IRIS = 473
    LEFT_EYE_LEFT = 362
    LEFT_EYE_RIGHT = 263
    LEFT_EYE_TOP = 159
    LEFT_EYE_BOTTOM = 145
    RIGHT_EYE_LEFT = 33
    RIGHT_EYE_RIGHT = 133
    RIGHT_EYE_TOP = 27
    RIGHT_EYE_BOTTOM = 23
    
    # Iris detection thresholds (50-90 pupil detection range)
    IRIS_RADIUS_MIN = 8  # Minimum iris radius in pixels
    IRIS_RADIUS_MAX = 30  # Maximum iris radius in pixels
    MIN_DETECTION_CONFIDENCE = 0.5  # Tuned for reliable detection
    MIN_TRACKING_CONFIDENCE = 0.5
    
    def __init__(self, debug=True):
        """
        Initialize MediaPipe Face Mesh detector with iris detection.
        
        Args:
            debug: Enable debug output (default True)
        """
        try:
            # Create FaceMesh with optimized settings for iris detection
            self.face_mesh = face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,  # IMPORTANT: enables iris detection
                min_detection_confidence=self.MIN_DETECTION_CONFIDENCE,
                min_tracking_confidence=self.MIN_TRACKING_CONFIDENCE
            )
            
            print("[+] EyeTracker initialized successfully with iris detection")
            self.debug = debug
        except Exception as e:
            print(f"[ERROR] Failed to initialize EyeTracker: {e}")
            raise
        
        self.frame_width = None
        self.frame_height = None
        self.previous_gaze = None
        
        # Gaze smoothing buffer for better stability
        self.gaze_buffer = GazeBuffer(buffer_size=3)
        
        # Iris coordinate smoothing
        self.previous_left_iris = None
        self.previous_right_iris = None
        
        # Raw gaze for calibration (stores normalized iris position in eye space)
        self.raw_gaze_x = None
        self.raw_gaze_y = None
        
        # Face detection tracking
        self.face_detected_count = 0
        self.frame_count = 0
    
    def detect_landmarks(self, frame):
        """
        Detect face landmarks in frame with validation.
        
        Args:
            frame: Input image frame (BGR)
            
        Returns:
            tuple: (landmarks, is_face_detected) where landmarks is dict with face mesh results
        """
        self.frame_count += 1
        
        try:
            # Validate frame
            if frame is None:
                if self.debug and self.frame_count % 30 == 0:
                    print("[WARN] Frame is None")
                return None, False
            
            if frame.size == 0:
                if self.debug and self.frame_count % 30 == 0:
                    print("[WARN] Frame is empty")
                return None, False
            
            # Validate frame dimensions
            if len(frame.shape) < 2:
                if self.debug and self.frame_count % 30 == 0:
                    print("[WARN] Invalid frame shape")
                return None, False
            
            self.frame_height, self.frame_width = frame.shape[:2]
            
            # Validate frame size is reasonable (expect 640x480 or similar)
            if self.frame_width < 320 or self.frame_height < 240:
                if self.debug and self.frame_count % 30 == 0:
                    print(f"[WARN] Frame too small: {self.frame_width}x{self.frame_height}")
                return None, False
            
            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process frame with MediaPipe Face Mesh
            results = self.face_mesh.process(rgb_frame)
            
            # Check if face landmarks detected
            if not results.multi_face_landmarks or len(results.multi_face_landmarks) == 0:
                return None, False
            
            # Extract landmarks from first detected face
            face_landmarks = results.multi_face_landmarks[0]
            landmarks_dict = self._extract_landmarks(face_landmarks)
            
            self.face_detected_count += 1
            
            # Debug output every 30 frames (~1 second at 30fps)
            if self.debug and self.frame_count % 30 == 0:
                print(f"[TRACK] Face #{self.face_detected_count} | Frame {self.frame_count} | "
                      f"Landmarks: {len(landmarks_dict)} | Resolution: {self.frame_width}x{self.frame_height}")
            
            return landmarks_dict, True
            
        except Exception as e:
            if self.debug and self.frame_count % 30 == 0:
                print(f"[ERROR] detect_landmarks: {e}")
            return None, False
    
    
    def _extract_landmarks(self, face_landmarks):
        """
        Extract and convert landmarks to pixel coordinates.
        
        Args:
            face_landmarks: MediaPipe face landmarks object
            
        Returns:
            dict: Dictionary mapping landmark index to (x, y) pixel coordinates
        """
        landmarks_dict = {}
        
        try:
            for idx, lm in enumerate(face_landmarks.landmark):
                # Convert normalized coordinates (0-1) to pixel coordinates
                x = int(lm.x * self.frame_width)
                y = int(lm.y * self.frame_height)
                
                # Clamp to frame boundaries to prevent invalid coordinates
                x = max(0, min(x, self.frame_width - 1))
                y = max(0, min(y, self.frame_height - 1))
                
                landmarks_dict[idx] = (x, y)
            
            # Validate that key landmarks were detected
            required_landmarks = [self.LEFT_IRIS, self.RIGHT_IRIS, 
                                self.LEFT_EYE_LEFT, self.LEFT_EYE_RIGHT,
                                self.RIGHT_EYE_LEFT, self.RIGHT_EYE_RIGHT]
            
            for landmark_idx in required_landmarks:
                if landmark_idx not in landmarks_dict:
                    if self.debug:
                        print(f"[WARN] Missing landmark {landmark_idx}")
                    return None  # Return None instead of empty dict for failed validation
            
            return landmarks_dict
        except Exception as e:
            if self.debug:
                print(f"[ERROR] _extract_landmarks: {e}")
            return {}
    
    def get_raw_gaze_coordinates(self, landmarks):
        """
        Get raw gaze coordinates from iris position.
        Returns normalized iris position in eye coordinate space (0-1).
        
        Args:
            landmarks: Dictionary of face landmarks
            
        Returns:
            tuple: (raw_gaze_x, raw_gaze_y) for use in calibration, or (None, None)
        """
        if landmarks is None or len(landmarks) < 474:
            return None, None
        
        try:
            # Validate required landmarks exist
            required = [self.LEFT_IRIS, self.RIGHT_IRIS, self.LEFT_EYE_LEFT, 
                       self.LEFT_EYE_RIGHT, self.RIGHT_EYE_LEFT, self.RIGHT_EYE_RIGHT,
                       self.LEFT_EYE_TOP, self.LEFT_EYE_BOTTOM,
                       self.RIGHT_EYE_TOP, self.RIGHT_EYE_BOTTOM]
            
            for idx in required:
                if idx not in landmarks:
                    if self.debug and self.frame_count % 60 == 0:
                        print(f"[WARN] Missing required landmark {idx} for gaze calculation")
                    return None, None
            
            # LEFT EYE GAZE
            left_iris = landmarks[self.LEFT_IRIS]
            
            # Apply iris smoothing to reduce jitter
            left_iris = smooth_iris_coordinates(left_iris, self.previous_left_iris, alpha=0.4)
            self.previous_left_iris = left_iris
            
            # Get left eye boundaries
            left_eye_left = landmarks[self.LEFT_EYE_LEFT]
            left_eye_right = landmarks[self.LEFT_EYE_RIGHT]
            left_eye_top = landmarks[self.LEFT_EYE_TOP]
            left_eye_bottom = landmarks[self.LEFT_EYE_BOTTOM]
            
            # Validate left eye iris position is within reasonable bounds
            left_iris_dist = calculate_distance(left_iris, left_eye_left)
            left_eye_width = calculate_distance(left_eye_left, left_eye_right)
            
            if left_eye_width == 0:
                return None, None
            
            # RIGHT EYE GAZE
            right_iris = landmarks[self.RIGHT_IRIS]
            
            # Apply iris smoothing to reduce jitter
            right_iris = smooth_iris_coordinates(right_iris, self.previous_right_iris, alpha=0.4)
            self.previous_right_iris = right_iris
            
            # Get right eye boundaries
            right_eye_left = landmarks[self.RIGHT_EYE_LEFT]
            right_eye_right = landmarks[self.RIGHT_EYE_RIGHT]
            right_eye_top = landmarks[self.RIGHT_EYE_TOP]
            right_eye_bottom = landmarks[self.RIGHT_EYE_BOTTOM]
            
            # Validate right eye iris position is within reasonable bounds
            right_iris_dist = calculate_distance(right_iris, right_eye_left)
            right_eye_width = calculate_distance(right_eye_left, right_eye_right)
            
            if right_eye_width == 0:
                return None, None
            
            # HORIZONTAL GAZE (x-axis: left-right)
            left_gaze_x = normalize_coordinates(left_iris[0], left_eye_left[0], left_eye_right[0], 0, 1)
            right_gaze_x = normalize_coordinates(right_iris[0], right_eye_left[0], right_eye_right[0], 0, 1)
            
            # Clamp to valid range to handle detected outliers
            left_gaze_x = max(0.0, min(1.0, left_gaze_x))
            right_gaze_x = max(0.0, min(1.0, right_gaze_x))
            
            # Average both eyes for horizontal gaze
            raw_x = (left_gaze_x + right_gaze_x) / 2.0
            
            # VERTICAL GAZE (y-axis: up-down)
            left_gaze_y = normalize_coordinates(left_iris[1], left_eye_top[1], left_eye_bottom[1], 0, 1)
            right_gaze_y = normalize_coordinates(right_iris[1], right_eye_top[1], right_eye_bottom[1], 0, 1)
            
            # Clamp to valid range
            left_gaze_y = max(0.0, min(1.0, left_gaze_y))
            right_gaze_y = max(0.0, min(1.0, right_gaze_y))
            
            # Average both eyes for vertical gaze
            raw_y = (left_gaze_y + right_gaze_y) / 2.0
            
            # Store for later use
            self.raw_gaze_x = raw_x
            self.raw_gaze_y = raw_y
            
            if self.debug and self.frame_count % 60 == 0:
                print(f"[GAZE] Raw: ({raw_x:.3f}, {raw_y:.3f}) | "
                      f"L_iris: ({left_iris[0]}, {left_iris[1]}) | "
                      f"R_iris: ({right_iris[0]}, {right_iris[1]})")
            
            return raw_x, raw_y
            
        except Exception as e:
            if self.debug and self.frame_count % 60 == 0:
                print(f"[ERROR] get_raw_gaze_coordinates: {e}")
            return None, None
    
    def get_head_position(self, landmarks):
        """
        Get head/nose position for more stable tracking than iris alone.
        Uses nose tip and face structure landmarks to estimate head position.
        
        Args:
            landmarks: Dictionary of face landmarks
            
        Returns:
            tuple: (head_x, head_y) normalized 0-1, or (None, None)
        """
        if landmarks is None or len(landmarks) < 400:
            return None, None
        
        try:
            # Nose landmarks: tip=1, bridge=6
            NOSE_TIP = 1
            NOSE_BRIDGE = 6
            FOREHEAD = 10
            
            # Face structure landmarks for bounding estimate
            FACE_LEFT = 234  # Left face contour
            FACE_RIGHT = 454  # Right face contour
            FACE_TOP = 10  # Forehead
            FACE_BOTTOM = 152  # Chin
            
            required = [NOSE_TIP, NOSE_BRIDGE, FOREHEAD, FACE_LEFT, FACE_RIGHT, FACE_TOP, FACE_BOTTOM]
            for idx in required:
                if idx not in landmarks:
                    return None, None
            
            # Get nose tip position
            nose_tip = landmarks[NOSE_TIP]
            
            # Get face bounding box
            face_left = landmarks[FACE_LEFT][0]
            face_right = landmarks[FACE_RIGHT][0]
            face_top = landmarks[FACE_TOP][1]
            face_bottom = landmarks[FACE_BOTTOM][1]
            
            # Normalize nose position within face bounding box
            face_width = face_right - face_left
            face_height = face_bottom - face_top
            
            if face_width == 0 or face_height == 0:
                return None, None
            
            # Map nose position to normalized coordinates
            head_x = (nose_tip[0] - face_left) / face_width
            head_y = (nose_tip[1] - face_top) / face_height
            
            # Clamp to valid range
            head_x = max(0.0, min(1.0, head_x))
            head_y = max(0.0, min(1.0, head_y))
            
            return head_x, head_y
            
        except Exception as e:
            if self.debug and self.frame_count % 60 == 0:
                print(f"[ERROR] get_head_position: {e}")
            return None, None
    
    def get_combined_gaze(self, landmarks):
        """
        Get combined gaze using HEAD/NOSE tracking as primary, iris as refinement.
        For stable operation: head position is more reliable than iris for key selection.
        
        Args:
            landmarks: Dictionary of face landmarks
            
        Returns:
            tuple: (gaze_x, gaze_y) normalized 0-1
        """
        iris_x, iris_y = self.get_raw_gaze_coordinates(landmarks)
        head_x, head_y = self.get_head_position(landmarks)
        
        if iris_x is None and head_x is None:
            return None, None
        
        # If one is missing, use the other
        if iris_x is None:
            return head_x, head_y
        if head_x is None:
            return iris_x, iris_y
        
        # STABLE VERSION: Head position is PRIMARY (80%), iris for fine adjustment (20%)
        # Head tracking is much more stable for key selection than eye iris
        # Iris jitter is filtered out, head position provides core gaze direction
        combined_x = head_x * 0.8 + iris_x * 0.2
        combined_y = head_y * 0.8 + iris_y * 0.2
        
        return combined_x, combined_y
    
    def estimate_gaze_direction(self, landmarks):
        """
        Estimate gaze direction (left, right, up, down, center).
        Uses iris position relative to eye boundaries with improved smoothing.
        
        Args:
            landmarks: Dictionary of face landmarks
            
        Returns:
            tuple: (gaze_x, gaze_y) normalized between -1 and 1, or None
        """
        if landmarks is None or len(landmarks) < 474:
            return None
        
        try:
            # Verify all required landmarks exist
            required_indices = [self.LEFT_IRIS, self.RIGHT_IRIS, self.LEFT_EYE_LEFT, 
                              self.LEFT_EYE_RIGHT, self.RIGHT_EYE_LEFT, self.RIGHT_EYE_RIGHT,
                              self.LEFT_EYE_TOP, self.LEFT_EYE_BOTTOM,
                              self.RIGHT_EYE_TOP, self.RIGHT_EYE_BOTTOM]
            
            for idx in required_indices:
                if idx not in landmarks:
                    if self.debug and self.frame_count % 60 == 0:
                        print(f"[WARN] Missing gaze landmark {idx}")
                    return self.previous_gaze if self.previous_gaze else (0, 0)
            
            # Left eye gaze with iris smoothing
            left_iris = landmarks[self.LEFT_IRIS]
            left_iris = smooth_iris_coordinates(left_iris, self.previous_left_iris, alpha=0.4)
            self.previous_left_iris = left_iris
            
            left_eye_left = landmarks[self.LEFT_EYE_LEFT]
            left_eye_right = landmarks[self.LEFT_EYE_RIGHT]
            left_eye_top = landmarks[self.LEFT_EYE_TOP]
            left_eye_bottom = landmarks[self.LEFT_EYE_BOTTOM]
            
            # Right eye gaze with iris smoothing
            right_iris = landmarks[self.RIGHT_IRIS]
            right_iris = smooth_iris_coordinates(right_iris, self.previous_right_iris, alpha=0.4)
            self.previous_right_iris = right_iris
            
            right_eye_left = landmarks[self.RIGHT_EYE_LEFT]
            right_eye_right = landmarks[self.RIGHT_EYE_RIGHT]
            right_eye_top = landmarks[self.RIGHT_EYE_TOP]
            right_eye_bottom = landmarks[self.RIGHT_EYE_BOTTOM]
            
            # Calculate gaze position for each eye (normalized -1 to 1)
            left_gaze_x = normalize_coordinates(left_iris[0], left_eye_left[0], left_eye_right[0], -1, 1)
            right_gaze_x = normalize_coordinates(right_iris[0], right_eye_left[0], right_eye_right[0], -1, 1)
            
            # Clamp to valid range
            left_gaze_x = max(-1.0, min(1.0, left_gaze_x))
            right_gaze_x = max(-1.0, min(1.0, right_gaze_x))
            
            # Average both eyes for horizontal gaze
            avg_gaze_x = (left_gaze_x + right_gaze_x) / 2.0
            
            # Calculate vertical gaze
            left_gaze_y = normalize_coordinates(left_iris[1], left_eye_top[1], left_eye_bottom[1], -1, 1)
            right_gaze_y = normalize_coordinates(right_iris[1], right_eye_top[1], right_eye_bottom[1], -1, 1)
            
            # Clamp to valid range
            left_gaze_y = max(-1.0, min(1.0, left_gaze_y))
            right_gaze_y = max(-1.0, min(1.0, right_gaze_y))
            
            # Average both eyes for vertical gaze
            avg_gaze_y = (left_gaze_y + right_gaze_y) / 2.0
            
            # Apply buffer averaging for additional stability
            current_gaze = (avg_gaze_x, avg_gaze_y)
            self.gaze_buffer.add(current_gaze)
            buffered_gaze = self.gaze_buffer.get_average()
            
            if buffered_gaze is None:
                buffered_gaze = current_gaze
            
            # Apply temporal smoothing for final output
            smoothed_gaze = smooth_gaze_direction(buffered_gaze, self.previous_gaze, alpha=0.6)
            self.previous_gaze = smoothed_gaze
            
            return smoothed_gaze
        
        except Exception as e:
            if self.debug and self.frame_count % 60 == 0:
                print(f"[ERROR] estimate_gaze_direction: {e}")
            return self.previous_gaze if self.previous_gaze else (0, 0)
    
    def get_eye_landmarks(self, landmarks, eye='left'):
        """
        Get specific eye landmarks.
        
        Args:
            landmarks: Dictionary of face landmarks
            eye: 'left' or 'right'
        
        Returns:
            list: List of (x, y) tuples for eye landmarks
        """
        if landmarks is None:
            return [
]
        
        indices = self.LEFT_EYE_INDICES if eye == 'left' else self.RIGHT_EYE_INDICES
        eye_landmarks = [landmarks.get(idx, (0, 0)) for idx in indices]
        
        return eye_landmarks
    
    def draw_neon_eye_markers(self, frame, landmarks, show_debug=False):
        """
        Draw neon green eye tracking markers that fit the eye shape.
        Creates filled eye-shaped markers matching actual eye contours.
        
        Args:
            frame: Input frame (BGR)
            landmarks: Dictionary of landmarks
            show_debug: Whether to show debug info
            
        Returns:
            frame: Frame with drawn eye markers
        """
        if landmarks is None or len(landmarks) == 0:
            return frame
        
        try:
            # DARK GREEN COLORS
            DARK_GREEN = (0, 150, 0)
            MEDIUM_GREEN = (0, 180, 0)
            
            # Draw LEFT EYE with proper eye shape
            left_eye_indices = self.LEFT_EYE_CONTOUR
            left_eye_points = []
            for idx in left_eye_indices:
                if idx in landmarks:
                    pt = landmarks[idx]
                    left_eye_points.append([int(pt[0]), int(pt[1])])
            
            if len(left_eye_points) > 2:
                left_eye_array = np.array(left_eye_points, dtype=np.int32)
                # Fill the eye region with dark green
                cv2.fillPoly(frame, [left_eye_array], DARK_GREEN)
                # Outline with medium green
                cv2.polylines(frame, [left_eye_array], True, MEDIUM_GREEN, 4)
            
            # Draw RIGHT EYE with proper eye shape
            right_eye_indices = self.RIGHT_EYE_CONTOUR
            right_eye_points = []
            for idx in right_eye_indices:
                if idx in landmarks:
                    pt = landmarks[idx]
                    right_eye_points.append([int(pt[0]), int(pt[1])])
            
            if len(right_eye_points) > 2:
                right_eye_array = np.array(right_eye_points, dtype=np.int32)
                # Fill the eye region with dark green
                cv2.fillPoly(frame, [right_eye_array], DARK_GREEN)
                # Outline with medium green
                cv2.polylines(frame, [right_eye_array], True, MEDIUM_GREEN, 4)
            
            # Add bright dots at iris centers
            left_iris = landmarks.get(self.LEFT_IRIS)
            right_iris = landmarks.get(self.RIGHT_IRIS)
            
            if left_iris:
                left_iris = tuple(int(coord) for coord in left_iris)
                if 0 <= left_iris[0] < self.frame_width and 0 <= left_iris[1] < self.frame_height:
                    cv2.circle(frame, left_iris, 5, MEDIUM_GREEN, -1)
            
            if right_iris:
                right_iris = tuple(int(coord) for coord in right_iris)
                if 0 <= right_iris[0] < self.frame_width and 0 <= right_iris[1] < self.frame_height:
                    cv2.circle(frame, right_iris, 5, MEDIUM_GREEN, -1)
            
            # DEBUG INFO (optional)
            if show_debug:
                cv2.putText(frame, "EYE TRACKING ACTIVE", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, MEDIUM_GREEN, 2)
        
        except Exception as e:
            if self.debug and self.frame_count % 60 == 0:
                print(f"[ERROR] draw_neon_eye_markers: {e}")
        
        return frame
    
    def draw_landmarks(self, frame, landmarks, show_debug=True):
        """
        Draw face landmarks on frame for debugging.
        Shows eye regions, iris positions, and gaze indicators.
        
        Args:
            frame: Input frame (BGR)
            landmarks: Dictionary of landmarks
            show_debug: Whether to show debug info overlay
            
        Returns:
            frame: Frame with drawn landmarks
        """
        if landmarks is None or len(landmarks) == 0:
            # Show "NO FACE" message if no landmarks
            if show_debug:
                cv2.putText(frame, "NO FACE DETECTED", (20, 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            return frame
        
        try:
            # DRAW IRIS (Pupil detection indicator)
            left_iris = landmarks.get(self.LEFT_IRIS)
            right_iris = landmarks.get(self.RIGHT_IRIS)
            
            if left_iris and right_iris:
                # Ensure iris coordinates are integer tuples for cv2.circle
                left_iris = tuple(int(coord) for coord in left_iris)
                right_iris = tuple(int(coord) for coord in right_iris)
                
                # Get iris radii by finding eye boundaries
                left_eye_left = landmarks.get(self.LEFT_EYE_LEFT, (0, 0))
                left_eye_right = landmarks.get(self.LEFT_EYE_RIGHT, (0, 0))
                left_eye_width = calculate_distance(left_eye_left, left_eye_right)
                left_iris_radius = max(3, int(left_eye_width / 8))  # Estimate iris radius
                
                right_eye_left = landmarks.get(self.RIGHT_EYE_LEFT, (0, 0))
                right_eye_right = landmarks.get(self.RIGHT_EYE_RIGHT, (0, 0))
                right_eye_width = calculate_distance(right_eye_left, right_eye_right)
                right_iris_radius = max(3, int(right_eye_width / 8))
                
                # Clamp iris radius to 50-90 range for pupil detection
                left_iris_radius = max(self.IRIS_RADIUS_MIN, min(self.IRIS_RADIUS_MAX, left_iris_radius))
                right_iris_radius = max(self.IRIS_RADIUS_MIN, min(self.IRIS_RADIUS_MAX, right_iris_radius))
                
                # Validate coordinates are within frame bounds
                if (0 <= left_iris[0] < self.frame_width and 0 <= left_iris[1] < self.frame_height and
                    0 <= right_iris[0] < self.frame_width and 0 <= right_iris[1] < self.frame_height):
                    # Draw iris circles with green fill (indicates detection)
                    cv2.circle(frame, left_iris, left_iris_radius, (0, 255, 0), -1)  # Filled green circle
                    cv2.circle(frame, right_iris, right_iris_radius, (0, 255, 0), -1)
                    
                    # Draw iris outline in brighter green
                    cv2.circle(frame, left_iris, left_iris_radius, (0, 255, 100), 2)
                    cv2.circle(frame, right_iris, right_iris_radius, (0, 255, 100), 2)
                    
                    # Draw iris center dot in yellow
                    cv2.circle(frame, left_iris, 2, (255, 255, 0), -1)
                    cv2.circle(frame, right_iris, 2, (255, 255, 0), -1)
            
            # DRAW EYE REGIONS (Bounding boxes around eyes)
            left_eye = self.get_eye_landmarks(landmarks, 'left')
            right_eye = self.get_eye_landmarks(landmarks, 'right')
            
            # Draw left eye landmarks (blue dots)
            for pt in left_eye:
                if pt and pt != (0, 0):
                    cv2.circle(frame, pt, 1, (255, 0, 0), -1)
            
            # Draw right eye landmarks (blue dots)
            for pt in right_eye:
                if pt and pt != (0, 0):
                    cv2.circle(frame, pt, 1, (255, 0, 0), -1)
            
            # Draw eye contour lines
            left_eye_array = np.array([pt for pt in left_eye if pt != (0, 0)], dtype=np.int32)
            right_eye_array = np.array([pt for pt in right_eye if pt != (0, 0)], dtype=np.int32)
            
            if len(left_eye_array) > 0:
                cv2.polylines(frame, [left_eye_array], True, (0, 255, 255), 1)
            if len(right_eye_array) > 0:
                cv2.polylines(frame, [right_eye_array], True, (0, 255, 255), 1)
            
            # DRAW DEBUG INFO
            if show_debug:
                # Face detection status
                cv2.putText(frame, "FACE DETECTED", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Iris position info
                if left_iris and right_iris:
                    cv2.putText(frame, f"L_Iris: ({left_iris[0]}, {left_iris[1]})", (10, 60),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 200), 1)
                    cv2.putText(frame, f"R_Iris: ({right_iris[0]}, {right_iris[1]})", (10, 85),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 200), 1)
                
                # Frame info
                cv2.putText(frame, f"Frame: {self.frame_count} | Size: {self.frame_width}x{self.frame_height}",
                           (10, self.frame_height - 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 0), 1)
        
        except Exception as e:
            if self.debug:
                print(f"[ERROR] draw_landmarks: {e}")
        
        return frame
    
    def release(self):
        """Release resources."""
        self.face_mesh.close()
