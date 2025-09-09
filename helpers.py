# enhanced_helpers.py
import tkinter as tk
from PIL import Image, ImageTk
import os
import time
import math
import threading
import functools
import weakref
from typing import Dict, Optional, Tuple, Any, Callable
import gc

# Create absolute path to icons directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class IconCache:
    """Thread-safe icon cache with memory management and automatic cleanup"""
    def __init__(self, max_size: int = 100):
        self.cache: Dict[str, ImageTk.PhotoImage] = {}
        self.access_times: Dict[str, float] = {}
        self.max_size = max_size
        self._lock = threading.RLock()
        
    def get(self, key: str, loader_func: Callable[[], ImageTk.PhotoImage]) -> ImageTk.PhotoImage:
        """Get icon from cache or load if not present"""
        with self._lock:
            current_time = time.time()
            
            if key in self.cache:
                self.access_times[key] = current_time
                return self.cache[key]
            
            # Load new icon
            try:
                icon = loader_func()
                self.cache[key] = icon
                self.access_times[key] = current_time
                
                # Cleanup old entries if cache is full
                if len(self.cache) > self.max_size:
                    self._cleanup_old_entries()
                    
                return icon
            except Exception as e:
                print(f"Failed to load icon {key}: {e}")
                # Return empty transparent image as fallback
                return ImageTk.PhotoImage(Image.new('RGBA', (24, 24), (0, 0, 0, 0)))
    
    def _cleanup_old_entries(self):
        """Remove least recently used entries"""
        if len(self.cache) <= self.max_size * 0.8:
            return
            
        # Sort by access time and remove oldest
        sorted_items = sorted(self.access_times.items(), key=lambda x: x[1])
        to_remove = len(sorted_items) - int(self.max_size * 0.7)
        
        for key, _ in sorted_items[:to_remove]:
            self.cache.pop(key, None)
            self.access_times.pop(key, None)
            
        # Force garbage collection
        gc.collect()
    
    def clear(self):
        """Clear all cached icons"""
        with self._lock:
            self.cache.clear()
            self.access_times.clear()
            gc.collect()

# Global icon cache instance
_icon_cache = IconCache()

class PerformanceAnimator:
    """High-performance animator with easing functions and frame skipping"""
    
    EASING_FUNCTIONS = {
        'linear': lambda t: t,
        'ease_in_quad': lambda t: t * t,
        'ease_out_quad': lambda t: 1 - (1 - t) ** 2,
        'ease_in_out_quad': lambda t: 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t,
        'ease_in_cubic': lambda t: t * t * t,
        'ease_out_cubic': lambda t: 1 + (t - 1) ** 3,
        'ease_in_out_cubic': lambda t: 4 * t * t * t if t < 0.5 else 1 + (t - 1) * (2 * t - 2) ** 2,
        'ease_out_bounce': lambda t: 1 - abs(math.cos(t * math.pi * 1.5)) * (1 - t)
    }
    
    def __init__(self, duration: float, update_callback: Callable[[float], None], 
                 easing: str = 'ease_out_quad', target_fps: int = 60):
        self.duration = duration
        self.update_callback = update_callback
        self.easing_func = self.EASING_FUNCTIONS.get(easing, self.EASING_FUNCTIONS['ease_out_quad'])
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        
        self.start_time = 0
        self.animation_id = None
        self.widget = None
        self.is_running = False
        self.last_frame_time = 0
        
    def start(self, widget: tk.Widget):
        """Start animation with performance monitoring"""
        if self.animation_id and widget:
            try:
                widget.after_cancel(self.animation_id)
            except:
                pass
                
        self.widget = widget
        self.start_time = time.perf_counter()
        self.last_frame_time = self.start_time
        self.is_running = True
        self._run_frame()
        
    def _run_frame(self):
        """Run single animation frame with adaptive timing"""
        if not self.is_running or not self.widget:
            return
            
        current_time = time.perf_counter()
        elapsed = current_time - self.start_time
        progress = min(elapsed / self.duration, 1.0)
        
        # Apply easing
        eased_progress = self.easing_func(progress)
        
        # Update callback
        try:
            self.update_callback(eased_progress)
        except Exception as e:
            print(f"Animation callback error: {e}")
            self.stop()
            return
            
        # Continue or finish
        if progress < 1.0:
            # Adaptive frame timing based on actual performance
            frame_duration = current_time - self.last_frame_time
            if frame_duration < self.frame_time * 0.8:
                delay = max(1, int((self.frame_time - frame_duration) * 1000))
            else:
                delay = 1  # Skip frame timing if we're behind
                
            self.last_frame_time = current_time
            try:
                self.animation_id = self.widget.after(delay, self._run_frame)
            except:
                self.stop()
        else:
            self.stop()
            
    def stop(self):
        """Stop animation"""
        self.is_running = False
        if self.animation_id and self.widget:
            try:
                self.widget.after_cancel(self.animation_id)
            except:
                pass
        self.animation_id = None

