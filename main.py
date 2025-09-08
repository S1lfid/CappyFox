# main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageGrab
import os
import datetime
import sys
import shutil
import threading
import io
import json

try:
    import requests
except ImportError:
    messagebox.showerror("Отсутствует зависимость", "Библиотека 'requests' не найдена.")
    sys.exit(1)

from constants import APP_NAME, THEMES
from settings_manager import SettingsManager
from selection import SimpleSelection
from helpers import load_icon, Tooltip

from pystray import Icon as PyTrayIcon, MenuItem as PyTrayMenuItem
import keyboard
from pyzbar.pyzbar import decode as qr_decode

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import win32clipboard

class ScreenshotApp:
    def __init__(self, master):
        self.master = master; master.app = self
        self.settings_manager = SettingsManager(self)
        self.theme_name = self.settings_manager.settings["theme"]
        self.icons = {}; self._load_all_icons()
        
        self.master.title(APP_NAME); self.master.geometry("1000x700")
        self.master.minsize(600, 400)
        if "app_icon_tk" in self.icons: self.master.iconphoto(True, self.icons.get("app_icon_tk"))
        self.master.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.screenshot_dir = self.settings_manager.settings["save_directory"]
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        # --- ВОССТАНОВЛЕНО: Путь к файлу истории ---
        self.history_file = "history.json"

        self.tray_icon = None; self.full_screen_hotkey = None; self.area_hotkey = None
        self.current_image = None; self.current_image_path = None
        self.thumbnail_cache = {}
        
        self.selection_rectangle = None; self.drag_start_pos = None
        
        self.selection_tool = SimpleSelection(self)
        self._setup_styles(); self.setup_ui()
        self.load_screenshots()
        self._setup_tray_icon(); self.rehook_hotkeys()
        
        if self.settings_manager.settings["start_minimized"]: master.withdraw()

    def _load_all_icons(self):
        theme = self.settings_manager.settings["theme"]; base_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            icon_path = os.path.join(base_dir, "icons", theme.lower(), "app_icon.png")
            pil_img = Image.open(icon_path).convert("RGBA")
            self.icons["app_icon_pil"] = pil_img; self.icons["app_icon_tk"] = ImageTk.PhotoImage(pil_img)
        except Exception:
            pil_img = Image.new('RGB', (64, 64), 'black')
            self.icons["app_icon_pil"] = pil_img; self.icons["app_icon_tk"] = ImageTk.PhotoImage(pil_img)
        
        # --- ВОССТАНОВЛЕНО: Иконка истории ---
        icon_names = ["screenshot-full", "screenshot-area", "settings", "refresh","copy", "delete", "export", "folder-open", "upload-cloud", "history"]
        for name in icon_names: self.icons[name] = load_icon(name, theme)

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')

    def setup_ui(self):
        for widget in self.master.winfo_children(): widget.destroy()
        self.master.columnconfigure(0, weight=1); self.master.rowconfigure(1, weight=1)
        
        self.control_frame = ttk.Frame(self.master); self.control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        btn_full = ttk.Button(self.control_frame, image=self.icons.get("screenshot-full"), text=" Весь экран", compound="left", command=self.take_full_screenshot, style="Cappy.TButton"); btn_full.pack(side="left", padx=2, pady=2); Tooltip(btn_full, f"({self.settings_manager.settings['hotkey_full_screen']})")
        btn_area = ttk.Button(self.control_frame, image=self.icons.get("screenshot-area"), text=" Область", compound="left", command=self.selection_tool.start_selection, style="Cappy.TButton"); btn_area.pack(side="left", padx=2, pady=2); Tooltip(btn_area, f"({self.settings_manager.settings['hotkey_select_area']})")
        
        # --- ВОССТАНОВЛЕНО: Кнопка "История" ---
        btn_refresh = ttk.Button(self.control_frame, image=self.icons.get("refresh"), command=self.load_screenshots, style="Cappy.TButton"); btn_refresh.pack(side="right", padx=2, pady=2); Tooltip(btn_refresh, "Обновить")
        btn_history = ttk.Button(self.control_frame, image=self.icons.get("history"), command=self.open_history_window, style="Cappy.TButton"); btn_history.pack(side="right", padx=(10,2), pady=2); Tooltip(btn_history, "История загрузок")
        btn_settings = ttk.Button(self.control_frame, image=self.icons.get("settings"), command=self.settings_manager.open_settings_window, style="Cappy.TButton"); btn_settings.pack(side="right", padx=(2,2), pady=2); Tooltip(btn_settings, "Настройки")
        
        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL); self.paned_window.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.left_pane = ttk.Frame(self.paned_window); self.paned_window.add(self.left_pane, weight=1)
        self.multi_actions_header = ttk.Frame(self.left_pane, style="Header.TFrame")
        self.selection_label = ttk.Label(self.multi_actions_header, text="Выбрано: 0", style="Header.TLabel"); self.selection_label.pack(side="left", padx=(5,10))
        header_buttons_frame = ttk.Frame(self.multi_actions_header, style="Header.TFrame"); header_buttons_frame.pack(side="right")
        self.btn_multi_export = ttk.Button(header_buttons_frame, text="Экспорт", command=self._export_selected, style="Cappy.TButton"); self.btn_multi_export.pack(side="left", padx=2)
        self.btn_multi_delete = ttk.Button(header_buttons_frame, text="Удалить", command=self._delete_selected, style="Cappy.TButton"); self.btn_multi_delete.pack(side="left", padx=2)
        self.tree_frame = ttk.Frame(self.left_pane); self.tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(self.tree_frame, columns=("filename",), show="tree headings", selectmode='extended')
        self.tree.heading("#0", text="Превью"); self.tree.heading("filename", text="Имя файла")
        self.tree.column("#0", width=70, anchor='center', stretch=False); self.tree.column("filename", width=200)
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview, style='Cappy.Vertical.TScrollbar')
        self.tree.configure(yscrollcommand=scrollbar.set); scrollbar.pack(side="right", fill="y"); self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_screenshot_select)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Control-a>", self._select_all); self.tree.bind("<Control-A>", self._select_all)
        self.tree.bind("<ButtonPress-1>", self._on_mouse_press)
        self.tree.bind("<B1-Motion>", self._on_mouse_drag)
        self.tree.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.right_pane = ttk.Frame(self.paned_window); self.paned_window.add(self.right_pane, weight=3)
        self.right_pane.rowconfigure(0, weight=1); self.right_pane.columnconfigure(0, weight=1)
        self.image_canvas = tk.Canvas(self.right_pane, highlightthickness=0); self.image_canvas.grid(row=0, column=0, sticky="nsew", pady=5); self.image_canvas.bind("<Configure>", self.resize_image_event)
        bottom_panel = ttk.Frame(self.right_pane); bottom_panel.grid(row=1, column=0, sticky="ew", pady=(0,5))
        self.info_label = ttk.Label(bottom_panel, text="Выберите файл", anchor="w"); self.info_label.pack(side="left", padx=5)
        actions_frame = ttk.Frame(bottom_panel); actions_frame.pack(side="right")
        self.btn_upload = ttk.Button(actions_frame, image=self.icons.get("upload-cloud"), command=self._upload_current_image, style="Action.TButton"); self.btn_upload.pack(side="left"); Tooltip(self.btn_upload, "Загрузить на Catbox.moe")
        if not self.settings_manager.settings.get("enable_catbox_upload", False): self.btn_upload.pack_forget()
        btn_copy = ttk.Button(actions_frame, image=self.icons.get("copy"), command=self._copy_current_image, style="Action.TButton"); btn_copy.pack(side="left"); Tooltip(btn_copy, "Копировать")
        btn_open_folder = ttk.Button(actions_frame, image=self.icons.get("folder-open"), command=self._open_current_folder, style="Action.TButton"); btn_open_folder.pack(side="left"); Tooltip(btn_open_folder, "Открыть папку")
        btn_delete_single = ttk.Button(actions_frame, image=self.icons.get("delete"), command=self._delete_current_image, style="Action.TButton"); btn_delete_single.pack(side="left"); Tooltip(btn_delete_single, "Удалить")
        self.apply_theme(self.theme_name)

    # --- ВОССТАНОВЛЕНЫ: Функции для управления историей ---
    def _load_history(self):
        if not os.path.exists(self.history_file): return []
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f: return json.load(f)
        except (json.JSONDecodeError, IOError): return []

    def _save_history(self, history_data):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=4)

    def _add_to_history(self, url):
        history = self._load_history()
        history.append({"url": url, "timestamp": datetime.datetime.now().isoformat()})
        self._save_history(history)
    
    def open_history_window(self):
        hist_win = tk.Toplevel(self.master)
        hist_win.title("История загрузок"); hist_win.geometry("600x400")
        hist_win.transient(self.master); hist_win.grab_set()

        theme_cfg = THEMES[self.theme_name]
        hist_win.config(bg=theme_cfg["bg"])

        main_frame = ttk.Frame(hist_win, style="Settings.TFrame"); main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tv_frame = ttk.Frame(main_frame); tv_frame.pack(fill="both", expand=True, pady=(0, 10))
        tv = ttk.Treeview(tv_frame, columns=("link", "date"), show="headings", selectmode='browse')
        tv.heading("link", text="Ссылка"); tv.heading("date", text="Дата загрузки")
        tv.column("link", width=350); tv.column("date", width=150)
        
        scrollbar = ttk.Scrollbar(tv_frame, orient="vertical", command=tv.yview, style='Cappy.Vertical.TScrollbar')
        tv.configure(yscrollcommand=scrollbar.set); scrollbar.pack(side="right", fill="y"); tv.pack(side="left", fill="both", expand=True)

        for entry in reversed(self._load_history()):
            try:
                date = datetime.datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                tv.insert("", "end", values=(entry['url'], date))
            except (KeyError, TypeError): continue
        
        btn_frame = ttk.Frame(main_frame, style='Settings.TFrame'); btn_frame.pack(fill="x")

        def copy_selected_link():
            if not tv.focus(): messagebox.showwarning("Нет выбора", "Выберите ссылку из списка.", parent=hist_win); return
            self._copy_text_to_clipboard(tv.item(tv.focus())['values'][0]); self.show_toast("Ссылка скопирована!")
        def delete_selected_entry():
            if not tv.focus(): messagebox.showwarning("Нет выбора", "Выберите запись для удаления.", parent=hist_win); return
            if not messagebox.askyesno("Подтверждение", "Удалить запись из истории?", parent=hist_win): return
            url_to_delete = tv.item(tv.focus())['values'][0]
            new_history = [e for e in self._load_history() if e.get("url") != url_to_delete]
            self._save_history(new_history); tv.delete(tv.focus()); self.show_toast("Запись удалена.")
        def clear_all_history():
            if not messagebox.askyesno("Подтверждение", "Очистить ВСЮ историю загрузок? Это действие нельзя отменить.", parent=hist_win): return
            self._save_history([]); tv.delete(*tv.get_children()); self.show_toast("История очищена.")

        ttk.Button(btn_frame, text="Копировать", command=copy_selected_link, style='Cappy.TButton').pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btn_frame, text="Удалить", command=delete_selected_entry, style='Cappy.TButton').pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btn_frame, text="Очистить все", command=clear_all_history, style='Cappy.TButton').pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btn_frame, text="Закрыть", command=hist_win.destroy, style='Cappy.TButton').pack(side="left", expand=True, fill="x", padx=2)
    # --- КОНЕЦ НОВЫХ ФУНКЦИЙ ---

    def on_screenshot_select(self, event):
        selection = self.tree.selection()
        if selection:
            self.multi_actions_header.pack(side="top", fill="x", pady=(0, 5))
            verb_file = "файл" if len(selection)%10==1 and len(selection)%100!=11 else ("файла" if 2<=len(selection)%10<=4 and (len(selection)%100<10 or len(selection)%100>=20) else "файлов")
            self.selection_label.config(text=f"Выбрано: {len(selection)} {verb_file}")
            last_selected_id = selection[-1]; filename = self.tree.item(last_selected_id, 'values')[0]
            filepath = os.path.join(self.screenshot_dir, filename)
            self.current_image_path = filepath
            if not os.path.exists(filepath): self.load_screenshots(); return
            try:
                with Image.open(filepath) as img:
                    self.current_image = img.copy()
                    self.display_image()
                    info = f"{filename} | {self.current_image.width}x{self.current_image.height} | {os.path.getsize(filepath)/1024:.1f} KB"
                    self.info_label.config(text=info)
            except Exception as e:
                self.info_label.config(text=f"Не удалось открыть файл: {e}"); self._clear_preview()
        else:
            self.multi_actions_header.pack_forget()
            self._clear_preview(); self.current_image_path = None
    
    def display_image(self):
        if not self.current_image: return
        canvas_w = self.image_canvas.winfo_width(); canvas_h = self.image_canvas.winfo_height()
        if canvas_w < 10 or canvas_h < 10: self.master.after(50, self.display_image); return
        img_to_show = self.current_image.copy()
        img_to_show.thumbnail((canvas_w, canvas_h), Image.Resampling.LANCZOS)
        self.tk_photo = ImageTk.PhotoImage(img_to_show)
        self.image_canvas.delete("all"); self.image_canvas.create_image(canvas_w / 2, canvas_h / 2, anchor="center", image=self.tk_photo)
    
    def _clear_preview(self):
        self.current_image = None; self.current_image_path = None
        self.image_canvas.delete("all"); self.info_label.config(text="Выберите файл")
        
    def _on_mouse_press(self, event):
        if not self.tree.identify_row(event.y):
            self.drag_start_pos = (event.x, event.y)
            if not (event.state & 0x0004): self.tree.selection_set([])
    
    def _on_mouse_drag(self, event):
        if not self.drag_start_pos: return
        if not self.selection_rectangle:
            self.selection_rectangle = tk.Frame(self.tree_frame, relief='solid', borderwidth=1, background=self.style.lookup("TCombobox", "selectbackground"))
            self.selection_rectangle.lower(self.tree)
        x, y = self.drag_start_pos; ex, ey = event.x, event.y
        self.selection_rectangle.place(x=min(x, ex), y=min(y, ey), width=abs(ex - x), height=abs(ey - y))
        for item in self.tree.get_children():
            bbox = self.tree.bbox(item)
            if not bbox: continue
            if (min(x, ex) < bbox[0] + bbox[2] and max(x, ex) > bbox[0] and min(y, ey) < bbox[1] + bbox[3] and max(y, ey) > bbox[1]):
                self.tree.selection_add(item)
            else:
                 if not (event.state & 0x0004): self.tree.selection_remove(item)

    def _on_mouse_release(self, event):
        if self.selection_rectangle: self.selection_rectangle.destroy(); self.selection_rectangle = None
        self.drag_start_pos = None

    def _select_all(self, event=None):
        self.tree.selection_set(self.tree.get_children()); return "break"
        
    def _show_context_menu(self, event):
        selection = self.tree.selection()
        if not selection: return
        context_menu = tk.Menu(self.master, tearoff=0)
        def get_verb(c): return "файл" if c%10==1 and c%100!=11 else "файла" if 2<=c%10<=4 and (c%100<10 or c%100>=20) else "файлов"
        context_menu.add_command(label=f"Удалить {len(selection)} {get_verb(len(selection))}", command=self._delete_selected)
        context_menu.add_command(label=f"Экспорт {len(selection)} {get_verb(len(selection))}", command=self._export_selected)
        context_menu.post(event.x_root, event.y_root)
        
    def _get_selected_paths(self):
        return [os.path.join(self.screenshot_dir, self.tree.item(i, 'values')[0]) for i in self.tree.selection()]
        
    def _delete_selected(self):
        paths = self._get_selected_paths();
        if not paths: return
        if messagebox.askyesno("Подтверждение", f"Удалить {len(paths)} выбранных файлов?"):
            for p in paths:
                try: os.remove(p)
                except Exception as e: print(f"Failed to delete {p}: {e}")
            self.load_screenshots()

    def _export_selected(self):
        paths = self._get_selected_paths();
        if not paths: return
        d = filedialog.askdirectory(title="Выберите папку");
        if not d: return
        c = sum(1 for p in paths if self._copy_file_safely(p, d))
        self.show_toast(f"Экспортировано {c} файлов.")
        
    def _copy_file_safely(self, src, dst):
        try: shutil.copy(src, dst); return True
        except Exception as e: print(f"Failed to copy {src} to {dst}: {e}"); return False

    def apply_theme(self, theme_name):
        self.theme_name = theme_name; theme = THEMES.get(theme_name, THEMES["Dark"])
        self.master.config(bg=theme["bg"]); s = self.style
        s.configure('.', background=theme["bg"], foreground=theme["fg"], font=("Arial", 10)); s.configure('TFrame', background=theme["bg"])
        s.configure('Cappy.TButton', background=theme["button_bg"], foreground=theme["button_fg"], padding=(10, 5), font=("Arial", 10), borderwidth=0, relief='flat')
        s.map('Cappy.TButton', background=[('active', theme["select_bg"])])
        s.configure('Action.TButton', background=theme["bg"], relief='flat', padding=5); s.map('Action.TButton', background=[('active', theme["control_bg"])])
        s.configure('Header.TFrame', background=theme["control_bg"]); s.configure('Header.TLabel', background=theme["control_bg"], foreground=theme["fg"])
        s.configure("Treeview", background=theme["list_bg"], fieldbackground=theme["list_bg"], foreground=theme["list_fg"], rowheight=45, borderwidth=0)
        s.configure("Treeview.Heading", background=theme["control_bg"], foreground=theme["fg"], font=("Arial", 10, "bold"), padding=5, borderwidth=0)
        s.map("Treeview", background=[('selected', theme["select_bg"])], foreground=[('selected', theme["select_fg"])])
        s.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
        s.configure('TPanedWindow', background=theme["bg"]); s.configure('Cappy.Vertical.TScrollbar', gripcount=0, background=theme["button_bg"], darkcolor=theme["control_bg"], lightcolor=theme["control_bg"], troughcolor=theme["bg"], borderwidth=0, relief='flat', arrowcolor=theme["fg"], arrowsize=14, width=14)
        s.map('Cappy.Vertical.TScrollbar', background=[('active', theme["select_bg"])]); self.image_canvas.config(bg=theme["preview_bg"])

    def load_screenshots(self):
        self.tree.delete(*self.tree.get_children())
        self.thumbnail_cache.clear()
        try:
            paths = sorted([os.path.join(self.screenshot_dir, f) for f in os.listdir(self.screenshot_dir) if f.lower().endswith(('.png','.jpg','.jpeg','.bmp'))], key=os.path.getmtime, reverse=True)
            for p in paths:
                try:
                    with Image.open(p) as img:
                        img.thumbnail((40, 40), Image.Resampling.LANCZOS); thumb = ImageTk.PhotoImage(img)
                        self.thumbnail_cache[p] = thumb; self.tree.insert("", "end", image=thumb, values=(os.path.basename(p),))
                except Exception: pass
        except FileNotFoundError: os.makedirs(self.screenshot_dir, exist_ok=True)
        self._clear_preview(); self.on_screenshot_select(None)
    
    def _upload_current_image(self):
        if self.current_image: self._start_upload_thread(self.current_image)
        else: messagebox.showwarning("Нет выбора", "Сначала выберите скриншот из списка.", parent=self.master)
        
    def _copy_current_image(self):
        if self.current_image: self.copy_image_to_clipboard(self.current_image)
        
    def _delete_current_image(self):
        if not self.current_image_path: messagebox.showwarning("Нет выбора", "Сначала выберите файл.", parent=self.master); return
        if messagebox.askyesno("Удаление", f"Удалить {os.path.basename(self.current_image_path)}?"):
            try: os.remove(self.current_image_path); self.load_screenshots()
            except Exception as e: messagebox.showerror("Ошибка", f"Не удалось удалить: {e}", parent=self.master)
            
    def _open_current_folder(self):
        if self.current_image_path:
            d = os.path.dirname(self.current_image_path)
            if sys.platform=="win32": os.startfile(d)
            else: os.system(f'open "{d}"' if sys.platform=="darwin" else f'xdg-open "{d}"')
            
    def save_screenshot(self, image):
        f = os.path.join(self.screenshot_dir, f"screenshot_{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}.png")
        image.convert("RGB").save(f); self.load_screenshots(); self.show_toast("Скриншот сохранен")
        
    def process_selected_area(self, image, action):
        if not image or action == "cancel":
            if self.settings_manager.settings.get("hide_on_screenshot", True): self.show_window()
            return
        h = {"save": self.save_screenshot, "copy": self.copy_image_to_clipboard, "scan_qr": self.scan_qr_code, "upload": self._start_upload_thread}
        if action in h: h[action](image)
        if self.settings_manager.settings.get("open_window_after_shot", True): self.show_window()
        
    def _start_upload_thread(self, image):
        if image: threading.Thread(target=self._upload_to_catbox, args=(image,), daemon=True).start()
        
    def _upload_to_catbox(self, image):
        self.master.after(0, lambda: self.show_toast("Загрузка..."))
        try:
            with io.BytesIO() as b:
                image.save(b, "PNG"); b.seek(0)
                r=requests.post("https://catbox.moe/user/api.php", data={'reqtype': 'fileupload'}, files={'fileToUpload': ('ss.png', b)}, timeout=20); r.raise_for_status()
                image_url = r.text
                if image_url.startswith("http"):
                    self._copy_text_to_clipboard(image_url)
                    self.master.after(0, lambda: self._add_to_history(image_url))
                    self.master.after(0, lambda: self.show_toast("Ссылка скопирована!"))
                else: raise Exception(f"API Error: {image_url}")
        except Exception as e:
            self.master.after(0, lambda: self.show_toast(f"Ошибка: {e}"))
            
    def _copy_text_to_clipboard(self, text):
        self.master.clipboard_clear(); self.master.clipboard_append(text)
        
    def show_toast(self, message):
        toast = tk.Toplevel(self.master); toast.overrideredirect(True); toast.attributes("-alpha", 0.0)
        toast.geometry(f"+{self.master.winfo_x()+self.master.winfo_width()-350}+{self.master.winfo_y()+self.master.winfo_height()-70}")
        tk.Label(toast, text=message, bg="#111", fg="white", padx=20, pady=10, font=("Arial", 10)).pack()
        self.fade_in(toast); self.master.after(2500, lambda: self.fade_out(toast))
        
    def fade_in(self, widget, alpha=0.0):
        if alpha < 0.9: alpha+=0.08; widget.attributes("-alpha", alpha); self.master.after(15, lambda: self.fade_in(widget, alpha))
        
    def fade_out(self, widget, alpha=0.9):
        if alpha > 0.0: alpha-=0.08; widget.attributes("-alpha", alpha); self.master.after(15, lambda: self.fade_out(widget, alpha))
        else: widget.destroy()
        
    def hide_window(self): self.master.withdraw(); self.show_toast("Приложение свернуто")
    
    def show_window(self): self.master.deiconify(); self.master.lift(); self.master.focus_force()
    
    def on_quit(self, i, item): self.rehook_hotkeys(True); self.tray_icon.stop(); self.master.quit()
        
    def take_full_screenshot(self):
        delay = 150 if self.settings_manager.settings["hide_on_screenshot"] else 1
        if delay > 1: self.master.withdraw()
        self.master.after(delay, self._capture_full)
        
    def _capture_full(self):
        s = ImageGrab.grab(all_screens=True); self.save_screenshot(s)
        if self.settings_manager.settings.get("open_window_after_shot", True): self.show_window()
        
    def rehook_hotkeys(self, unhook_only=False):
        if hasattr(self, 'full_screen_hotkey') and self.full_screen_hotkey:
            try: keyboard.remove_hotkey(self.full_screen_hotkey)
            except Exception: pass
        if hasattr(self, 'area_hotkey') and self.area_hotkey:
            try: keyboard.remove_hotkey(self.area_hotkey)
            except Exception: pass
        if unhook_only: return
        s = self.settings_manager.settings
        try:
            self.full_screen_hotkey = keyboard.add_hotkey(s["hotkey_full_screen"], self.take_full_screenshot)
        except Exception as e: print(f"Не удалось назначить горячую клавишу '{s['hotkey_full_screen']}': {e}")
        try:
            self.area_hotkey = keyboard.add_hotkey(s["hotkey_select_area"], self.selection_tool.start_selection)
        except Exception as e: print(f"Не удалось назначить горячую клавишу '{s['hotkey_select_area']}': {e}")
            
    def resize_image_event(self, e):
        if self.current_image: self.display_image()
        
    def copy_image_to_clipboard(self, image):
        if not IS_WINDOWS: return self.show_toast("Копирование только для Windows")
        output = io.BytesIO(); image.convert("RGB").save(output, "BMP"); data = output.getvalue()[14:]; output.close()
        try:
            win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data); win32clipboard.CloseClipboard()
            self.show_toast("Скопировано в буфер")
        except Exception as e: self.show_toast(f"Ошибка буфера обмена: {e}")
        
    def scan_qr_code(self, image):
        decoded = qr_decode(image)
        if not decoded:
            messagebox.showinfo("QR Сканнер", "QR-код не найден", parent=self.master); return
        result = "\n".join([o.data.decode("utf-8", 'ignore') for o in decoded])
        win = tk.Toplevel(self.master); win.title("Результат сканирования"); win.transient(self.master); win.grab_set()
        tk.Label(win, text="Найденные данные:").pack(padx=10, pady=(10,5))
        text_widget = tk.Text(win, height=5, width=60); text_widget.pack(padx=10); text_widget.insert(tk.END, result)
        def copy_and_close():
            self.master.clipboard_clear(); self.master.clipboard_append(result); win.destroy()
        tk.Button(win, text="Копировать и закрыть", command=copy_and_close).pack(pady=10)
        
    def _setup_tray_icon(self):
        image = self.icons.get("app_icon_pil")
        menu = (PyTrayMenuItem('Показать', self.show_window, default=True), PyTrayMenuItem('Скриншот экрана', self.take_full_screenshot), PyTrayMenuItem('Скриншот области', self.selection_tool.start_selection), PyTrayMenuItem('Выход', self.on_quit))
        self.tray_icon = PyTrayIcon(APP_NAME, image, APP_NAME, menu=menu); threading.Thread(target=self.tray_icon.run, daemon=True).start()

if __name__ == "__main__":
    if IS_WINDOWS:
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except: pass
    
    root = tk.Tk()
    app = ScreenshotApp(root)
    root.mainloop()