"""
Gaze Calibration Module
Implements 5-point calibration system for accurate gaze tracking.
"""

import cv2
import json
import os
from datetime import datetime


class GazeCalibration:
    """
    5-point calibration system for eye gaze tracking.
    Captures eye coordinates at known screen positions and creates mapping.
    """
    
    # Calibration points as ratios of screen (0 to 1)
    CALIBRATION_POINTS = {
        'top_left': (0.1, 0.1),
        'top_right': (0.9, 0.1),
        'center': (0.5, 0.5),
        'bottom_left': (0.1, 0.9),
        'bottom_right': (0.9, 0.9)
    }
    
    def __init__(self, calibration_file="calibration_data.json"):
        """
        Initialize calibration system.
        
        Args:
            calibration_file: File to store/load calibration data
        """
        self.calibration_file = calibration_file
        self.calibration_data = {
            'min_x': None,
            'max_x': None,
            'min_y': None,
            'max_y': None,
            'gaze_samples': {}  # Store raw samples
        }
        self.collected_samples = {}  # Store samples during calibration
        
        # Try to load existing calibration
        self.load_calibration()
    
    def start_calibration(self, frame_width=640, frame_height=480):
        """
        Start 5-point calibration process.
        
        Args:
            frame_width: Camera frame width
            frame_height: Camera frame height
            
        Returns:
            dict: Calibration points with screen coordinates
        """
        self.collected_samples = {}
        self.calibration_points_screen = {}
        
        # Convert relative positions to screen coordinates
        for point_name, (rel_x, rel_y) in self.CALIBRATION_POINTS.items():
            screen_x = int(rel_x * frame_width)
            screen_y = int(rel_y * frame_height)
            self.calibration_points_screen[point_name] = (screen_x, screen_y)
        
        return self.calibration_points_screen
    
    def add_calibration_sample(self, point_name, gaze_x, gaze_y):
        """
        Add a gaze sample for a calibration point.
        
        Args:
            point_name: Name of calibration point
            gaze_x: Gaze X coordinate (from MediaPipe)
            gaze_y: Gaze Y coordinate (from MediaPipe)
        """
        if point_name not in self.collected_samples:
            self.collected_samples[point_name] = []
        
        self.collected_samples[point_name].append((gaze_x, gaze_y))
    
    def finish_calibration(self, min_samples=5):
        """
        Finish calibration with collected samples.
        Calculates min/max bounds for gaze normalization.
        
        Args:
            min_samples: Minimum samples required per point
            
        Returns:
            bool: True if calibration successful, False otherwise
        """
        # Check if enough samples collected
        for point_name in self.CALIBRATION_POINTS.keys():
            if point_name not in self.collected_samples:
                print(f"Error: No samples for {point_name}")
                return False
            
            if len(self.collected_samples[point_name]) < min_samples:
                print(f"Error: Not enough samples for {point_name}")
                return False
        
        try:
            # Calculate bounds from all samples
            all_x = []
            all_y = []
            
            for point_name, samples in self.collected_samples.items():
                # Average samples for this point
                avg_x = sum(x for x, y in samples) / len(samples)
                avg_y = sum(y for x, y in samples) / len(samples)
                
                all_x.append(avg_x)
                all_y.append(avg_y)
                
                self.calibration_data['gaze_samples'][point_name] = {
                    'avg_x': avg_x,
                    'avg_y': avg_y,
                    'samples_count': len(samples)
                }
            
            # Set bounds with small padding
            self.calibration_data['min_x'] = min(all_x) * 0.95  # 5% padding
            self.calibration_data['max_x'] = max(all_x) * 1.05
            self.calibration_data['min_y'] = min(all_y) * 0.95
            self.calibration_data['max_y'] = max(all_y) * 1.05
            
            print("Calibration complete!")
            print(f"X range: {self.calibration_data['min_x']:.3f} to {self.calibration_data['max_x']:.3f}")
            print(f"Y range: {self.calibration_data['min_y']:.3f} to {self.calibration_data['max_y']:.3f}")
            
            # Save calibration
            self.save_calibration()
            return True
            
        except Exception as e:
            print(f"Error during calibration: {e}")
            return False
    
    def normalize_gaze(self, gaze_x, gaze_y, clamp=True):
        """
        Normalize raw gaze coordinates to screen space (0 to 1).
        
        Args:
            gaze_x: Raw gaze X coordinate
            gaze_y: Raw gaze Y coordinate
            clamp: Clamp values between 0 and 1
            
        Returns:
            tuple: (normalized_x, normalized_y) or (None, None) if not calibrated
        """
        if (self.calibration_data['min_x'] is None or 
            self.calibration_data['max_x'] is None or
            self.calibration_data['min_y'] is None or
            self.calibration_data['max_y'] is None):
            return None, None  # Not calibrated
        
        try:
            # Normalize to 0-1 range
            norm_x = (gaze_x - self.calibration_data['min_x']) / \
                     (self.calibration_data['max_x'] - self.calibration_data['min_x'])
            norm_y = (gaze_y - self.calibration_data['min_y']) / \
                     (self.calibration_data['max_y'] - self.calibration_data['min_y'])
            
            # Clamp to 0-1 range
            if clamp:
                norm_x = max(0.0, min(1.0, norm_x))
                norm_y = max(0.0, min(1.0, norm_y))
            
            return norm_x, norm_y
            
        except Exception as e:
            print(f"Error normalizing gaze: {e}")
            return None, None
    
    def is_calibrated(self):
        """Check if system is calibrated."""
        return (self.calibration_data['min_x'] is not None and
                self.calibration_data['max_x'] is not None and
                self.calibration_data['min_y'] is not None and
                self.calibration_data['max_y'] is not None)
    
    def save_calibration(self):
        """Save calibration data to file."""
        try:
            with open(self.calibration_file, 'w') as f:
                json.dump(self.calibration_data, f, indent=2)
            print(f"Calibration saved to {self.calibration_file}")
        except Exception as e:
            print(f"Error saving calibration: {e}")
    
    def load_calibration(self):
        """Load calibration data from file."""
        try:
            if os.path.exists(self.calibration_file):
                with open(self.calibration_file, 'r') as f:
                    data = json.load(f)
                    self.calibration_data = data
                    print(f"Calibration loaded from {self.calibration_file}")
                    return True
        except Exception as e:
            print(f"Error loading calibration: {e}")
        
        return False
    
    def reset_calibration(self):
        """Reset calibration data."""
        self.calibration_data = {
            'min_x': None,
            'max_x': None,
            'min_y': None,
            'max_y': None,
            'gaze_samples': {}
        }
        self.collected_samples = {}
        print("Calibration reset")
    
    def get_calibration_stats(self):
        """Get current calibration statistics."""
        if not self.is_calibrated():
            return "Not calibrated"
        
        stats = {
            'x_range': f"{self.calibration_data['min_x']:.3f} - {self.calibration_data['max_x']:.3f}",
            'y_range': f"{self.calibration_data['min_y']:.3f} - {self.calibration_data['max_y']:.3f}",
            'points_calibrated': list(self.calibration_data['gaze_samples'].keys())
        }
        return stats
