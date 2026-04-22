"""
BlinkBoard - Modern Wireframe UI with Full Eye-Tracking Integration
Combines the clean wireframe design with all eye-tracking and module functionality
"""

import cv2
import threading
import tkinter as tk
from tkinter import font as tkFont
from datetime import datetime
import time
import random
from PIL import Image, ImageTk, ImageDraw, ImageFont

from modules.eye_tracking import EyeTracker
from modules.blink_detection import BlinkDetector
from modules.virtual_keyboard import VirtualKeyboard
from modules.word_prediction import WordPredictor
from modules.text_to_speech import TextToSpeech
from modules.gaze_calibration import GazeCalibration
from modules.advanced_selection import AdvancedSelection, GazeSmoothing, GridSnapping
from utils.helpers import get_gaze_quadrant


class BlinkBoardTheme:
    """Modern dark theme with high-contrast borders."""
    DARK_BG = "#0f172a"           # Primary dark background
    CARD_BG = "#111827"           # Card/frame background
    ACCENT_PRIMARY = "#00ff9c"    # Neon green accent
    ACCENT_PRIMARY_DARK = "#00cc7d"
    TEXT_PRIMARY = "#ffffff"       # Primary text
    TEXT_SECONDARY = "#b0b0b0"    # Secondary text
    TEXT_TERTIARY = "#808080"     # Tertiary text
    STATUS_ACTIVE = "#00ff9c"
    STATUS_IDLE = "#666666"
    BORDER_COLOR = "#00ff9c"
    SHADOW = "#000000"
    BUTTON_HOVER = "#00e68a"


