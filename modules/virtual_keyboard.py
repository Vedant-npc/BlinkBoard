"""
Virtual Keyboard Module
Displays an on-screen QWERTY keyboard with gaze-based selection and a wide centered spacebar.
"""

import tkinter as tk
from tkinter import Canvas
import math
from collections import deque


class GazeSmoothingBuffer:
    """
    Smooths gaze coordinates by averaging recent samples.
    Reduces jitter from eye detection noise.
    """
    
    def __init__(self, buffer_size=5):
        """
        Initialize smoothing buffer.
        
        Args:
            buffer_size: Number of samples to average (higher = smoother but slower)
        """
        self.buffer_size = buffer_size
        self.x_buffer = deque(maxlen=buffer_size)
        self.y_buffer = deque(maxlen=buffer_size)
    
    def add_sample(self, gaze_x, gaze_y):
        """Add a gaze sample to the buffer."""
        if gaze_x is not None:
            self.x_buffer.append(gaze_x)
        if gaze_y is not None:
            self.y_buffer.append(gaze_y)
    
    def get_smoothed_gaze(self):
        """Get smoothed gaze coordinates."""
        if not self.x_buffer or not self.y_buffer:
            return None, None
        
        avg_x = sum(self.x_buffer) / len(self.x_buffer)
        avg_y = sum(self.y_buffer) / len(self.y_buffer)
        
        return avg_x, avg_y
    
    def clear(self):
        """Clear the buffer."""
        self.x_buffer.clear()
        self.y_buffer.clear()


