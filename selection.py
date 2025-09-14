# selection.py (Версия с "Классическим" поведением и горячими клавишами)
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageGrab, ImageDraw
import logging
import sys
from enum import Enum, auto
from typing import Callable, Optional, Tuple, Dict, Any

from enums import SelectionAction
from helpers import Tooltip, Animator 

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDpiAwarenessContext(-4)
    except (AttributeError, TypeError):
        logging.warning("Could not set DPI awareness.")
else:
    user32 = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class State(Enum):
    INACTIVE = auto()
    SELECTING = auto()

class MagnifierLens:
    def __init__(self, screenshot: Image.Image):
        self.screenshot = screenshot
        self.is_visible = False
        self._zoom = 4; self._size = 140; self._border_size = 3
        self._crosshair_size = 10; self._offset_from_cursor = 25
        self._window: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None
        self._photo: Optional[ImageTk.PhotoImage] = None

    def _create_window(self, master: tk.Widget):
        self._window = tk.Toplevel(master)
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True); self._window.attributes("-alpha", 0.95)
        self._canvas = tk.Canvas(self._window, width=self._size, height=self._size, highlightthickness=0)
        self._canvas.pack()

    def update(self, master: tk.Widget, x: int, y: int):
        if not self.is_visible: return
        if not self._window or not self._window.winfo_exists(): self._create_window(master)
        pos_x, pos_y = x + self._offset_from_cursor, y + self._offset_from_cursor
        if pos_x + self._size > master.winfo_screenwidth(): pos_x = x - self._size - self._offset_from_cursor
        if pos_y + self._size > master.winfo_screenheight(): pos_y = y - self._size - self._offset_from_cursor
        self._window.geometry(f"{self._size}x{self._size}+{pos_x}+{pos_y}")
        self._render(x, y)

    def _render(self, center_x: int, center_y: int):
        try:
            radius = (self._size // self._zoom) // 2
            box = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)
            source = self.screenshot.crop(box)
            magnified = source.resize((self._size, self._size), Image.Resampling.NEAREST)
            draw = ImageDraw.Draw(magnified)
            center = self._size // 2
            draw.line((center, center - self._crosshair_size, center, center + self._crosshair_size), fill="red")
            draw.line((center - self._crosshair_size, center, center + self._crosshair_size, center), fill="red")
            self._photo = ImageTk.PhotoImage(magnified)
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, image=self._photo, anchor="nw")
        except Exception: pass

    def show(self): self.is_visible = True
    def hide(self):
        if self.is_visible:
            self.is_visible = False
            if self._window and self._window.winfo_exists(): self._window.withdraw()

    def cleanup(self):
        self.is_visible = False
        if self._window:
            try: self._window.destroy()
            except tk.TclError: pass
        self._window = self._canvas = self._photo = None

