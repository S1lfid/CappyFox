# helpers.py
import tkinter as tk
from PIL import Image, ImageTk
import os
import time
import math

# --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ ---
# Создаем абсолютный путь к папке, где лежит этот скрипт (helpers.py)
# Это гарантирует, что папка icons будет найдена, откуда бы мы ни запускали main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# NEW: A simple, reusable animation engine for smooth UI transitions.
class Animator:
    def __init__(self, duration, update_callback, easing_func=None):
        self.duration = duration
        self.update_callback = update_callback
        self.easing_func = easing_func or self._ease_out_quad
        self.start_time = 0
        self.animation_id = None
        self.widget = None # A widget to use for the 'after' method

    def _ease_out_quad(self, t):
        """A simple easing function for a smooth slow-down effect."""
        return 1 - (1 - t) ** 2

    def start(self, widget):
        """Starts the animation, using the provided widget for the mainloop context."""
        if self.animation_id:
            widget.after_cancel(self.animation_id)
            
        self.widget = widget
        self.start_time = time.time()
        self._run()

    def _run(self):
        elapsed = time.time() - self.start_time
        progress = min(elapsed / self.duration, 1.0)
        
        # Apply the easing function to the progress
        eased_progress = self.easing_func(progress)

        # Call the user-provided function with the eased progress
        self.update_callback(eased_progress)

        if progress < 1.0:
            self.animation_id = self.widget.after(10, self._run) # Aim for ~100 FPS
        else:
            self.update_callback(1.0) # Ensure it finishes at the exact final state
            self.animation_id = None

def load_icon(icon_name, theme_name, size=(24, 24)):
    """
    Загружает иконку из папки, соответствующей теме, и изменяет её размер.
    Использует абсолютный путь для надежности.
    """
    icon_path = os.path.join(BASE_DIR, "icons", theme_name.lower(), f"{icon_name}.png")

    if not os.path.exists(icon_path):
        print(f"Иконка не найдена: {icon_path}")
        return ImageTk.PhotoImage(Image.new('RGBA', size, (0, 0, 0, 0)))

    try:
        img = Image.open(icon_path).convert("RGBA")
        img = img.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"Не удалось загрузить иконку {icon_name}: {e}")
        return ImageTk.PhotoImage(Image.new('RGBA', size, (0, 0, 0, 0)))

class Tooltip:
    """
    Создает всплывающую подсказку для виджета. (без изменений)
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=self.text, justify='left',
                      background="#333333", foreground="white", relief='solid', borderwidth=1,
                      font=("Arial", "9", "normal"), padx=8, pady=4)
        label.pack(ipadx=1)

    def leave(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None