def load_icon_optimized(icon_name: str, theme_name: str, size: Tuple[int, int] = (24, 24)) -> ImageTk.PhotoImage:
    """
    Optimized icon loading with caching and error handling
    """
    cache_key = f"{icon_name}_{theme_name}_{size[0]}x{size[1]}"
    
    def loader():
        icon_path = os.path.join(BASE_DIR, "icons", theme_name.lower(), f"{icon_name}.png")
        
        if not os.path.exists(icon_path):
            print(f"Icon not found: {icon_path}")
            return ImageTk.PhotoImage(Image.new('RGBA', size, (0, 0, 0, 0)))
        
        try:
            # Load and process image
            with Image.open(icon_path) as img:
                img = img.convert("RGBA")
                
                # High-quality resize if needed
                if img.size != size:
                    img = img.resize(size, Image.Resampling.LANCZOS)
                
                return ImageTk.PhotoImage(img)
                
        except Exception as e:
            print(f"Failed to load icon {icon_name}: {e}")
            return ImageTk.PhotoImage(Image.new('RGBA', size, (0, 0, 0, 0)))
    
    return _icon_cache.get(cache_key, loader)

# Backward compatibility
load_icon = load_icon_optimized

class EnhancedTooltip:
    """Enhanced tooltip with animations and better positioning"""
    
    def __init__(self, widget: tk.Widget, text: str, delay: int = 500, 
                 fade_duration: float = 0.2):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.fade_duration = fade_duration
        
        self.tooltip_window = None
        self.show_timer = None
        self.fade_animator = None
        
        # Bind events
        self.widget.bind("<Enter>", self._on_enter)
        self.widget.bind("<Leave>", self._on_leave)
        self.widget.bind("<Motion>", self._on_motion)
        
    def _on_enter(self, event=None):
        """Start show timer"""
        self._cancel_show_timer()
        self.show_timer = self.widget.after(self.delay, self._show_tooltip)
        
    def _on_leave(self, event=None):
        """Hide tooltip"""
        self._cancel_show_timer()
        self._hide_tooltip()
        
    def _on_motion(self, event=None):
        """Update position on mouse move"""
        if self.tooltip_window and self.tooltip_window.winfo_exists():
            self._update_position()
            
    def _cancel_show_timer(self):
        """Cancel pending show timer"""
        if self.show_timer:
            self.widget.after_cancel(self.show_timer)
            self.show_timer = None
            
    def _show_tooltip(self):
        """Show tooltip with fade-in animation"""
        if self.tooltip_window:
            return
            
        # Create tooltip window
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.attributes("-alpha", 0.0)
        
        # Create content
        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            justify='left',
            background="#2D2D2D",
            foreground="#E0E0E0",
            relief='solid',
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=8,
            pady=6
        )
        label.pack()
        
        # Position tooltip
        self._update_position()
        
        # Fade in
        self.fade_animator = PerformanceAnimator(
            duration=self.fade_duration,
            update_callback=self._fade_in_update,
            easing='ease_out_quad'
        )
        self.fade_animator.start(self.widget)
        
    def _fade_in_update(self, progress: float):
        """Update fade-in animation"""
        if self.tooltip_window and self.tooltip_window.winfo_exists():
            self.tooltip_window.attributes("-alpha", progress * 0.95)
            
    def _hide_tooltip(self):
        """Hide tooltip with fade-out animation"""
        if not self.tooltip_window:
            return
            
        if self.fade_animator:
            self.fade_animator.stop()
            
        self.fade_animator = PerformanceAnimator(
            duration=self.fade_duration * 0.5,  # Faster fade out
            update_callback=self._fade_out_update,
            easing='ease_in_quad'
        )
        self.fade_animator.start(self.widget)
        
    def _fade_out_update(self, progress: float):
        """Update fade-out animation"""
        if self.tooltip_window and self.tooltip_window.winfo_exists():
            alpha = (1.0 - progress) * 0.95
            self.tooltip_window.attributes("-alpha", alpha)
            
            if progress >= 1.0:
                self._destroy_tooltip()
                
    def _destroy_tooltip(self):
        """Destroy tooltip window"""
        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except:
                pass
        self.tooltip_window = None
        
    def _update_position(self):
        """Update tooltip position relative to widget"""
        if not self.tooltip_window:
            return
            
        try:
            # Get widget position
            x = self.widget.winfo_rootx() + 10
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
            
            # Get screen dimensions
            screen_width = self.widget.winfo_screenwidth()
            screen_height = self.widget.winfo_screenheight()
            
            # Get tooltip dimensions
            self.tooltip_window.update_idletasks()
            tooltip_width = self.tooltip_window.winfo_reqwidth()
            tooltip_height = self.tooltip_window.winfo_reqheight()
            
            # Adjust position to keep tooltip on screen
            if x + tooltip_width > screen_width:
                x = self.widget.winfo_rootx() - tooltip_width - 10
                
            if y + tooltip_height > screen_height:
                y = self.widget.winfo_rooty() - tooltip_height - 5
                
            self.tooltip_window.wm_geometry(f"+{x}+{y}")
            
        except Exception as e:
            print(f"Tooltip positioning error: {e}")