class SimpleSelection:
    def __init__(self, app):
        self._app = app
        self._on_complete = self._app.process_selected_area
        self._settings = self._app.settings_manager.settings
        self._state = State.INACTIVE
        self._root: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None
        self._screenshot: Optional[Image.Image] = None
        self._magnifier: Optional[MagnifierLens] = None
        self._start_pos = (0, 0); self._selection_bbox = [0, 0, 0, 0]

    def start_selection(self):
        if self._state != State.INACTIVE: return
        delay = 150 if self._settings.get("hide_on_screenshot") else 1
        self._app.master.withdraw()
        self._app.master.after(delay, lambda: self._capture_and_show(self._app.master))

    def _capture_and_show(self, master: tk.Widget):
        try:
            self._screenshot = ImageGrab.grab(all_screens=True)
            self._magnifier = MagnifierLens(self._screenshot)
            self._setup_ui(master)
            self._magnifier.show()
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}", exc_info=True)
            messagebox.showerror("Capture Error", f"Could not capture screen: {e}")
            self._cleanup(); master.deiconify()

    def _setup_ui(self, master: tk.Widget):
        self._root = tk.Toplevel(master)
        self._root.attributes("-fullscreen", True); self._root.attributes("-topmost", True)
        self._root.wait_visibility()
        self._canvas = tk.Canvas(self._root, cursor="cross", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        overlay = Image.new('RGBA', self._screenshot.size, (0, 0, 0, 120))
        bg_image = Image.alpha_composite(self._screenshot.convert('RGBA'), overlay)
        self._bg_photo = ImageTk.PhotoImage(bg_image)
        self._canvas.create_image(0, 0, image=self._bg_photo, anchor="nw")
        self._bind_events(); self._root.focus_force()

    def _bind_events(self):
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<Motion>", self._on_mouse_move)
        self._root.bind("<Escape>", lambda e: self._finalize(None, SelectionAction.CANCEL))

    def _on_mouse_move(self, event):
        if self._state == State.INACTIVE:
            self._magnifier.update(self._root, event.x, event.y)

    def _on_press(self, event):
        self._state = State.SELECTING
        self._start_pos = (event.x, event.y)
        self._selection_bbox = [event.x, event.y, event.x, event.y]
        self._magnifier.hide()

    def _on_drag(self, event):
        if self._state != State.SELECTING: return
        self._selection_bbox = [self._start_pos[0], self._start_pos[1], event.x, event.y]
        self._draw_selection_box()
    
    def _on_release(self, event):
        if self._state != State.SELECTING: return
        x1, y1, x2, y2 = self._selection_bbox
        self._selection_bbox = [min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2)]
        width = self._selection_bbox[2] - self._selection_bbox[0]
        height = self._selection_bbox[3] - self._selection_bbox[1]
        if width < 10 or height < 10:
            return self._finalize(None, SelectionAction.CANCEL)
        self._show_action_panel()

    def _draw_selection_box(self):
        self._canvas.delete("selection_elements")
        x1, y1, x2, y2 = map(int, self._selection_bbox)
        norm_x1, norm_y1, norm_x2, norm_y2 = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        self._canvas.create_rectangle(norm_x1, norm_y1, norm_x2, norm_y2, 
                                     outline="#00AAFF", width=1, dash=(4,2), tags="selection_elements")
        width, height = norm_x2 - norm_x1, norm_y2 - norm_y1
        dim_text = f"{width} × {height}"
        text_y = norm_y1 - 20 if norm_y1 > 20 else norm_y2 + 5
        text_bg = self._canvas.create_rectangle(norm_x1, text_y - 2, norm_x1 + len(dim_text)*7 + 10, text_y + 18, 
                                     fill="black", outline="", tags="selection_elements")
        text_id = self._canvas.create_text(norm_x1 + 5, text_y + 8, text=dim_text, fill="white", 
                                anchor="w", font=("Segoe UI", 9), tags="selection_elements")
            
    def _show_action_panel(self):
        self._canvas.delete("selection_elements")
        x1, y1, x2, y2 = map(int, self._selection_bbox)
        if x2-x1 > 0 and y2-y1 > 0:
            highlight_crop = self._screenshot.crop((x1, y1, x2, y2))
            self._highlight_photo = ImageTk.PhotoImage(highlight_crop)
            self._canvas.create_image(x1, y1, image=self._highlight_photo, anchor="nw")
        self._canvas.create_rectangle(x1, y1, x2, y2, outline="#00AAFF", width=1)
        
        self._magnifier.hide()
        self._canvas.unbind("<Motion>"); self._canvas.unbind("<ButtonPress-1>")
        self._canvas.unbind("<B1-Motion>"); self._canvas.unbind("<ButtonRelease-1>")
        self._canvas.config(cursor="")
        
        panel = tk.Frame(self._canvas, bg="#2D2D2D", highlightbackground="#555", highlightthickness=1)
        
        # --- НОВОЕ: Карта действий с подсказками о горячих клавишах ---
        actions_map = [
            (SelectionAction.SAVE, "✓ Сохранить (Ctrl+S)"),
            (SelectionAction.COPY, "📋 Копировать (Ctrl+C)"),
            (SelectionAction.UPLOAD, "☁️ Загрузить"),
            (SelectionAction.SCAN_QR, "🔍 QR Скан (Ctrl+Q)"),
            (SelectionAction.CANCEL, "❌ Отмена (Ctrl+Z)")
        ]

        for action, text in actions_map:
            if action == SelectionAction.UPLOAD and not self._settings.get("enable_catbox_upload"): continue
            btn = tk.Button(panel, text=text, bg="#3C3C3C", fg="white", activebackground="#007ACC",
                            activeforeground="white", relief="flat", font=("Segoe UI", 9),
                            padx=10, pady=5, command=lambda a=action: self._finalize(self._selection_bbox, a))
            btn.pack(side="left", padx=4, pady=4)

        panel.update_idletasks()
        panel_y = y2 + 8
        if panel_y + panel.winfo_height() > self._root.winfo_height(): panel_y = y1 - panel.winfo_height() - 8
        self._canvas.create_window(x1, panel_y, window=panel, anchor="nw")
        
        # --- НОВОЕ: Привязка горячих клавиш ---
        self._bind_action_hotkeys()

    # --- НОВОЕ: Метод для привязки горячих клавиш ---
    def _bind_action_hotkeys(self):
        """Binds hotkeys that are active only when the action panel is visible."""
        self._root.bind("<Control-s>", lambda e: self._finalize(self._selection_bbox, SelectionAction.SAVE))
        self._root.bind("<Control-c>", lambda e: self._finalize(self._selection_bbox, SelectionAction.COPY))
        self._root.bind("<Control-q>", lambda e: self._finalize(self._selection_bbox, SelectionAction.SCAN_QR))
        self._root.bind("<Control-z>", lambda e: self._finalize(None, SelectionAction.CANCEL))

    def _finalize(self, bbox: Optional[list], action: SelectionAction):
        image_to_process = None
        if bbox and action != SelectionAction.CANCEL:
            safe_bbox = ( max(0, int(bbox[0])), max(0, int(bbox[1])),
                          min(self._screenshot.width, int(bbox[2])), min(self._screenshot.height, int(bbox[3])) )
            if safe_bbox[2] > safe_bbox[0] and safe_bbox[3] > safe_bbox[1]:
                image_to_process = self._screenshot.crop(safe_bbox)
        
        action_str = action.name.lower()
        callback, image, act = self._on_complete, image_to_process, action_str
        self._cleanup()
        callback(image, act)
        
    def _cleanup(self):
        if self._state == State.INACTIVE: return
        self._state = State.INACTIVE

        # --- НОВОЕ: Отвязка горячих клавиш перед закрытием окна ---
        if self._root and self._root.winfo_exists():
            self._root.unbind("<Control-s>")
            self._root.unbind("<Control-c>")
            self._root.unbind("<Control-q>")
            self._root.unbind("<Control-z>")
        
        if self._magnifier: self._magnifier.cleanup()
        if self._root:
            try: self._root.destroy()
            except tk.TclError: pass
        self._root = self._canvas = self._screenshot = self._magnifier = None
        logger.info("Selection UI cleaned up.")