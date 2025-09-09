# enhanced_selection.py
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageGrab, ImageDraw, ImageFilter
import time
import math
import threading
from typing import Tuple, Optional, Callable
import ctypes
from ctypes import wintypes

# Windows API constants for DPI awareness and window detection
try:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    gdi32 = ctypes.windll.gdi32
    
    # DPI awareness
    user32.SetProcessDpiAwarenessContext(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
except:
    user32 = kernel32 = gdi32 = None

class PerformanceMonitor:
    """Monitor and optimize rendering performance"""
    def __init__(self):
        self.frame_times = []
        self.target_fps = 60
        self.frame_budget = 1.0 / self.target_fps
        
    def start_frame(self):
        self.frame_start = time.perf_counter()
        
    def end_frame(self):
        frame_time = time.perf_counter() - self.frame_start
        self.frame_times.append(frame_time)
        if len(self.frame_times) > 60:  # Keep last 60 frames
            self.frame_times.pop(0)
            
    def get_avg_fps(self):
        if not self.frame_times:
            return 0
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0

class WindowDetector:
    """Detect windows for smart snapping"""
    def __init__(self):
        self.window_rects = []
        self.snap_threshold = 10
        
    def update_windows(self):
        """Update list of window rectangles for snapping"""
        if not user32:
            return
            
        self.window_rects = []
        
        def enum_windows_proc(hwnd, lParam):
            if user32.IsWindowVisible(hwnd):
                rect = wintypes.RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    # Convert to tuple for easier handling
                    window_rect = (rect.left, rect.top, rect.right, rect.bottom)
                    self.window_rects.append(window_rect)
            return True
            
        try:
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(EnumWindowsProc(enum_windows_proc), 0)
        except:
            pass
            
    def snap_to_windows(self, x1: int, y1: int, x2: int, y2: int) -> Tuple[int, int, int, int]:
        """Snap selection rectangle to nearby windows"""
        if not self.window_rects:
            return x1, y1, x2, y2
            
        snapped_x1, snapped_y1, snapped_x2, snapped_y2 = x1, y1, x2, y2
        
        for wx1, wy1, wx2, wy2 in self.window_rects:
            # Check if selection is close to window edges
            if abs(x1 - wx1) < self.snap_threshold:
                snapped_x1 = wx1
            if abs(y1 - wy1) < self.snap_threshold:
                snapped_y1 = wy1
            if abs(x2 - wx2) < self.snap_threshold:
                snapped_x2 = wx2
            if abs(y2 - wy2) < self.snap_threshold:
                snapped_y2 = wy2
                
        return snapped_x1, snapped_y1, snapped_x2, snapped_y2

class MagnifierLens:
    """High-performance magnifier with smooth rendering"""
    def __init__(self, canvas: tk.Canvas, screenshot: Image.Image):
        self.canvas = canvas
        self.screenshot = screenshot
        self.zoom_factor = 3
        self.lens_size = 120
        self.is_visible = False
        self.last_pos = (0, 0)
        self.magnifier_window = None
        
    def create_magnifier_window(self):
        """Create separate window for magnifier to avoid canvas conflicts"""
        if self.magnifier_window:
            return
            
        self.magnifier_window = tk.Toplevel()
        self.magnifier_window.overrideredirect(True)
        self.magnifier_window.attributes("-topmost", True)
        self.magnifier_window.attributes("-alpha", 0.9)
        
        # Create circular frame
        self.mag_canvas = tk.Canvas(
            self.magnifier_window, 
            width=self.lens_size, 
            height=self.lens_size,
            highlightthickness=0,
            bd=0
        )
        self.mag_canvas.pack()
        
    def update_position(self, x: int, y: int):
        """Update magnifier position with smooth movement"""
        if not self.is_visible:
            return
            
        # Avoid unnecessary updates
        if abs(x - self.last_pos[0]) < 2 and abs(y - self.last_pos[1]) < 2:
            return
            
        self.last_pos = (x, y)
        
        if not self.magnifier_window:
            self.create_magnifier_window()
            
        # Position magnifier offset from cursor
        offset_x, offset_y = 20, -140
        screen_width = self.canvas.winfo_screenwidth()
        screen_height = self.canvas.winfo_screenheight()
        
        # Keep magnifier on screen
        mag_x = min(max(x + offset_x, 0), screen_width - self.lens_size)
        mag_y = min(max(y + offset_y, 0), screen_height - self.lens_size)
        
        self.magnifier_window.geometry(f"{self.lens_size}x{self.lens_size}+{mag_x}+{mag_y}")
        
        # Create magnified view
        self._render_magnified_view(x, y)
        
    def _render_magnified_view(self, center_x: int, center_y: int):
        """Render high-quality magnified view"""
        try:
            # Calculate crop area
            crop_size = self.lens_size // (2 * self.zoom_factor)
            x1 = max(0, center_x - crop_size)
            y1 = max(0, center_y - crop_size)
            x2 = min(self.screenshot.width, center_x + crop_size)
            y2 = min(self.screenshot.height, center_y + crop_size)
            
            # Crop and resize
            cropped = self.screenshot.crop((x1, y1, x2, y2))
            magnified = cropped.resize(
                (self.lens_size - 20, self.lens_size - 20), 
                Image.Resampling.NEAREST  # Pixel-perfect for UI elements
            )
            
            # Create circular mask
            mask = Image.new('L', (self.lens_size - 20, self.lens_size - 20), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, self.lens_size - 20, self.lens_size - 20), fill=255)
            
            # Apply mask and create final image
            final_img = Image.new('RGBA', (self.lens_size, self.lens_size), (0, 0, 0, 0))
            magnified.putalpha(mask)
            final_img.paste(magnified, (10, 10), magnified)
            
            # Add crosshair
            draw = ImageDraw.Draw(final_img)
            center = self.lens_size // 2
            draw.line((center - 10, center, center + 10, center), fill=(255, 0, 0, 200), width=1)
            draw.line((center, center - 10, center, center + 10), fill=(255, 0, 0, 200), width=1)
            
            # Add border
            draw.ellipse((2, 2, self.lens_size - 2, self.lens_size - 2), 
                        outline=(255, 255, 255, 200), width=3)
            
            # Update canvas
            self.photo = ImageTk.PhotoImage(final_img)
            self.mag_canvas.delete("all")
            self.mag_canvas.create_image(0, 0, image=self.photo, anchor="nw")
            
        except Exception as e:
            print(f"Magnifier render error: {e}")
            
    def show(self):
        """Show magnifier"""
        self.is_visible = True
        if not self.magnifier_window:
            self.create_magnifier_window()
        self.magnifier_window.deiconify()
        
    def hide(self):
        """Hide magnifier"""
        self.is_visible = False
        if self.magnifier_window:
            self.magnifier_window.withdraw()
            
    def cleanup(self):
        """Clean up magnifier resources"""
        self.is_visible = False
        if self.magnifier_window:
            try:
                self.magnifier_window.destroy()
            except:
                pass
        self.magnifier_window = None