class VirtualKeyboard:
    """
    Displays a QWERTY virtual keyboard on screen with gaze-tracking support.
    Features a proper QWERTY layout with a wide, centered spacebar like a real keyboard.
    """
    
    # Keyboard layout - QWERTY format with special keys
    # Each row is a list of (key_name, width_multiplier) tuples
    # width_multiplier: 1.0 = normal key, 6.5 = spacebar (very wide and centered)
    KEYBOARD_LAYOUT = [
        # Row 1: Q W E R T Y U I O P (10 keys)
        [('Q', 1.0), ('W', 1.0), ('E', 1.0), ('R', 1.0), ('T', 1.0), 
         ('Y', 1.0), ('U', 1.0), ('I', 1.0), ('O', 1.0), ('P', 1.0)],
        
        # Row 2: A S D F G H J K L (9 keys - slightly offset for realistic look)
        [('A', 1.0), ('S', 1.0), ('D', 1.0), ('F', 1.0), ('G', 1.0), 
         ('H', 1.0), ('J', 1.0), ('K', 1.0), ('L', 1.0)],
        
        # Row 3: Z X C V B N M (7 keys - more offset)
        [('Z', 1.0), ('X', 1.0), ('C', 1.0), ('V', 1.0), ('B', 1.0), 
         ('N', 1.0), ('M', 1.0)],
        
        # Row 4: ACTION ROW - Shift, SPACE (very wide and centered), Backspace, Enter
        # The spacebar is 6.5x the width of a normal key for maximum width
        [('SHIFT_LEFT', 1.0), ('SPACE', 6.5), ('BACKSPACE', 1.0), ('ENTER', 1.0)]
    ]
    
    # Key labels for display (can include special characters or descriptions)
    KEY_LABELS = {
        'SHIFT_LEFT': '⇧',  # Shift symbol
        'SPACE': '   SPACE   ',  # Spacebar label
        'BACKSPACE': '⌫',  # Backspace symbol
        'ENTER': '⏎',  # Enter symbol
    }
    
    # Actual values sent when keys are selected (for keyboard shortcuts)
    KEY_VALUES = {
        'SHIFT_LEFT': 'SHIFT',
        'SPACE': ' ',
        'BACKSPACE': 'BACKSPACE',
        'ENTER': 'ENTER',
    }
    
    def __init__(self, parent=None, width=1100, height=420, embed=False):
        """
        Initialize virtual QWERTY keyboard with wide centered spacebar.
        Designed for confirmation-based selection: look at key, then confirm via blink.
        
        Args:
            parent: Parent Tkinter window/frame (main window or frame container).
            width: Keyboard width (1100 for large keys and spacebar)
            height: Keyboard height (420 for good visibility)
            embed: If True, embed in parent frame instead of creating floating window
        """
        self.width = width
        self.height = height
        self.embed = embed
        self.key_size = 65  # Base key size for normal keys
        self.key_spacing = 8  # Spacing between keys (small for realistic keyboard look)
        self.row_offset = 12  # Horizontal offset for each row (slight stagger like real keyboard)
        self.font_size = 13  # Font size for key labels
        self.key_padding = 5  # Padding to avoid edge misselection
        self.highlighted_key = None
        self.selected_key = None
        
        # Gaze tracking variables
        self.gaze_smoother = GazeSmoothingBuffer(buffer_size=5)
        
        # Focus tracking for stability (requires stable focus on same key)
        self.focus_stability_frames = 5  # Frames needed to confirm focus
        self.focus_counter = 0  # Current focus frame count
        self.focus_candidate = None  # Key being focused on
        self.previous_gaze_key = None  # Previous frame's key
        
        # Store current gaze position for visualization
        self.current_gaze_px = None
        self.current_gaze_py = None
        
        # Dwell time visualization
        self.dwell_progress = 0.0  # 0 to 1 (stability progress now)
        self.dwell_key = None  # Key with focus indicator
        self.stable_key = None  # Key with stable focus
        
        # Calculate keyboard dimensions
        self.rows = len(self.KEYBOARD_LAYOUT)
        self._calculate_keyboard_dimensions()
        
        # Create window - use embedded frame or Toplevel
        if embed and parent:
            # Embedded mode: use parent frame directly
            self.window = parent
            self.is_embedded = True
        elif parent:
            # Floating window mode
            self.window = tk.Toplevel(parent)
            self.window.attributes('-topmost', True)  # Keep on top so it's always visible
            self.is_embedded = False
        else:
            # Standalone mode
            self.window = tk.Tk()
            self.is_embedded = False
            
        if not embed or not parent:
            self.window.title("BlinkBoard - QWERTY Keyboard")
        
        # Only set geometry for non-embedded windows
        if not self.is_embedded:
            # Calculate window position for better visibility
            if parent and not embed:
                try:
                    parent.update_idletasks()
                    parent_x = parent.winfo_x()
                    parent_y = parent.winfo_y()
                    parent_width = parent.winfo_width()
                    parent_height = parent.winfo_height()
                    
                    screen_width = self.window.winfo_screenwidth()
                    screen_height = self.window.winfo_screenheight()
                    
                    # Try to position below parent window
                    window_x = parent_x
                    window_y = parent_y + parent_height + 10
                    
                    # Adjust if goes off-screen
                    if window_x + self.width > screen_width:
                        window_x = max(0, screen_width - self.width - 10)
                    
                    if window_y + self.height > screen_height:
                        window_y = max(0, parent_y - self.height - 10)
                    
                    window_x = max(0, window_x)
                    window_y = max(0, window_y)
                except Exception as e:
                    # If parent position unavailable, center on screen
                    screen_width = self.window.winfo_screenwidth()
                    screen_height = self.window.winfo_screenheight()
                    window_x = (screen_width - self.width) // 2
                    window_y = (screen_height - self.height) // 2
            else:
                # Center on screen for standalone window
                screen_width = self.window.winfo_screenwidth()
                screen_height = self.window.winfo_screenheight()
                window_x = (screen_width - self.width) // 2
                window_y = (screen_height - self.height) // 2
            
            self.window.geometry(f"{self.width}x{self.height}+{window_x}+{window_y}")
            self.window.resizable(False, False)
            self.window.lift()
            self.window.update()
        
        # Create canvas with dark background
        self.canvas = Canvas(
            self.window,
            width=self.width,
            height=self.height,
            bg='#1a1a1a'
        )
        self.canvas.pack()
        
        # Store key positions for gaze tracking
        self.key_positions = {}
        self._create_keyboard()
    
    def _calculate_keyboard_dimensions(self):
        """Calculate total keyboard dimensions based on variable key widths."""
        # Calculate width of each row
        row_widths = []
        for row in self.KEYBOARD_LAYOUT:
            row_width = sum(key_width for _, key_width in row) * self.key_size + (len(row) - 1) * self.key_spacing
            row_widths.append(row_width)
        
        # Total width is the widest row plus padding
        self.total_width = max(row_widths) if row_widths else 0
        
        # Total height is number of rows plus spacing
        self.total_height = self.rows * (self.key_size + self.key_spacing)
    
    def _create_keyboard(self):
        """Create keyboard layout on canvas with centered positioning and variable key widths."""
        # Calculate starting position to center keyboard
        keyboard_padding = 20
        start_base_x = keyboard_padding + (self.width - self.total_width - 2 * keyboard_padding) // 2
        start_y = keyboard_padding + (self.height - self.total_height - 2 * keyboard_padding) // 2
        
        # Ensure minimum space is left
        start_base_x = max(keyboard_padding, start_base_x)
        start_y = max(keyboard_padding, start_y)
        
        self.start_x = start_base_x
        self.start_y = start_y
        
        key_id = 0
        for row_idx, row in enumerate(self.KEYBOARD_LAYOUT):
            # Calculate row offset for staggered keyboard look
            row_offset_x = 0
            if row_idx == 1:  # A row
                row_offset_x = self.row_offset
            elif row_idx == 2:  # Z row
                row_offset_x = self.row_offset * 2
            elif row_idx == 3:  # Spacebar row
                row_offset_x = 0
            
            # Calculate starting x for this row (centered)
            row_width = sum(key_width for _, key_width in row) * self.key_size + (len(row) - 1) * self.key_spacing
            row_start_x = start_base_x + (self.total_width - row_width) // 2 + row_offset_x
            
            # Place keys in this row
            current_x = row_start_x
            for col_idx, (key_name, width_mult) in enumerate(row):
                y = start_y + row_idx * (self.key_size + self.key_spacing)
                actual_width = self.key_size * width_mult
                
                self.key_positions[key_name] = {
                    'x': current_x,
                    'y': y,
                    'width': actual_width,
                    'height': self.key_size,
                    'id': key_id
                }
                
                current_x += actual_width + self.key_spacing
                key_id += 1
        
        # Set default highlighted key to first letter key
        self.highlighted_key = 'Q'
        
        self._draw_keyboard()
    
    
    def _point_in_key(self, gaze_x, gaze_y, key_name):
        """
        Check if a gaze point (pixel coordinates) is inside a key's bounding box.
        Uses padded region to avoid edge misselection.
        
        Args:
            gaze_x: Gaze X coordinate in pixels
            gaze_y: Gaze Y coordinate in pixels
            key_name: Name of the key to check
            
        Returns:
            bool: True if gaze point is inside the key's padded region
        """
        if key_name not in self.key_positions:
            return False
        
        pos = self.key_positions[key_name]
        x = pos['x']
        y = pos['y']
        w = pos['width']
        h = pos['height']
        
        # Apply padding to reduce edge misselection
        padded_x1 = x + self.key_padding
        padded_y1 = y + self.key_padding
        padded_x2 = x + w - self.key_padding
        padded_y2 = y + h - self.key_padding
        
        # Check if gaze is within padded bounds
        return (padded_x1 <= gaze_x <= padded_x2 and 
                padded_y1 <= gaze_y <= padded_y2)
    
    def _find_key_at_gaze(self, gaze_x, gaze_y):
        """
        Find which key the gaze is pointing at using boundary checking.
        
        Args:
            gaze_x: Gaze X coordinate in pixels
            gaze_y: Gaze Y coordinate in pixels
            
        Returns:
            str: Key name if gaze is inside a key, None if between keys
        """
        # First check if gaze is inside any key's padded region
        for key_name in self.key_positions.keys():
            if self._point_in_key(gaze_x, gaze_y, key_name):
                return key_name
        
        # If no key found, return None (gaze is between keys)
        return None
    
    def _draw_keyboard(self):
        """Draw keyboard on canvas with modern design: glowing highlights and animations."""
        self.canvas.delete("all")
        
        # Draw dark background
        self.canvas.create_rectangle(
            0, 0, self.width, self.height,
            fill='#0d0d0d',
            outline='#1a1a1a',
            width=1
        )
        
        # Draw each key
        for key, pos in self.key_positions.items():
            x = pos['x']
            y = pos['y']
            w = pos['width']
            h = pos['height']
            
            # Determine colors and effects based on key state
            if key == self.highlighted_key:
                # Glowing highlight effect for focused key
                fill_color = '#00ff88'  # Bright neon green
                outline_color = '#00cc66'  # Darker green outline
                text_color = '#000000'  # Black text for contrast
                outline_width = 3
            elif key == self.selected_key:
                # Blue highlight for selected
                fill_color = '#1e90ff'  # Dodger blue
                outline_color = '#0066ff'
                text_color = 'white'
                outline_width = 3
            else:
                # Dark neutral keys
                fill_color = '#2a2a2a'
                outline_color = '#3a3a3a'
                text_color = '#cccccc'
                outline_width = 1
            
            # Draw main key rectangle with rounded corners effect (using slight arcs)
            self.canvas.create_rectangle(
                x, y, x + w, y + h,
                fill=fill_color,
                outline=outline_color,
                width=outline_width
            )
            
            # Draw subtle inner shadow for depth
            shadow_offset = 2
            self.canvas.create_rectangle(
                x + shadow_offset, y + shadow_offset,
                x + w - shadow_offset, y + h - shadow_offset,
                fill='',
                outline=outline_color,
                width=0
            )
            
            # Draw dwell progress ring if active
            if key == self.dwell_key and self.dwell_progress > 0:
                center_x = x + w // 2
                center_y = y + h // 2
                radius = min(w, h) // 2 - 8
                
                # Draw filled arc for progress (animated ring)
                angle = int(360 * self.dwell_progress)
                if radius > 0:
                    self.canvas.create_arc(
                        center_x - radius, center_y - radius,
                        center_x + radius, center_y + radius,
                        start=90, extent=-angle,
                        outline='#FFD700', width=3
                    )
                    
                    # Add a pulsing center indicator
                    pulse_radius = int(4 * self.dwell_progress)
                    if pulse_radius > 0:
                        self.canvas.create_oval(
                            center_x - pulse_radius, center_y - pulse_radius,
                            center_x + pulse_radius, center_y + pulse_radius,
                            fill='#FFD700', outline='#FFD700'
                        )
            
            # Draw key text with better styling
            # Use special label if defined, otherwise use key name
            display_text = self.KEY_LABELS.get(key, key)
            text_font = ("Arial", self.font_size, "bold")
            self.canvas.create_text(
                x + w // 2, y + h // 2,
                text=display_text,
                fill=text_color,
                font=text_font
            )
        
        # Draw visible gaze cursor (red dot) for debugging
        if self.current_gaze_px is not None and self.current_gaze_py is not None:
            cursor_radius = 7
            cursor_outline = 2
            
            # Draw outer ring (red)
            self.canvas.create_oval(
                self.current_gaze_px - cursor_radius,
                self.current_gaze_py - cursor_radius,
                self.current_gaze_px + cursor_radius,
                self.current_gaze_py + cursor_radius,
                fill='#FF0000',
                outline='#FFFF00',
                width=cursor_outline
            )
            
            # Draw inner crosshair
            crosshair_size = cursor_radius - 1
            self.canvas.create_line(
                self.current_gaze_px - crosshair_size, self.current_gaze_py,
                self.current_gaze_px + crosshair_size, self.current_gaze_py,
                fill='#FFFF00', width=1
            )
            self.canvas.create_line(
                self.current_gaze_px, self.current_gaze_py - crosshair_size,
                self.current_gaze_px, self.current_gaze_py + crosshair_size,
                fill='#FFFF00', width=1
            )
    
    def update_highlight(self, gaze_direction, gaze_quadrant):
        """
        Update highlighted key based on gaze direction.
        
        Args:
            gaze_direction: Tuple (gaze_x, gaze_y) normalized (can be None)
            gaze_quadrant: String indicating direction ('left', 'right', 'up', 'down', 'center')
        """
        # Simple location-based highlighting using quadrant
        highlighted = None
        
        # Filter out special keys for highlighting
        regular_keys = {k: v for k, v in self.key_positions.items() if k not in ["SHIFT_LEFT", "SPACE", "BACKSPACE", "ENTER"]}
        
        if not regular_keys:
            return
        
        # Use quadrant to suggest keyboard area
        if gaze_quadrant == "left":
            sorted_keys = sorted(regular_keys.items(), key=lambda item: item[1]['x'])
            if sorted_keys:
                highlighted = sorted_keys[0][0]
        elif gaze_quadrant == "right":
            sorted_keys = sorted(regular_keys.items(), key=lambda item: item[1]['x'], reverse=True)
            if sorted_keys:
                highlighted = sorted_keys[0][0]
        elif gaze_quadrant == "up":
            sorted_keys = sorted(regular_keys.items(), key=lambda item: item[1]['y'])
            if sorted_keys:
                highlighted = sorted_keys[0][0]
        elif gaze_quadrant == "down":
            sorted_keys = sorted(regular_keys.items(), key=lambda item: item[1]['y'], reverse=True)
            if sorted_keys:
                highlighted = sorted_keys[0][0]
        else:  # center
            if self.key_positions:
                avg_x = sum(p['x'] for p in regular_keys.values()) / len(regular_keys)
                avg_y = sum(p['y'] for p in regular_keys.values()) / len(regular_keys)
                
                min_dist = float('inf')
                for key, pos in regular_keys.items():
                    key_center_x = pos['x'] + pos['width'] / 2
                    key_center_y = pos['y'] + pos['height'] / 2
                    dist = math.sqrt((key_center_x - avg_x) ** 2 + (key_center_y - avg_y) ** 2)
                    if dist < min_dist:
                        min_dist = dist
                        highlighted = key
        
        if highlighted and highlighted != self.highlighted_key:
            self.highlighted_key = highlighted
            self._draw_keyboard()
    
    def update_highlight_from_normalized_gaze(self, norm_x, norm_y):
        """
        Update highlighted key based on normalized gaze coordinates (0 to 1).
        Uses proper boundary checking with padding and focus delay for stability.
        
        Args:
            norm_x: Normalized gaze X coordinate (0 to 1)
            norm_y: Normalized gaze Y coordinate (0 to 1)
        """
        if norm_x is None or norm_y is None:
            # Clear smoothing buffer if no gaze data
            self.current_gaze_px = None
            self.current_gaze_py = None
            return
        
        # CLAMP normalized coordinates to valid range [0, 1]
        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))
        
        # Add to smoothing buffer
        self.gaze_smoother.add_sample(norm_x, norm_y)
        
        # Get smoothed gaze (average of last N samples)
        smooth_x, smooth_y = self.gaze_smoother.get_smoothed_gaze()
        
        if smooth_x is None or smooth_y is None:
            self.current_gaze_px = None
            self.current_gaze_py = None
            return
        
        # CLAMP smoothed coordinates before converting to pixels
        smooth_x = max(0.0, min(1.0, smooth_x))
        smooth_y = max(0.0, min(1.0, smooth_y))
        
        # Convert smoothed normalized coords to pixel coordinates
        # Ensure we're scaling to the correct keyboard window dimensions
        gaze_px = smooth_x * self.width
        gaze_py = smooth_y * self.height
        
        # CLAMP pixel coordinates to keyboard bounds
        gaze_px = max(0, min(self.width, gaze_px))
        gaze_py = max(0, min(self.height, gaze_py))
        
        # Store for visualization in next draw
        self.current_gaze_px = gaze_px
        self.current_gaze_py = gaze_py
        
        # Find which key the gaze is pointing at (using boundary checking)
        current_key = self._find_key_at_gaze(gaze_px, gaze_py)
        
        # Stability tracking for focus delay
        if current_key == self.focus_candidate:
            # Same key as last frame - increase focus counter
            self.focus_counter += 1
        else:
            # Different key - reset focus counter for new candidate
            self.focus_counter = 1
            self.focus_candidate = current_key
        
        # Only highlight after stable focus for N frames
        if self.focus_counter >= self.focus_stability_frames:
            # Gaze is stable on a key
            if current_key and current_key != self.highlighted_key:
                self.highlighted_key = current_key
                self._draw_keyboard()
        elif not current_key and self.highlighted_key is not None:
            # Gaze moved between keys (no key found) - clear highlight
            self.highlighted_key = None
            self._draw_keyboard()
        
        self.previous_gaze_key = current_key
        
        # Redraw to show updated gaze cursor
        self._draw_keyboard()
    
    
    def set_dwell_progress(self, key_name, progress):
        """
        Update dwell time progress for a key.
        
        Args:
            key_name: Key being dwelled on
            progress: Progress value (0 to 1)
        """
        # Only redraw if dwell key or progress changed
        if key_name != self.dwell_key or abs(progress - self.dwell_progress) > 0.01:
            self.dwell_key = key_name
            self.dwell_progress = progress
            self._draw_keyboard()
    
    def clear_dwell_progress(self):
        """Clear dwell progress indicator."""
        self.dwell_key = None
        self.dwell_progress = 0.0
        self._draw_keyboard()
    
    def highlight_key(self, key):
        """
        Highlight a specific key by name.
        
        Args:
            key: Key name to highlight (e.g. 'Q', 'SPACE', 'BACKSPACE')
        """
        if key in self.key_positions and key != self.highlighted_key:
            self.highlighted_key = key
            self._draw_keyboard()
    
    def select_key(self):
        """
        Select the currently highlighted key.
        
        Returns:
            str: The selected key, or None if no key is highlighted
        """
        if self.highlighted_key:
            self.selected_key = self.highlighted_key
            # Reset gaze tracking after selection for clean state
            self.reset_gaze_tracking()
            self._draw_keyboard()
            return self.highlighted_key
        return None
    
    def clear_selection(self):
        """Clear the selection and reset gaze tracking."""
        self.selected_key = None
        self.reset_gaze_tracking()
        self._draw_keyboard()
    
    def get_highlighted_key(self):
        """Get currently highlighted key."""
        return self.highlighted_key
    
    def get_selected_key(self):
        """Get currently selected key."""
        return self.selected_key
    
    def update_display(self):
        """Update keyboard display."""
        try:
            self.window.update()
        except:
            pass
    
    def is_open(self):
        """Check if keyboard window is still open."""
        try:
            self.window.state()
            return True
        except tk.TclError:
            return False
    
    
    def reset_gaze_tracking(self):
        """Reset gaze smoothing buffer, focus counter, and gaze position."""
        self.gaze_smoother.clear()
        self.focus_counter = 0
        self.focus_candidate = None
        self.previous_gaze_key = None
        # Clear gaze position for clean appearance
        self.current_gaze_px = None
        self.current_gaze_py = None
    
    def set_smoothing_buffer_size(self, size):
        """
        Adjust gaze smoothing strength.
        
        Args:
            size: Number of samples to average (3-10 recommended)
                  - Smaller = more responsive but jittery (3)
                  - Larger = smoother but slower (10)
        """
        self.gaze_smoother = GazeSmoothingBuffer(buffer_size=size)
    
    def set_focus_stability_frames(self, num_frames):
        """
        Adjust how long gaze must be stable before highlighting a key.
        
        Args:
            num_frames: Number of frames required (1-5 recommended)
                       - Lower = faster selection but more mis-highlights (1)
                       - Higher = more stable but slower (5)
        """
        self.focus_stability_frames = num_frames
        self.focus_counter = 0
    
    def set_scale(self, scale_factor):
        """
        Dynamically scale keyboard size.
        
        Args:
            scale_factor: Multiplier for key size (1.0 = default, 0.8 = 20% smaller, 1.2 = 20% larger)
        """
        base_key_size = 65  # Base size
        self.key_size = int(base_key_size * scale_factor)
        
        # Recalculate dimensions
        self._calculate_keyboard_dimensions()
        
        # Rebuild keyboard
        self._create_keyboard()
    
    def get_keyboard_info(self):
        """
        Get keyboard layout information for debugging.
        
        Returns:
            dict: Information about keyboard configuration
        """
        return {
            'layout': 'QWERTY',
            'rows': self.rows,
            'key_size': self.key_size,
            'total_keys': len(self.key_positions),
            'spacebar_width': self.key_positions.get('SPACE', {}).get('width', 0),
            'highlighted_key': self.highlighted_key,
            'selected_key': self.selected_key,
            'window_width': self.width,
            'window_height': self.height
        }
    
    def validate_initialization(self):
        """
        Check if keyboard is properly initialized.
        Returns dict with validation status.
        """
        validation = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check if window exists
        try:
            if not self.window.winfo_exists():
                validation['is_valid'] = False
                validation['errors'].append('Window does not exist')
        except Exception as e:
            validation['is_valid'] = False
            validation['errors'].append(f'Window check failed: {e}')
        
        # Check if key_positions is populated
        if not self.key_positions or len(self.key_positions) == 0:
            validation['is_valid'] = False
            validation['errors'].append('key_positions dictionary is empty')
        else:
            validation['info'] = f'Keyboard has {len(self.key_positions)} keys'
        
        # Check for required QWERTY keys
        required_keys = ['Q', 'SPACE', 'BACKSPACE', 'ENTER']
        for key in required_keys:
            if key not in self.key_positions:
                validation['warnings'].append(f'Missing key: {key}')
        
        # Check canvas
        if not hasattr(self, 'canvas') or self.canvas is None:
            validation['is_valid'] = False
            validation['errors'].append('Canvas not created')
        
        # Verify spacebar is wide enough
        spacebar_width = self.key_positions.get('SPACE', {}).get('width', 0)
        if spacebar_width < self.key_size * 5:
            validation['warnings'].append(f'Spacebar may be too narrow: {spacebar_width}px')
        
        return validation
    
    def close(self):
        """Close the keyboard window or clear embedded frame."""
        try:
            if hasattr(self, 'window') and self.window:
                if self.is_embedded:
                    # For embedded mode, just hide the canvas
                    if hasattr(self, 'canvas'):
                        self.canvas.delete("all")
                else:
                    # For floating windows, destroy them
                    self.window.destroy()
                self.window = None
        except Exception as e:
            print(f"[WARNING] Error closing keyboard: {e}")
