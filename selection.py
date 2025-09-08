# selection.py
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageGrab, ImageDraw

class SimpleSelection:
    def __init__(self, master_app):
        self.app = master_app
        self.callback = master_app.process_selected_area
        self.root = None
        self.canvas = None
        self.start_pos = None
        self.screenshot_base = None

    def start_selection(self):
        delay = 150 if self.app.settings_manager.settings["hide_on_screenshot"] else 1
        if delay > 1:
            self.app.master.withdraw()
        self.app.master.after(delay, self._grab_screen)

    def _grab_screen(self):
        try:
            self.root = tk.Toplevel(self.app.master)
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True)
            self.root.wait_visibility()

            self.canvas = tk.Canvas(self.root, cursor="cross", highlightthickness=0)
            self.canvas.pack(fill="both", expand=True)

            self.screenshot_base = ImageGrab.grab(all_screens=True)
            self.image_tk = ImageTk.PhotoImage(self.screenshot_base)
            self.canvas.create_image(0, 0, image=self.image_tk, anchor="nw")
            
            self.overlay_id = self.canvas.create_rectangle(0, 0, self.screenshot_base.width, self.screenshot_base.height, fill='black', stipple='gray50', outline="")
        
            # --- НОВАЯ СТРОКА ---
            # Привязываем клавишу Escape к функции отмены
            self.root.bind("<Escape>", self.cancel_selection)
            # --- КОНЕЦ НОВОЙ СТРОКИ ---
            
            self.canvas.bind("<ButtonPress-1>", self.on_press)
            self.canvas.bind("<B1-Motion>", self.on_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_release)

        except Exception as e:
            print(f"Не удалось захватить экран: {e}")
            self.cleanup()
            messagebox.showerror("Ошибка захвата", "Не удалось сделать снимок экрана.\nУбедитесь, что нет других программ, блокирующих экран.")
            if self.app:
                self.app.show_window()


    def on_press(self, event):
        self.start_pos = (event.x, event.y)
        self.rect_inner = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="white", width=1, dash=(6, 4))
        self.dim_bg = self.canvas.create_rectangle(0, 0, 0, 0, fill="black", outline="")
        self.dim_text = self.canvas.create_text(0, 0, text="", fill="white", anchor="nw", font=("Arial", 10))

    def on_drag(self, event):
        if not self.start_pos: return
        x1, y1 = self.start_pos
        x2, y2 = event.x, event.y
        self.canvas.coords(self.rect_inner, min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        
        width = abs(x2 - x1); height = abs(y2 - y1); dim_string = f"{width}x{height}"
        text_x, text_y = min(x1, x2) + 5, min(y1, y2) + 5
        self.canvas.coords(self.dim_text, text_x, text_y)
        self.canvas.itemconfigure(self.dim_text, text=dim_string)
        
        bbox = self.canvas.bbox(self.dim_text)
        if bbox:
            self.canvas.coords(self.dim_bg, bbox[0]-3, bbox[1]-3, bbox[2]+3, bbox[3]+3)

    def on_release(self, event):
        if not self.start_pos: 
            self.cleanup(); return
            
        x1 = min(self.start_pos[0], event.x); y1 = min(self.start_pos[1], event.y)
        x2 = max(self.start_pos[0], event.x); y2 = max(self.start_pos[1], event.y)
        
        self.canvas.delete(self.rect_inner, self.dim_bg, self.dim_text)
        
        if x2 - x1 > 5 and y2 - y1 > 5:
            self.show_action_panel((x1, y1, x2, y2))
        else:
            self.cancel_selection()

    def show_action_panel(self, bbox):
        self.canvas.unbind("<ButtonPress-1>"); self.canvas.unbind("<B1-Motion>"); self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.config(cursor="")

        self.canvas.delete(self.overlay_id)
        w, h = self.screenshot_base.width, self.screenshot_base.height
        self.canvas.create_rectangle(0, 0, w, bbox[1], fill='black', stipple='gray50', outline="")
        self.canvas.create_rectangle(0, bbox[3], w, h, fill='black', stipple='gray50', outline="")
        self.canvas.create_rectangle(0, bbox[1], bbox[0], bbox[3], fill='black', stipple='gray50', outline="")
        self.canvas.create_rectangle(bbox[2], bbox[1], w, bbox[3], fill='black', stipple='gray50', outline="")

        panel = tk.Frame(self.root, bg="#2D2D2D", bd=1, relief="solid")
        
        action_btns = {"✓ Сохранить": ("#28a745", "save"), "📋 Копировать": ("#007ACC", "copy")}
        if self.app.settings_manager.settings.get("enable_catbox_upload", True):
             action_btns["☁️ Загрузить"] = ("#8e44ad", "upload")
        action_btns.update({"🔍 QR-Скан": ("#5856d6", "scan_qr"), "❌ Отмена": ("#ff3b30", "cancel")})
        for txt, (bg_color, action) in action_btns.items():
            btn = tk.Button(
                panel, text=txt, bg=bg_color, fg="white", 
                activebackground=bg_color, activeforeground="white",
                relief="flat", font=("Arial", 9, "bold"), 
                command=lambda a=action: self.finalize(bbox, a), padx=10, pady=4
            )
            btn.pack(side="left", padx=3, pady=3)
        
        panel_height = panel.winfo_reqheight()
        y_pos, anchor = (bbox[3] + 5, "nw")
        if y_pos + panel_height > self.root.winfo_screenheight():
            y_pos, anchor = (bbox[1] - 5, "sw")
        self.canvas.create_window(bbox[0], y_pos, window=panel, anchor=anchor)

    def finalize(self, bbox, action):
        image_to_process = None
        if action != "cancel":
            image_to_process = self.screenshot_base.crop(bbox)
        self.callback(image_to_process, action)
        self.cleanup()

    def cancel_selection(self, event=None):
        self.callback(None, "cancel")
        self.cleanup()
        
    def cleanup(self):
        if self.root:
            self.root.destroy()
            self.root = None
            self.screenshot_base = None
            self.image_tk = None