class EnhancedSelection:
    def __init__(self, master_app):
        self.app = master_app
        self.callback = master_app.process_selected_area
        self.root = None
        self.canvas = None
        self.start_pos = None
        self.screenshot_base = None
        self.magnifier = None
        self.window_detector = WindowDetector()
        self.performance_monitor = PerformanceMonitor()
        
        # Animation and rendering state
        self.selection_rect = None
        self.is_selecting = False
        self.last_mouse_pos = (0, 0)
        self.animation_frame = 0
        self.render_job = None
        
        # Visual settings
        self.selection_color = "#00AAFF"
        self.selection_alpha = 0.3
        self.border_width = 2
        self.dash_offset = 0
        
        # Keyboard handling
        self.keyboard_adjustment = False
        self.adjustment_step = 1
        
    def start_selection(self):
        """Start enhanced selection process"""
        delay = 150 if self.app.settings_manager.settings["hide_on_screenshot"] else 1
        if delay > 1:
            self.app.master.withdraw()
        self.app.master.after(delay, self._grab_screen)
        
    def _grab_screen(self):
        """Capture screen with enhanced error handling and DPI awareness"""
        try:
            # Get all monitors info for proper multi-monitor support
            screenshot = self._capture_all_monitors()
            if not screenshot:
                raise Exception("Failed to capture screenshot")
                
            self._setup_selection_ui(screenshot)
            
        except Exception as e:
            print(f"Screen capture error: {e}")
            self.cleanup()
            messagebox.showerror(
                "Capture Error", 
                f"Failed to capture screen: {e}\n\nTry running as administrator or check display settings."
            )
            if self.app:
                self.app.show_window()
                
    def _capture_all_monitors(self) -> Optional[Image.Image]:
        """Capture all monitors with proper DPI handling"""
        try:
            # Use PIL's all_screens parameter for multi-monitor support
            screenshot = ImageGrab.grab(all_screens=True)
            
            # Validate screenshot
            if not screenshot or screenshot.size[0] == 0 or screenshot.size[1] == 0:
                raise Exception("Invalid screenshot dimensions")
                
            return screenshot
            
        except Exception as e:
            print(f"Multi-monitor capture failed: {e}")
            # Fallback to single monitor
            try:
                return ImageGrab.grab()
            except Exception as e2:
                print(f"Single monitor capture failed: {e2}")
                return None
                
    def _setup_selection_ui(self, screenshot: Image.Image):
        """Setup selection UI with enhanced performance"""
        self.root = tk.Toplevel(self.app.master)
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(cursor="cross")
        self.root.wait_visibility()
        
        # Create high-performance canvas
        self.canvas = tk.Canvas(
            self.root, 
            cursor="cross", 
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill="both", expand=True)
        
        self.screenshot_base = screenshot
        
        # Optimize image display
        self._setup_background_image()
        
        # Initialize components
        self.magnifier = MagnifierLens(self.canvas, screenshot)
        self.window_detector.update_windows()
        
        # Bind events
        self._bind_events()
        
        # Start render loop
        self._start_render_loop()
        
    def _setup_background_image(self):
        """Setup optimized background image"""
        try:
            # Create darkened overlay for better selection visibility
            overlay = Image.new('RGBA', self.screenshot_base.size, (0, 0, 0, 100))
            background = Image.alpha_composite(
                self.screenshot_base.convert('RGBA'), 
                overlay
            )
            
            self.image_tk = ImageTk.PhotoImage(background)
            self.canvas.create_image(0, 0, image=self.image_tk, anchor="nw")
            
        except Exception as e:
            print(f"Background setup error: {e}")
            # Fallback to original image
            self.image_tk = ImageTk.PhotoImage(self.screenshot_base)
            self.canvas.create_image(0, 0, image=self.image_tk, anchor="nw")
            
    def _bind_events(self):
        """Bind all UI events"""
        # Mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        
        # Keyboard events
        self.root.bind("<Escape>", self.cancel_selection)
        self.root.bind("<Return>", self.finish_selection)
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        
        # Focus events
        self.root.focus_set()
        
    def _start_render_loop(self):
        """Start high-performance render loop"""
        self._render_frame()
        
    def _render_frame(self):
        """Render single frame with performance monitoring"""
        try:
            self.performance_monitor.start_frame()
            
            if self.is_selecting and self.selection_rect:
                self._update_selection_visuals()
                
            # Animate selection border
            self.dash_offset = (self.dash_offset + 2) % 20
            self.animation_frame += 1
            
            self.performance_monitor.end_frame()
            
            # Schedule next frame based on performance
            avg_fps = self.performance_monitor.get_avg_fps()
            if avg_fps < 30:  # Reduce update rate if performance is poor
                delay = 33  # ~30 FPS
            else:
                delay = 16  # ~60 FPS
                
            if self.root and self.root.winfo_exists():
                self.render_job = self.root.after(delay, self._render_frame)
                
        except Exception as e:
            print(f"Render frame error: {e}")
            
    def on_mouse_move(self, event):
        """Handle mouse movement with magnifier"""
        self.last_mouse_pos = (event.x, event.y)
        
        if not self.is_selecting:
            # Show magnifier when hovering
            if self.magnifier and not self.magnifier.is_visible:
                self.magnifier.show()
            self.magnifier.update_position(event.x, event.y)
            
    def on_press(self, event):
        """Handle mouse press with enhanced feedback"""
        self.start_pos = (event.x, event.y)
        self.is_selecting = True
        
        if self.magnifier:
            self.magnifier.hide()
            
        # Create selection rectangle
        self.selection_rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline=self.selection_color,
            width=self.border_width,
            dash=(8, 4)
        )
        
        # Create dimension text background
        self.dim_bg = self.canvas.create_rectangle(0, 0, 0, 0, fill="black", outline="")
        self.dim_text = self.canvas.create_text(
            0, 0, text="", fill="white", 
            anchor="nw", font=("Arial", 10, "bold")
        )
        
    def on_drag(self, event):
        """Handle mouse drag with snapping and smooth updates"""
        if not self.is_selecting or not self.start_pos:
            return
            
        x1, y1 = self.start_pos
        x2, y2 = event.x, event.y
        
        # Apply window snapping if enabled
        if self.app.settings_manager.settings.get("enable_window_snapping", True):
            x1, y1, x2, y2 = self.window_detector.snap_to_windows(x1, y1, x2, y2)
            
        # Ensure valid rectangle
        min_x, min_y = min(x1, x2), min(y1, y2)
        max_x, max_y = max(x1, x2), max(y1, y2)
        
        # Update selection rectangle
        self.canvas.coords(self.selection_rect, min_x, min_y, max_x, max_y)
        
        # Update dimension display
        width = max_x - min_x
        height = max_y - min_y
        dim_string = f"{width} × {height}"
        
        text_x, text_y = min_x + 5, min_y - 25
        if text_y < 0:  # Keep text visible
            text_y = min_y + 5
            
        self.canvas.coords(self.dim_text, text_x, text_y)
        self.canvas.itemconfigure(self.dim_text, text=dim_string)
        
        # Update text background
        bbox = self.canvas.bbox(self.dim_text)
        if bbox:
            self.canvas.coords(self.dim_bg, bbox[0]-4, bbox[1]-2, bbox[2]+4, bbox[3]+2)
            
    def _update_selection_visuals(self):
        """Update selection visuals with animations"""
        if not self.selection_rect:
            return
            
        # Animate dashed border
        self.canvas.itemconfig(
            self.selection_rect,
            dashoffset=self.dash_offset
        )
        
    def on_release(self, event):
        """Handle mouse release with validation"""
        if not self.is_selecting or not self.start_pos:
            self.cleanup()
            return
            
        x1, y1 = self.start_pos
        x2, y2 = event.x, event.y
        
        # Calculate final selection
        min_x, min_y = min(x1, x2), min(y1, y2)
        max_x, max_y = max(x1, x2), max(y1, y2)
        
        # Validate selection size
        if max_x - min_x < 5 or max_y - min_y < 5:
            self.cancel_selection()
            return
            
        # Clean up selection visuals
        self.canvas.delete(self.selection_rect, self.dim_bg, self.dim_text)
        
        # Show action panel
        self.show_action_panel((min_x, min_y, max_x, max_y))
        
    def show_action_panel(self, bbox: Tuple[int, int, int, int]):
        """Show enhanced action panel with animations"""
        self.is_selecting = False
        self.canvas.config(cursor="")
        
        # Create selection highlight
        self._create_selection_highlight(bbox)
        
        # Create action panel
        panel = tk.Frame(self.root, bg="#2D2D2D", bd=2, relief="solid")
        panel.configure(highlightbackground="#007ACC", highlightthickness=1)
        
        # Enhanced action buttons
        actions = {
            "✓ Save": ("#28a745", "save", "Save screenshot to file"),
            "📋 Copy": ("#007ACC", "copy", "Copy to clipboard"),
        }
        
        if self.app.settings_manager.settings.get("enable_catbox_upload", True):
            actions["☁️ Upload"] = ("#8e44ad", "upload", "Upload to Catbox.moe")
            
        actions.update({
            "🔍 QR Scan": ("#5856d6", "scan_qr", "Scan QR codes"),
            "❌ Cancel": ("#dc3545", "cancel", "Cancel selection")
        })
        
        for text, (bg_color, action, tooltip) in actions.items():
            btn = tk.Button(
                panel, text=text, bg=bg_color, fg="white",
                activebackground=self._darken_color(bg_color), 
                activeforeground="white",
                relief="flat", font=("Arial", 9, "bold"),
                command=lambda a=action: self.finalize(bbox, a),
                padx=12, pady=6, cursor="hand2"
            )
            btn.pack(side="left", padx=2, pady=4)
            
            # Simple tooltip
            btn.bind("<Enter>", lambda e, t=tooltip: self._show_tooltip(e, t))
            btn.bind("<Leave>", self._hide_tooltip)
            
        # Position panel smartly
        self._position_panel(panel, bbox)
        
    def _create_selection_highlight(self, bbox: Tuple[int, int, int, int]):
        """Create animated selection highlight"""
        x1, y1, x2, y2 = bbox
        w, h = self.screenshot_base.size
        
        # Create overlay areas (darkened regions outside selection)
        self.canvas.create_rectangle(0, 0, w, y1, fill='black', stipple='gray50', outline="")
        self.canvas.create_rectangle(0, y2, w, h, fill='black', stipple='gray50', outline="")
        self.canvas.create_rectangle(0, y1, x1, y2, fill='black', stipple='gray50', outline="")
        self.canvas.create_rectangle(x2, y1, w, y2, fill='black', stipple='gray50', outline="")
        
        # Create animated selection border
        self.canvas.create_rectangle(
            x1-1, y1-1, x2+1, y2+1,
            outline="#00AAFF", width=3
        )
        
    def _position_panel(self, panel, bbox: Tuple[int, int, int, int]):
        """Position action panel optimally"""
        x1, y1, x2, y2 = bbox
        panel.update_idletasks()
        panel_width = panel.winfo_reqwidth()
        panel_height = panel.winfo_reqheight()
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Default position below selection
        panel_x = x1
        panel_y = y2 + 10
        anchor = "nw"
        
        # Adjust if panel goes off screen
        if panel_x + panel_width > screen_width:
            panel_x = screen_width - panel_width - 10
            
        if panel_y + panel_height > screen_height:
            panel_y = y1 - panel_height - 10
            anchor = "nw"
            if panel_y < 0:
                panel_y = y1 + (y2 - y1) // 2 - panel_height // 2
                
        self.canvas.create_window(panel_x, panel_y, window=panel, anchor=anchor)
        
    def _darken_color(self, color: str) -> str:
        """Darken a hex color for hover effects"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        darker_rgb = tuple(max(0, int(c * 0.8)) for c in rgb)
        return f"#{darker_rgb[0]:02x}{darker_rgb[1]:02x}{darker_rgb[2]:02x}"
        
    def _show_tooltip(self, event, text):
        """Show simple tooltip"""
        # Implementation would go here - simplified for brevity
        pass
        
    def _hide_tooltip(self, event):
        """Hide tooltip"""
        # Implementation would go here - simplified for brevity
        pass
        
    def on_key_press(self, event):
        """Handle keyboard input for fine adjustments"""
        if event.keysym in ['Up', 'Down', 'Left', 'Right']:
            self.keyboard_adjustment = True
            # Implementation for arrow key adjustments would go here
        elif event.keysym == 'Shift_L' or event.keysym == 'Shift_R':
            self.adjustment_step = 10  # Larger steps with shift
            
    def on_key_release(self, event):
        """Handle key release"""
        if event.keysym == 'Shift_L' or event.keysym == 'Shift_R':
            self.adjustment_step = 1
            
    def finish_selection(self, event=None):
        """Finish selection with current bounds"""
        if self.selection_rect:
            bbox = self.canvas.coords(self.selection_rect)
            if len(bbox) == 4:
                self.show_action_panel(tuple(map(int, bbox)))
                
    def finalize(self, bbox: Tuple[int, int, int, int], action: str):
        """Finalize selection with enhanced error handling"""
        image_to_process = None
        
        try:
            if action != "cancel":
                x1, y1, x2, y2 = bbox
                # Ensure coordinates are within screenshot bounds
                x1 = max(0, min(x1, self.screenshot_base.width))
                y1 = max(0, min(y1, self.screenshot_base.height))
                x2 = max(0, min(x2, self.screenshot_base.width))
                y2 = max(0, min(y2, self.screenshot_base.height))
                
                if x2 > x1 and y2 > y1:
                    image_to_process = self.screenshot_base.crop((x1, y1, x2, y2))
                    
        except Exception as e:
            print(f"Selection finalization error: {e}")
            image_to_process = None
            
        self.callback(image_to_process, action)
        self.cleanup()
        
    def cancel_selection(self, event=None):
        """Cancel selection process"""
        self.callback(None, "cancel")
        self.cleanup()
        
    def cleanup(self):
        """Enhanced cleanup with proper resource management"""
        try:
            # Cancel any pending render jobs
            if self.render_job:
                self.root.after_cancel(self.render_job)
                self.render_job = None
                
            # Cleanup magnifier
            if self.magnifier:
                self.magnifier.cleanup()
                self.magnifier = None
                
            # Cleanup UI elements
            if self.root and self.root.winfo_exists():
                self.root.destroy()
                
        except Exception as e:
            print(f"Cleanup error: {e}")
        finally:
            self.root = None
            self.canvas = None
            self.screenshot_base = None
            self.image_tk = None
            self.is_selecting = False

# Backward compatibility alias
SimpleSelection = EnhancedSelection