# Backward compatibility
Tooltip = EnhancedTooltip

class MemoryManager:
    """Memory management utilities for large image operations"""
    
    @staticmethod
    def cleanup_thumbnails(thumbnail_cache: Dict[str, Any], max_size: int = 50):
        """Clean up thumbnail cache when it gets too large"""
        if len(thumbnail_cache) <= max_size:
            return
            
        # Remove oldest entries (assuming dict maintains insertion order)
        items_to_remove = len(thumbnail_cache) - max_size
        keys_to_remove = list(thumbnail_cache.keys())[:items_to_remove]
        
        for key in keys_to_remove:
            thumbnail_cache.pop(key, None)
            
        # Force garbage collection
        gc.collect()
        
    @staticmethod
    def optimize_image_for_display(image: Image.Image, max_size: Tuple[int, int] = (800, 600)) -> Image.Image:
        """Optimize image for display while maintaining quality"""
        if image.width <= max_size[0] and image.height <= max_size[1]:
            return image
            
        # Calculate optimal size maintaining aspect ratio
        ratio = min(max_size[0] / image.width, max_size[1] / image.height)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        
        # Use high-quality resampling
        return image.resize(new_size, Image.Resampling.LANCZOS)
        
    @staticmethod
    def create_thumbnail_safe(image_path: str, size: Tuple[int, int] = (40, 40)) -> Optional[ImageTk.PhotoImage]:
        """Safely create thumbnail with error handling"""
        try:
            with Image.open(image_path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Thumbnail creation failed for {image_path}: {e}")
            return None

class ErrorHandler:
    """Centralized error handling and logging"""
    
    @staticmethod
    def handle_ui_error(error: Exception, context: str = "", show_user: bool = False):
        """Handle UI-related errors gracefully"""
        error_msg = f"UI Error in {context}: {error}"
        print(error_msg)
        
        if show_user:
            try:
                import tkinter.messagebox as mb
                mb.showerror("Error", f"An error occurred: {error}")
            except:
                pass
                
    @staticmethod
    def safe_execute(func: Callable, *args, context: str = "", **kwargs) -> Any:
        """Safely execute function with error handling"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            ErrorHandler.handle_ui_error(e, context)
            return None

def debounce(wait_ms: int):
    """Debounce decorator for UI callbacks"""
    def decorator(func):
        timer = None
        
        @functools.wraps(func)
        def debounced(self, *args, **kwargs):
            nonlocal timer
            
            def call_func():
                nonlocal timer
                timer = None
                func(self, *args, **kwargs)
                
            if timer is not None:
                self.master.after_cancel(timer) if hasattr(self, 'master') else None
                
            widget = getattr(self, 'master', None) or getattr(self, 'widget', None)
            if widget:
                timer = widget.after(wait_ms, call_func)
                
        return debounced
    return decorator

# Legacy Animator class for backward compatibility
class Animator(PerformanceAnimator):
    """Legacy animator class - redirects to PerformanceAnimator"""
    def __init__(self, duration, update_callback, easing_func=None):
        easing = 'ease_out_quad'  # Default easing
        if easing_func:
            # Try to match legacy easing function
            easing = 'linear' if easing_func.__name__ == 'linear' else 'ease_out_quad'
            
        super().__init__(duration, update_callback, easing)