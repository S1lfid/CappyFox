# selection.py
import tkinter as tk
from PIL import Image, ImageTk, ImageGrab, ImageDraw

class SimpleSelection:
    def __init__(self, master_app):
        self.app = master_app
        self.callback = master_app.process_selected_area
        self.root, self.canvas, self.start_pos, self.screenshot_base = None, None, None, None

    def start_selection(self):
        delay = 150 if self.app.settings_manager.settings["hide_on_screenshot"] else 1
        if delay > 1: self.app.master.withdraw()
        self.app.master.after(delay, self._grab_screen)

    def _grab_screen(self):
        self.root = tk.Toplevel(self.app.master)
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.wait_visibility()

        self.canvas = tk.Canvas(self.root, cursor="cross", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.screenshot_base = ImageGrab.grab(all_screens=True)
        self.image_tk = ImageTk.PhotoImage(self.screenshot_base)
        self.canvas.create_image(0, 0, image=self.image_tk, anchor="nw")
        
        # Полупрозрачный оверлей
        self.overlay_id = self.canvas.create_rectangle(0, 0, self.screenshot_base.width, self.screenshot_base.height, fill='black', stipple='gray50', outline="")

        self.root.bind("<Escape>", self.cancel_selection)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def on_press(self, e):
        self.start_pos = (e.x, e.y)
        # --- УЛУЧШЕННЫЙ ДИЗАЙН РАМКИ ---
        self.rect_outer = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="black", width=3)
        self.rect_inner = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="white", width=1)
        # --- ДИСПЛЕЙ РАЗМЕРОВ И ЛУПА ---
        self.dim_bg = self.canvas.create_rectangle(0,0,0,0, fill="black")
        self.dim_text = self.canvas.create_text(0,0, text="", fill="white", anchor="sw")
        self.magnifier_canvas = tk.Canvas(self.canvas, width=100, height=100, borderwidth=1, relief="solid")
        self.magnifier_window_id = self.canvas.create_window(10, 10, window=self.magnifier_canvas, anchor="nw")

    def on_drag(self, e):
        if not self.start_pos: return
        x1, y1 = self.start_pos
        x2, y2 = e.x, e.y

        # Обновляем рамку
        self.canvas.coords(self.rect_outer, x1, y1, x2, y2)
        self.canvas.coords(self.rect_inner, x1, y1, x2, y2)
        
        # Обновляем дисплей размеров
        width = abs(x2 - x1); height = abs(y2 - y1)
        dim_string = f"{width} x {height}"
        text_x, text_y = min(x1, x2), min(y1, y2) - 5
        self.canvas.coords(self.dim_text, text_x, text_y)
        self.canvas.itemconfigure(self.dim_text, text=dim_string)
        bbox = self.canvas.bbox(self.dim_text)
        if bbox:
            self.canvas.coords(self.dim_bg, bbox[0]-2, bbox[1]-2, bbox[2]+2, bbox[3]+2)
        
        # Обновляем лупу
        self._update_magnifier(e.x, e.y)

    def on_release(self, e):
        if not self.start_pos: return
        x1 = min(self.start_pos[0], e.x)
        y1 = min(self.start_pos[1], e.y)
        x2 = max(self.start_pos[0], e.x)
        y2 = max(self.start_pos[1], e.y)
        
        self.canvas.delete(self.rect_outer, self.rect_inner, self.dim_bg, self.dim_text)
        self.canvas.delete(self.magnifier_window_id)

        if x2 - x1 > 10 and y2 - y1 > 10:
            self.show_action_panel((x1, y1, x2, y2))
        else:
            self.cancel_selection()

    def _update_magnifier(self, x, y):
        try:
            box = (x - 7, y - 7, x + 8, y + 8)
            grab_region = self.screenshot_base.crop(box)
            zoomed = grab_region.resize((100, 100), Image.NEAREST)
            draw = ImageDraw.Draw(zoomed)
            draw.line((50, 0, 50, 100), fill="red", width=1)
            draw.line((0, 50, 100, 50), fill="red", width=1)
            self.magnifier_image = ImageTk.PhotoImage(zoomed)
            self.magnifier_canvas.create_image(0, 0, image=self.magnifier_image, anchor="nw")
        except:
            pass # Игнорируем ошибки, если курсор у края экрана

    def show_action_panel(self, bbox):
        self.canvas.unbind("<ButtonPress-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.config(cursor="")
        
        self.canvas.create_rectangle(bbox, outline="white", width=1)
        # Очищаем оверлей ПОЛНОСТЬЮ, так как мы "под ним" рисуем копию выделенной области
        self.canvas.coords(self.overlay_id, 0,0,0,0)
        
        # Вместо создания "дырки" просто рисуем яркую область поверх темной
        bright_crop = self.screenshot_base.crop(bbox)
        self.tk_bright_crop = ImageTk.PhotoImage(bright_crop)
        self.canvas.create_image(bbox[0], bbox[1], image=self.tk_bright_crop, anchor="nw")

        panel = tk.Frame(self.root, bg="#2D2D2D", bd=1, relief="solid")
        action_btns = {
            "✓ Сохранить": ("green", "save"),
            "📋 Копировать": ("#007ACC", "copy"),
            "🔍 QR-Скан": ("#5856d6", "scan_qr"),
            "❌ Отмена": ("#ff3b30", "cancel")
        }
        for txt, (bg, action) in action_btns.items():
            btn = tk.Button(panel, text=txt, bg=bg, fg="white", relief="flat", font=("Arial",9), command=lambda a=action: self.finalize(bbox, a))
            btn.pack(side="left", padx=2, pady=2)
            
        y_pos = bbox[3] + 5
        if y_pos + 40 > self.root.winfo_screenheight():
            y_pos = bbox[1] - 35
        self.canvas.create_window(bbox[2], y_pos, window=panel, anchor="se")

    def finalize(self, bbox, action):
        self.callback(self.screenshot_base.crop(bbox) if action != "cancel" else None, action)
        self.cleanup()

    def cancel_selection(self, event=None):
        self.callback(None, "cancel")
        self.cleanup()
        
    def cleanup(self):
        if self.root:
            self.root.destroy()
            self.root = None