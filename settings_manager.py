# settings_manager.py
import tkinter as tk
from tkinter import ttk, filedialog
import os
import json
import sys
from constants import THEMES, APP_NAME

# NEW: Import Animator and math for the new widget
from helpers import Animator
import math

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import winreg

# --- NEW WIDGET: A modern, animated Segmented Control for theme selection ---
class SegmentedControl(tk.Frame):
    def __init__(self, parent, variable, options, theme_config, **kwargs):
        super().__init__(parent, bg=theme_config["control_bg"], **kwargs)
        self.variable = variable
        self.options = list(options)
        self.theme_config = theme_config
        
        self.config(height=34, highlightbackground=theme_config["border_color"], highlightthickness=1)
        
        self.canvas = tk.Canvas(self, bg=theme_config["control_bg"], highlightthickness=0, bd=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.labels = []
        for option_text in self.options:
            label = tk.Label(self, text=option_text, bg=theme_config["control_bg"], 
                             fg=theme_config["fg"], font=("Arial", 10))
            label.bind("<Button-1>", lambda e, opt=option_text: self._on_click(opt))
            label.bind("<Enter>", lambda e, lbl=label: lbl.config(fg=self.theme_config["select_bg"]))
            label.bind("<Leave>", lambda e, lbl=label: self._update_label_colors())
            self.labels.append(label)

        self.variable.trace_add("write", self._on_var_change)
        
        self.after(1, self._initial_layout) # Defer layout until widget has a size
        self.current_selector_x = 0
        self.current_selector_width = 0

    def _initial_layout(self):
        """Places labels and draws the initial selector."""
        width = self.winfo_width()
        option_width = width / len(self.options)
        
        for i, label in enumerate(self.labels):
            label.place(relx=i / len(self.options), rely=0, relwidth=1 / len(self.options), relheight=1)

        try:
            current_index = self.options.index(self.variable.get())
        except ValueError:
            current_index = 0
            
        self.current_selector_x = current_index * option_width
        self.current_selector_width = option_width
        self._draw_selector()
        self._update_label_colors()
    
    def _on_click(self, option):
        self.variable.set(option)

    def _on_var_change(self, *args):
        self._animate_selector()
        self._update_label_colors()
        
    def _update_label_colors(self):
        """Update text color based on the current selection."""
        current_value = self.variable.get()
        for label in self.labels:
            if label.cget("text") == current_value:
                label.config(fg=self.theme_config["select_fg"])
            else:
                label.config(fg=self.theme_config["fg"])
                
    def _draw_selector(self, x=None, width=None):
        """Draws the rounded rectangle selector on the canvas."""
        self.canvas.delete("all")
        if x is None: x = self.current_selector_x
        if width is None: width = self.current_selector_width
        
        padding = 3
        r = (self.winfo_height() - padding * 2) / 2 # Corner radius
        
        points = [
            x + r + padding, padding, x + width - r - padding, padding,
            x + width - padding, padding, x + width - padding, padding + r,
            x + width - padding, self.winfo_height() - r - padding,
            x + width - padding, self.winfo_height() - padding, x + width - r - padding, self.winfo_height() - padding,
            x + r + padding, self.winfo_height() - padding,
            x + padding, self.winfo_height() - padding, x + padding, self.winfo_height() - r,
            x + padding, padding + r, x + padding, padding, x + r + padding, padding
        ]
        self.canvas.create_polygon(points, fill=self.theme_config["select_bg"], smooth=True)

    def _animate_selector(self):
        """Starts the animation to move the selector."""
        try:
            target_index = self.options.index(self.variable.get())
        except ValueError:
            return

        option_width = self.winfo_width() / len(self.options)
        target_x = target_index * option_width
        start_x = self.current_selector_x

        def update(progress):
            self.current_selector_x = start_x + (target_x - start_x) * progress
            self._draw_selector()

        anim = Animator(duration=0.25, update_callback=update)
        anim.start(self)

# --- THE REST OF THE FILE ---
# (I'm using the version with standard, fixed checkbuttons as requested before)

class SettingsManager:
    def __init__(self, app):
        self.app = app
        self.settings_file = "settings.json"
        self.default_settings = {
            "save_directory": os.path.join(os.path.expanduser("~"), "Screenshots"),
            "image_format": "png",
            "theme": "Dark",
            "hide_on_screenshot": True,
            "hotkey_full_screen": "print screen",
            "hotkey_select_area": "ctrl+print screen",
            "autostart": False,
            "start_minimized": True,
            "enable_catbox_upload": True,
            "open_window_after_shot": True
        }
        self.settings = self.load_settings()

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    s = json.load(f)
                    if 'theme' in s: s['theme'] = s['theme'].title()
                    return {**self.default_settings, **s}
        except (json.JSONDecodeError, IOError):
            pass
        return self.default_settings.copy()
        
    def save_settings(self):
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def open_settings_window(self):
        win = tk.Toplevel(self.app.master)
        win.title("Настройки")
        win.geometry("500x550")
        win.resizable(False, False)
        win.transient(self.app.master)
        win.grab_set()
        
        current_theme_name = self.settings["theme"]
        theme_cfg = THEMES[current_theme_name]
        win.config(bg=theme_cfg["bg"])

        style = ttk.Style(win)
        style.theme_use('clam')
        style.configure('TNotebook', background=theme_cfg["bg"], borderwidth=0)
        style.configure('TNotebook.Tab', background=theme_cfg["control_bg"], foreground=theme_cfg["fg"], padding=[10, 5], font=('Arial', 10))
        style.map('TNotebook.Tab', background=[('selected', theme_cfg["bg"])])
        style.configure('Settings.TFrame', background=theme_cfg["bg"])
        style.configure('Settings.TLabel', background=theme_cfg["bg"], foreground=theme_cfg["fg"], font=('Arial', 10))
        
        style.configure('Settings.TCheckbutton', 
            background=theme_cfg["bg"], foreground=theme_cfg["fg"], font=('Arial', 10), padding=(0, 4)
        )
        style.map('Settings.TCheckbutton',
            indicatorbackground=[('selected', theme_cfg["select_bg"]), ('!selected', theme_cfg["control_bg"])],
            background=[('active', theme_cfg["bg"])]
        )

        style.configure('Settings.TLabelframe', background=theme_cfg["bg"], bordercolor=theme_cfg["border_color"], font=('Arial', 10))
        style.configure('Settings.TLabelframe.Label', background=theme_cfg["bg"], foreground=theme_cfg["label_frame_fg"])
        style.configure('Settings.TButton', background=theme_cfg["button_bg"], foreground=theme_cfg["button_fg"], font=('Arial', 10), padding=5)
        style.map('Settings.TButton', background=[('active', theme_cfg["select_bg"])])
        style.configure('Settings.TEntry', 
            fieldbackground=theme_cfg["list_bg"], foreground=theme_cfg["list_fg"],
            insertcolor=theme_cfg["list_fg"], background=theme_cfg['control_bg'],
            borderwidth=1, relief='flat'
        )

        notebook = ttk.Notebook(win, style='TNotebook'); notebook.pack(expand=True, fill="both", padx=10, pady=10)

        tab_main = ttk.Frame(notebook, style='Settings.TFrame', padding=15)
        tab_ui = ttk.Frame(notebook, style='Settings.TFrame', padding=15)
        tab_hotkeys = ttk.Frame(notebook, style='Settings.TFrame', padding=15)
        notebook.add(tab_main, text="  Основные  ")
        notebook.add(tab_ui, text="  Внешний вид  ")
        notebook.add(tab_hotkeys, text="  Горячие клавиши  ")

        lf_save = ttk.LabelFrame(tab_main, text="Папка для сохранения", style="Settings.TLabelframe", padding=10); lf_save.pack(pady=10, fill="x")
        dir_frame = ttk.Frame(lf_save, style='Settings.TFrame'); dir_frame.pack(fill='x', expand=True)
        self.save_dir_entry = ttk.Entry(dir_frame, style='Settings.TEntry')
        self.save_dir_entry.insert(0, self.settings["save_directory"]); self.save_dir_entry.pack(side='left', fill='x', expand=True, ipady=4)
        ttk.Button(dir_frame, text="...", command=self._browse_save_directory, width=3, style='Settings.TButton').pack(side='left', padx=(5,0))

        lf_system = ttk.LabelFrame(tab_main, text="Системные опции", style="Settings.TLabelframe", padding=10); lf_system.pack(pady=10, fill="x")
        
        self.autostart_var=tk.BooleanVar(value=self.settings.get("autostart", False))
        ttk.Checkbutton(lf_system, text="Запускать при включении компьютера", var=self.autostart_var, style="Settings.TCheckbutton").pack(anchor="w", pady=2)
        
        self.start_minimized_var=tk.BooleanVar(value=self.settings.get("start_minimized", True))
        ttk.Checkbutton(lf_system,text="Запускать свернутым в трей", var=self.start_minimized_var, style="Settings.TCheckbutton").pack(anchor="w", pady=2)
        
        self.hide_on_screenshot_var=tk.BooleanVar(value=self.settings.get("hide_on_screenshot", True))
        ttk.Checkbutton(lf_system,text="Скрывать окно при создании скриншота", var=self.hide_on_screenshot_var, style="Settings.TCheckbutton").pack(anchor="w", pady=2)

        self.open_window_after_shot_var = tk.BooleanVar(value=self.settings.get("open_window_after_shot", True))
        ttk.Checkbutton(lf_system, text="Открывать окно после скриншота", var=self.open_window_after_shot_var, style="Settings.TCheckbutton").pack(anchor="w", pady=2)
        
        self.enable_catbox_upload_var = tk.BooleanVar(value=self.settings.get("enable_catbox_upload", True))
        ttk.Checkbutton(lf_system, text="Включить загрузку на catbox.moe", var=self.enable_catbox_upload_var, style="Settings.TCheckbutton").pack(anchor="w", pady=2)
        
        lf_theme = ttk.LabelFrame(tab_ui, text="Тема оформления", style="Settings.TLabelframe", padding=10); lf_theme.pack(pady=10, fill="x")
        
        # --- MODIFIED: The old radio buttons are replaced with our new widget ---
        self.theme_var = tk.StringVar(value=self.settings["theme"])
        SegmentedControl(lf_theme, variable=self.theme_var, options=THEMES.keys(), theme_config=theme_cfg).pack(fill="x", padx=5, pady=5)
        
        lf_hk = ttk.LabelFrame(tab_hotkeys, text="Назначение клавиш", style="Settings.TLabelframe", padding=10); lf_hk.pack(pady=10, fill="x")
        hk_full_frame = ttk.Frame(lf_hk, style='Settings.TFrame'); hk_full_frame.pack(fill='x', expand=True, padx=5, pady=5)
        ttk.Label(hk_full_frame, text="Полный экран:", style='Settings.TLabel').pack(side='left', padx=(0,10))
        self.hotkey_full_screen_entry = ttk.Entry(hk_full_frame, style='Settings.TEntry')
        self.hotkey_full_screen_entry.insert(0, self.settings["hotkey_full_screen"]); self.hotkey_full_screen_entry.pack(side='left', fill='x', expand=True, ipady=4)
        hk_area_frame = ttk.Frame(lf_hk, style='Settings.TFrame'); hk_area_frame.pack(fill='x', expand=True, padx=5, pady=(5,10))
        ttk.Label(hk_area_frame, text="Выделение области:", style='Settings.TLabel', width=18).pack(side='left', padx=(0,10))
        self.hotkey_select_area_entry = ttk.Entry(hk_area_frame, style='Settings.TEntry')
        self.hotkey_select_area_entry.insert(0, self.settings["hotkey_select_area"]); self.hotkey_select_area_entry.pack(side='left', fill='x', expand=True, ipady=4)
        
        btn_frame = ttk.Frame(win, style='Settings.TFrame'); btn_frame.pack(side="bottom", pady=15)
        ttk.Button(btn_frame, text="Сохранить", command=lambda: self._save_and_close(win), style='Settings.TButton', width=12).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Отмена", command=win.destroy, style='Settings.TButton', width=12).pack(side="left", padx=5)

    def _on_theme_change(self, window_to_close):
        new_theme = self.theme_var.get()
        if self.settings['theme'] == new_theme:
            return
        self.settings['theme'] = new_theme
        window_to_close.destroy()
        self.open_settings_window()

    def _browse_save_directory(self):
        new_dir=filedialog.askdirectory(initialdir=self.save_dir_entry.get())
        if new_dir:
            self.save_dir_entry.delete(0, tk.END)
            self.save_dir_entry.insert(0, new_dir)
            
    def _save_and_close(self, window):
        new_theme = self.theme_var.get()
        self.settings.update({
            "save_directory": self.save_dir_entry.get(),
            "theme": new_theme,
            "hide_on_screenshot": self.hide_on_screenshot_var.get(),
            "hotkey_full_screen": self.hotkey_full_screen_entry.get().lower(),
            "hotkey_select_area": self.hotkey_select_area_entry.get().lower(),
            "autostart": self.autostart_var.get(),
            "start_minimized": self.start_minimized_var.get(),
            "enable_catbox_upload": self.enable_catbox_upload_var.get(),
            "open_window_after_shot": self.open_window_after_shot_var.get()
        })
        
        if IS_WINDOWS: self.manage_autostart()
        self.save_settings()
        
        if self.app.theme_name != new_theme:
            self.app.theme_name = new_theme
            self.app._load_all_icons()
            self.app.setup_ui() # Full UI rebuild for theme change
        else:
             # Partial rebuild needed if only settings changed
             self.app.setup_ui() 

        self.app.load_screenshots()
        self.app.rehook_hotkeys()
        
        window.destroy()
        
    def manage_autostart(self):
        if not IS_WINDOWS: return
        key_path=r"Software\Microsoft\Windows\CurrentVersion\Run"; script_path = os.path.realpath(sys.argv[0])
        exe_path = f'"{sys.executable}" "{script_path}"'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
                if self.settings["autostart"]: winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
                else:
                    try: winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError: pass
        except Exception as e:
            print(f"Ошибка при работе с реестром: {e}")