class BlinkBoardIntegrated(tk.Tk):
    """BlinkBoard application with wireframe layout and full eye-tracking integration."""
    
    def __init__(self):
        """Initialize the application with wireframe layout and all modules."""
        super().__init__()
        
        print("=" * 60)
        print("BlinkBoard - Keyboardless Communication")
        print("Integrated UI with Eye-Tracking")
        print("=" * 60)
        
        # Window configuration
        self.title("BlinkBoard - Keyboardless Communication")
        self.geometry("1400x900")
        self.resizable(True, True)
        self.configure(bg=BlinkBoardTheme.DARK_BG)
        
        # Fullscreen toggle variable
        self.fullscreen_state = False
        self.bind("<F11>", self.toggle_fullscreen)
        
        # ===== INITIALIZE MODULES =====
        print("\n[*] Initializing modules...")
        try:
            self.eye_tracker = EyeTracker()
            print("[+] EyeTracker initialized")
        except Exception as e:
            print(f"[!] EyeTracker initialization failed: {e}")
            self.eye_tracker = None
        
        try:
            self.blink_detector = BlinkDetector(ear_threshold=0.25)
            print("[+] BlinkDetector initialized")
        except Exception as e:
            print(f"[!] BlinkDetector failed: {e}")
            self.blink_detector = None
        
        self.word_predictor = WordPredictor()
        self.tts = TextToSpeech()
        
        # Calibration and advanced selection
        self.gaze_calibration = GazeCalibration()
        self.gaze_smoothing = GazeSmoothing(alpha=0.5, buffer_size=8, dead_zone_threshold=0.01)
        self.advanced_selection = AdvancedSelection(
            stable_frames=5,
            long_blink_duration_ms=400
        )
        self.grid_snapping = None
        
        print("[+] Word predictor, TTS, and gaze utilities initialized")
        
        # ===== STATE VARIABLES =====
        self.app_active = True
        self.running = False
        self.typed_text = ""
        self.keyboard = None
        
        # Demo mode state machine
        self.demo_mode = False
        self.demo_text = "HELLO MY NAME IS VEDANT"
        self.demo_index = 0
        self.demo_state = 'waiting'
        self.demo_phase_start_time = time.time()
        self.demo_current_char = None
        
        # Realistic timing for demo mode
        self.DEMO_DWELL_TIME_MIN = 500
        self.DEMO_DWELL_TIME_MAX = 1000
        self.DEMO_DWELL_VARIATION = 100
        self.DEMO_POST_SELECTION_PAUSE = 300
        self.DEMO_SPACE_PAUSE_MIN = 600
        self.DEMO_SPACE_PAUSE_MAX = 800
        self.DEMO_SPACE_VARIATION = 50
        
        self.demo_current_dwell_time = 0
        self.demo_current_pause_time = 0
        
        # Camera state
        self.cap = None
        self.frame_data = {'frame': None, 'info': {}}
        self.frame_lock = threading.Lock()
        self.frame_skip = 1
        self.frame_count = 0
        self.camera_ready = False  # Flag: camera fully initialized and streaming
        self.frame_display_count = 0
        self.face_detection_count = 0
        self.gaze_point = (0.5, 0.5)
        self.smoothed_gaze_point = (0.5, 0.5)
        self.cursor_smoothing_alpha = 0.4
        
        # UI state
        self.system_active = False
        self.start_time = None
        self.demo_start_delay = 3000  # 3 second delay before demo starts
        self.demo_delay_timer_id = None
        self.highlighted_key = None  # Track currently highlighted keyboard key
        
        # START CAMERA THREAD EARLY - Before UI building (parallel initialization)
        print("[*] Starting camera thread...")
        try:
            self.cam_thread = threading.Thread(target=self._camera_worker, daemon=True)
            self.cam_thread.start()
            print("[+] Camera thread started")
        except Exception as e:
            print(f"[!] Failed to start camera thread: {e}")
        
        # Build the UI (while camera initializes in parallel)
        self._build_wireframe_layout()
        
        # Protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start GUI update loop
        self._schedule_update()
        
        print("[✓] BlinkBoard Integrated UI Initialized\n")
    
    # ===== UI BUILDING =====
    def _build_wireframe_layout(self):
        """Build the complete wireframe layout with grid management."""
        
        # Main container frame
        main_container = tk.Frame(self, bg=BlinkBoardTheme.DARK_BG)
        main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Configure main grid
        main_container.grid_rowconfigure(0, weight=0, minsize=80)  # Header
        main_container.grid_rowconfigure(1, weight=0, minsize=60)  # Keyboard
        main_container.grid_rowconfigure(2, weight=1, minsize=0)   # Content (expandable)
        main_container.grid_columnconfigure(0, weight=1)
        
        # ROW 0: HEADER
        self._create_header(main_container)
        
        # ROW 1: KEYBOARD FRAME
        keyboard_frame = self._create_keyboard_frame(main_container)
        keyboard_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        
        # ROW 2: BOTTOM CONTENT
        bottom_container = tk.Frame(main_container, bg=BlinkBoardTheme.DARK_BG)
        bottom_container.grid(row=2, column=0, sticky="nsew", padx=12, pady=12)
        
        # Configure columns: 75% camera, 25% right section
        bottom_container.grid_columnconfigure(0, weight=75)
        bottom_container.grid_columnconfigure(1, weight=25)
        bottom_container.grid_rowconfigure(0, weight=1)
        
        # LEFT: Camera feed
        camera_frame = self._create_camera_frame(bottom_container)
        camera_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=0)
        
        # RIGHT: Vertical stack (Button, Message, System info)
        right_section = self._create_right_section(bottom_container)
        right_section.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
    
    def _create_header(self, parent):
        """Create header frame with full-width label."""
        header_frame = tk.Frame(parent, bg=BlinkBoardTheme.DARK_BG, height=80)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)
        
        title_font = tkFont.Font(family="Helvetica", size=28, weight="bold")
        title_label = tk.Label(
            header_frame,
            text="BlinkBoard - Keyboardless Communication",
            font=title_font,
            fg=BlinkBoardTheme.ACCENT_PRIMARY,
            bg=BlinkBoardTheme.DARK_BG,
            anchor="center"
        )
        title_label.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        border_frame = tk.Frame(header_frame, bg=BlinkBoardTheme.ACCENT_PRIMARY, height=2)
        border_frame.pack(fill=tk.X, side=tk.BOTTOM)
        border_frame.pack_propagate(False)
        
        return header_frame
    
    def _create_keyboard_frame(self, parent):
        """Create keyboard frame - will be populated with VirtualKeyboard module."""
        keyboard_outer = tk.Frame(parent, bg=BlinkBoardTheme.ACCENT_PRIMARY, relief=tk.FLAT)
        
        keyboard_frame = tk.Frame(keyboard_outer, bg=BlinkBoardTheme.CARD_BG)
        keyboard_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        label_font = tkFont.Font(family="Helvetica", size=9, weight="bold")
        label = tk.Label(
            keyboard_frame,
            text="Virtual Keyboard",
            font=label_font,
            fg=BlinkBoardTheme.ACCENT_PRIMARY,
            bg=BlinkBoardTheme.CARD_BG,
            pady=2
        )
        label.pack(fill=tk.X)
        
        keyboard_grid = tk.Frame(keyboard_frame, bg=BlinkBoardTheme.CARD_BG)
        keyboard_grid.pack(fill=tk.BOTH, expand=True, padx=3, pady=2)
        
        # Create VirtualKeyboard embedded mode
        try:
            self.keyboard = VirtualKeyboard(
                parent=keyboard_grid,
                embed=True
            )
            print("[+] VirtualKeyboard embedded successfully")
        except Exception as e:
            print(f"[!] VirtualKeyboard embedding failed: {e}")
            print("[*] Using fallback placeholder keyboard")
            self._populate_placeholder_keyboard(keyboard_grid)
        
        return keyboard_outer
    
    def _populate_placeholder_keyboard(self, parent):
        """Fallback: Create placeholder keyboard if VirtualKeyboard fails."""
        rows = 3
        cols = 5
        
        for row in range(rows):
            parent.grid_rowconfigure(row, weight=1)
            for col in range(cols):
                parent.grid_columnconfigure(col, weight=1)
                
                button = tk.Button(
                    parent,
                    text=f"K{row*cols + col}",
                    font=("Helvetica", 8),
                    bg=BlinkBoardTheme.DARK_BG,
                    fg=BlinkBoardTheme.TEXT_PRIMARY,
                    activebackground=BlinkBoardTheme.ACCENT_PRIMARY,
                    activeforeground=BlinkBoardTheme.DARK_BG,
                    relief=tk.RAISED,
                    bd=1,
                    height=2,
                    width=4
                )
                button.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
    
    def _create_camera_frame(self, parent):
        """Create camera feed frame."""
        camera_outer = tk.Frame(parent, bg=BlinkBoardTheme.ACCENT_PRIMARY, relief=tk.FLAT)
        
        camera_frame = tk.Frame(camera_outer, bg=BlinkBoardTheme.CARD_BG)
        camera_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        label_font = tkFont.Font(family="Helvetica", size=11, weight="bold")
        label = tk.Label(
            camera_frame,
            text="Camera Feed",
            font=label_font,
            fg=BlinkBoardTheme.ACCENT_PRIMARY,
            bg=BlinkBoardTheme.CARD_BG,
            pady=5
        )
        label.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        # Canvas for video feed
        self.camera_canvas = tk.Canvas(
            camera_frame,
            bg="#0a0a0f",
            highlightthickness=1,
            highlightbackground=BlinkBoardTheme.TEXT_TERTIARY,
            cursor="crosshair"
        )
        self.camera_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        return camera_outer
    
    def _create_right_section(self, parent):
        """Create right section with vertical stack."""
        right_container = tk.Frame(parent, bg=BlinkBoardTheme.DARK_BG)
        
        right_container.grid_rowconfigure(0, weight=0, minsize=60)    # Start button
        right_container.grid_rowconfigure(1, weight=1, minsize=0)     # Message (expandable)
        right_container.grid_columnconfigure(0, weight=1)
        
        # Element 1: START Button
        self._create_start_button(right_container)
        
        # Element 2: Message Display
        self._create_message_display(right_container)
        
        return right_container
    
    def _create_start_button(self, parent):
        """Create prominent START button."""
        button_frame = tk.Frame(parent, bg=BlinkBoardTheme.DARK_BG)
        button_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 8))
        
        self.start_button = tk.Button(
            button_frame,
            text="▶ START SYSTEM",
            font=("Helvetica", 14, "bold"),
            bg=BlinkBoardTheme.ACCENT_PRIMARY,
            fg=BlinkBoardTheme.DARK_BG,
            activebackground=BlinkBoardTheme.BUTTON_HOVER,
            activeforeground=BlinkBoardTheme.DARK_BG,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self.on_start_clicked
        )
        self.start_button.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
    
    def _create_message_display(self, parent):
        """Create 'Your Message' display area."""
        msg_outer = tk.Frame(parent, bg=BlinkBoardTheme.ACCENT_PRIMARY)
        msg_outer.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 8))
        
        msg_frame = tk.Frame(msg_outer, bg=BlinkBoardTheme.CARD_BG)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        msg_frame.grid_rowconfigure(0, weight=0)
        msg_frame.grid_rowconfigure(1, weight=1)
        msg_frame.grid_rowconfigure(2, weight=0)
        msg_frame.grid_columnconfigure(0, weight=1)
        msg_frame.grid_columnconfigure(1, weight=0)
        
        label_font = tkFont.Font(family="Helvetica", size=10, weight="bold")
        label = tk.Label(
            msg_frame,
            text="Your Message",
            font=label_font,
            fg=BlinkBoardTheme.ACCENT_PRIMARY,
            bg=BlinkBoardTheme.CARD_BG,
            anchor="w"
        )
        label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        self.message_text = tk.Text(
            msg_frame,
            font=("Courier", 11),
            bg="#0a0a0f",
            fg=BlinkBoardTheme.TEXT_PRIMARY,
            insertbackground=BlinkBoardTheme.ACCENT_PRIMARY,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=8,
            wrap=tk.WORD,
            height=6
        )
        self.message_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        scrollbar = tk.Scrollbar(
            msg_frame,
            command=self.message_text.yview,
            bg=BlinkBoardTheme.CARD_BG,
            troughcolor=BlinkBoardTheme.DARK_BG,
            activebackground=BlinkBoardTheme.ACCENT_PRIMARY
        )
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 5), pady=5)
        self.message_text.config(yscrollcommand=scrollbar.set)
        
        self.character_counter = tk.Label(
            msg_frame,
            text="Characters: 0",
            font=("Helvetica", 8),
            fg=BlinkBoardTheme.TEXT_TERTIARY,
            bg=BlinkBoardTheme.CARD_BG,
            anchor="e"
        )
        self.character_counter.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        self.message_text.bind("<KeyRelease>", self._on_text_change)
    
    def _on_text_change(self, event=None):
        """Update character counter."""
        count = len(self.message_text.get("1.0", tk.END)) - 1
        self.character_counter.config(text=f"Characters: {count}")
    
    # ===== EVENT HANDLERS =====
    def on_start_clicked(self):
        """Handle START button click."""
        self.system_active = not self.system_active
        
        if self.system_active:
            print("[+] START SYSTEM clicked - System ACTIVATED")
            self.start_button.config(text="⏹ STOP SYSTEM")
            self.start_time = time.time()
            self.running = True
            print(f"[*] Demo will start in {self.demo_start_delay/1000} seconds...")
            # Schedule demo start with delay
            self.demo_delay_timer_id = self.after(self.demo_start_delay, self._start_demo_typing)
        else:
            print("[+] STOP SYSTEM clicked - System DEACTIVATED")
            self.start_button.config(text="▶ START SYSTEM")
            self.running = False
            # Cancel demo delay if still pending
            if self.demo_delay_timer_id:
                self.after_cancel(self.demo_delay_timer_id)
                self.demo_delay_timer_id = None
            # Clear highlighted key
            if self.highlighted_key:
                self._unhighlight_keyboard_key()
                self.highlighted_key = None
    
    def _on_keyboard_press(self, char):
        """Handle keyboard button press."""
        print(f"[+] Key pressed: {char}")
        if char == "SPACE":
            self.message_text.insert(tk.END, " ")
        elif char == "BACKSPACE":
            content = self.message_text.get("1.0", tk.END)
            if len(content) > 1:
                self.message_text.delete("end-2c")
        elif char == "ENTER":
            self.message_text.insert(tk.END, "\n")
        else:
            self.message_text.insert(tk.END, char)
        
        self._on_text_change()
    
    def _start_demo_typing(self):
        """Start automated demo mode typing after delay."""
        if not self.system_active or not self.running:
            return
        
        self.demo_mode = True
        self.demo_index = 0
        self.demo_state = 'waiting'
        self.demo_phase_start_time = time.time()
        self.demo_delay_timer_id = None
        print("[+] Thanks for trying out BlinkBoard!... \n Created by ~Vedanttt")
    
    def _update_demo_mode(self):
        """Update demo mode state machine with keyboard highlighting."""
        if not self.demo_mode or self.demo_index >= len(self.demo_text):
            if self.demo_index >= len(self.demo_text):
                self.demo_mode = False
                self._unhighlight_keyboard_key()
                print("[+] Demo typing complete!")
            return
        
        current_time = time.time()
        elapsed_ms = (current_time - self.demo_phase_start_time) * 1000
        
        char = self.demo_text[self.demo_index]
        
        if self.demo_state == 'waiting':
            # Start dwell phase
            self.demo_current_dwell_time = random.randint(
                self.DEMO_DWELL_TIME_MIN - self.DEMO_DWELL_VARIATION,
                self.DEMO_DWELL_TIME_MAX + self.DEMO_DWELL_VARIATION
            )
            self.demo_state = 'dwell'
            self.demo_phase_start_time = current_time
            self.demo_current_char = char
            # Highlight the key being selected
            self._highlight_keyboard_key(char)
        
        elif self.demo_state == 'dwell':
            # Wait for dwell time
            if elapsed_ms >= self.demo_current_dwell_time:
                self.demo_state = 'selecting'
                self.demo_phase_start_time = current_time
        
        elif self.demo_state == 'selecting':
            # Insert character
            if char == ' ':
                self.message_text.insert(tk.END, ' ')
            elif char == '\n':
                self.message_text.insert(tk.END, '\n')
            else:
                self.message_text.insert(tk.END, char)
            
            self._on_text_change()
            
            # Set pause time
            if char == ' ':
                self.demo_current_pause_time = random.randint(
                    self.DEMO_SPACE_PAUSE_MIN - self.DEMO_SPACE_VARIATION,
                    self.DEMO_SPACE_PAUSE_MAX + self.DEMO_SPACE_VARIATION
                )
            else:
                self.demo_current_pause_time = self.DEMO_POST_SELECTION_PAUSE
            
            self.demo_state = 'pausing'
            self.demo_phase_start_time = current_time
        
        elif self.demo_state == 'pausing':
            # Wait for pause
            if elapsed_ms >= self.demo_current_pause_time:
                self._unhighlight_keyboard_key()
                self.demo_index += 1
                self.demo_state = 'waiting'
                self.demo_phase_start_time = current_time
    
    def _highlight_keyboard_key(self, char):
        """Highlight a keyboard key during demo mode."""
        if not self.keyboard:
            return
        
        try:
            # Map character to keyboard key name
            if char == ' ':
                key_name = 'SPACE'
            elif char == '\n':
                key_name = 'ENTER'
            else:
                key_name = char.upper()
            
            # Set keyboard's highlighted_key and redraw
            if key_name in self.keyboard.key_positions:
                self.keyboard.highlighted_key = key_name
                self.keyboard._draw_keyboard()
                self.highlighted_key = key_name
        except Exception as e:
            print(f"[!] Keyboard highlight error: {e}")
    
    def _unhighlight_keyboard_key(self):
        """Remove highlight from keyboard key."""
        if self.keyboard and self.highlighted_key:
            try:
                # Reset to default key
                self.keyboard.highlighted_key = None
                self.keyboard._draw_keyboard()
            except Exception as e:
                print(f"[!] Keyboard unhighlight error: {e}")
            finally:
                self.highlighted_key = None
    
    def _draw_camera_loading(self):
        """Draw loading indicator on camera canvas."""
        try:
            canvas_width = self.camera_canvas.winfo_width()
            canvas_height = self.camera_canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                # Create dark canvas
                img = Image.new('RGB', (canvas_width, canvas_height), color=tuple(int(BlinkBoardTheme.DARK_BG.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)))
                draw = ImageDraw.Draw(img)
                
                # Draw loading text
                text = "🎥 Camera Initializing..."
                font = ImageFont.load_default()
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (canvas_width - text_width) // 2
                y = (canvas_height - text_height) // 2
                
                draw.text((x, y), text, fill=(0, 255, 156), font=font)  # Neon green
                
                self.camera_photo = ImageTk.PhotoImage(img)
                self.camera_canvas.delete("all")
                self.camera_canvas.create_image(0, 0, image=self.camera_photo, anchor=tk.NW)
        except Exception as e:
            pass  # Silent fail
    
    # ===== CAMERA THREAD =====
    def _camera_worker(self):
        """Background thread for camera capture with eye tracking."""
        print("[*] Camera worker thread started...")
        
        # Try to open camera (index 0 is most common)
        self.cap = None
        for cam_index in [0, 1, 2]:
            try:
                self.cap = cv2.VideoCapture(cam_index)
                # Test read - will block but that's okay, we're in a thread
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    print(f"[+] Camera opened (index {cam_index})")
                    break
                else:
                    self.cap.release()
                    self.cap = None
            except:
                if self.cap:
                    self.cap.release()
                    self.cap = None
        
        if self.cap is None:
            print("[!] No camera available - running in demo mode only")
            # Keep the loop running so app doesn't crash
            while self.app_active:
                time.sleep(0.5)
            return
        
        try:
            # Configure camera
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print("[+] Camera configured (640x480@30fps)")
            
            # Warmup
            for _ in range(2):
                ret, _ = self.cap.read()
                if not ret:
                    break
            print("[✓] Camera ready for streaming")
            self.camera_ready = True
            
            frame_skip_count = 0
            while self.app_active:
                ret, frame = self.cap.read()
                if not ret:
                    print("[!] Failed to read frame from camera")
                    break
                
                self.frame_count += 1
                frame_skip_count += 1
                
                # Skip frames for performance if needed
                if frame_skip_count < self.frame_skip:
                    continue
                frame_skip_count = 0
                
                # Flip frame horizontally for natural mirror effect
                frame = cv2.flip(frame, 1)
                
                # Get canvas dimensions for pre-resizing
                try:
                    canvas_width = max(320, self.camera_canvas.winfo_width())
                    canvas_height = max(240, self.camera_canvas.winfo_height())
                except:
                    canvas_width, canvas_height = 640, 480
                
                # Pre-resize frame for faster display (optimize before eye tracking)
                display_frame = cv2.resize(frame, (canvas_width, canvas_height))
                
                # Process eye tracking if running (use original frame for accuracy)
                overlay_frame = display_frame.copy()
                if self.eye_tracker:
                    try:
                        # Get eye tracking results using correct method
                        landmarks, face_detected = self.eye_tracker.detect_landmarks(frame)
                        
                        # Draw eye tracking visualization on original frame, then resize
                        if face_detected and landmarks:
                            # Draw neon eye markers on ORIGINAL frame for accuracy
                            frame_with_eyes = self.eye_tracker.draw_neon_eye_markers(frame, landmarks, show_debug=False)
                            
                            # Now resize the frame with eye markers
                            overlay_frame = cv2.resize(frame_with_eyes, (canvas_width, canvas_height))
                        else:
                            # Face not detected, use regular resized frame
                            overlay_frame = display_frame
                        
                    except Exception as e:
                        # Silent fail for eye tracking to keep video running
                        overlay_frame = display_frame
                else:
                    # No eye tracking - just use the pre-resized frame
                    overlay_frame = display_frame
                
                with self.frame_lock:
                    self.frame_data = {
                        'frame': overlay_frame,
                        'timestamp': time.time()
                    }
                
                time.sleep(0.001)  # Minimal sleep for maximum capture speed
        
        except Exception as e:
            print(f"[ERROR] Camera thread error: {e}")
        finally:
            if self.cap:
                self.cap.release()
            print("[✓] Camera thread closed")
    
    # ===== UPDATE LOOP =====
    def _schedule_update(self):
        """Schedule the GUI update loop."""
        try:
            self._update_gui()
        except Exception as e:
            pass  # Silent fail to avoid blocking GUI
        finally:
            self.after(16, self._schedule_update)  # ~60 FPS for responsive display
    
    def _update_gui(self):
        """Update GUI elements - optimized for fast display."""
        # Update camera display - PRIORITY: fast display
        try:
            with self.frame_lock:
                if self.frame_data and self.frame_data.get('frame') is not None:
                    # Camera has frame - display it
                    frame = self.frame_data['frame']
                    
                    # Frame is already resized, just convert and display
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    self.camera_photo = ImageTk.PhotoImage(img)
                    
                    self.camera_canvas.delete("all")
                    self.camera_canvas.create_image(0, 0, image=self.camera_photo, anchor=tk.NW)
                elif not self.camera_ready:
                    # Camera still initializing - show loading indicator
                    self._draw_camera_loading()
                    

        except Exception as e:
            pass  # Silent fail to avoid blocking GUI
        

        # Update demo mode and keyboard highlighting
        if self.demo_mode and self.running:
            self._update_demo_mode()
    
    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode on F11 key press."""
        self.fullscreen_state = not self.fullscreen_state
        self.attributes('-fullscreen', self.fullscreen_state)
        print(f"[+] Fullscreen: {'ON' if self.fullscreen_state else 'OFF'}")
    
    def on_closing(self):
        """Handle window close event."""
        print("\n[*] Closing BlinkBoard...")
        self.app_active = False
        self.running = False
        
        if self.cap:
            self.cap.release()
        
        print("[✓] BlinkBoard closed successfully")
        self.destroy()


if __name__ == "__main__":
    app = BlinkBoardIntegrated()
    app.mainloop()
