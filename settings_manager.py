# settings_manager.py
import tkinter as tk
from tkinter import ttk, filedialog
import os
import json
import sys
from constants import THEMES, APP_NAME

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import winreg

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
            "start_minimized": True
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
        win.geometry("500x520")
        win.resizable(False, False)
        win.transient(self.app.master)
        win.grab_set()
        
        # Используем текущую выбранную тему для отрисовки окна
        current_theme_name = self.settings["theme"]
        theme_cfg = THEMES[current_theme_name]
        win.config(bg=theme_cfg["bg"])

        style = ttk.Style(win)
        style.theme_use('clam')
        # ... (старые стили без изменений) ...
        style.configure('TNotebook', background=theme_cfg["bg"], borderwidth=0)
        style.configure('TNotebook.Tab', background=theme_cfg["control_bg"], foreground=theme_cfg["fg"], padding=[10, 5], font=('Arial', 10))
        style.map('TNotebook.Tab', background=[('selected', theme_cfg["bg"])])
        style.configure('Settings.TFrame', background=theme_cfg["bg"])
        style.configure('Settings.TLabel', background=theme_cfg["bg"], foreground=theme_cfg["fg"], font=('Arial', 10))
        style.configure('Settings.TCheckbutton', background=theme_cfg["bg"], foreground=theme_cfg["fg"], font=('Arial', 10))
        style.map('Settings.TCheckbutton', indicatorbackground=[('!active', theme_cfg["control_bg"])], background=[('active', theme_cfg["bg"])])
        style.configure('Settings.TLabelframe', background=theme_cfg["bg"], bordercolor=theme_cfg["border_color"], font=('Arial', 10))
        style.configure('Settings.TLabelframe.Label', background=theme_cfg["bg"], foreground=theme_cfg["label_frame_fg"])
        style.configure('Settings.TButton', background=theme_cfg["button_bg"], foreground=theme_cfg["button_fg"], font=('Arial', 10), padding=5)
        style.map('Settings.TButton', background=[('active', theme_cfg["select_bg"])])

        # --- ИЗМЕНЕНИЕ 1: Добавляем кастомный стиль для полей ввода ---
        style.configure('Settings.TEntry', 
            fieldbackground=theme_cfg["list_bg"], # Цвет фона самого поля
            foreground=theme_cfg["list_fg"],      # Цвет текста
            insertcolor=theme_cfg["list_fg"],     # Цвет курсора
            background=theme_cfg['control_bg'],   # Цвет фона рамки
            borderwidth=1,
            relief='flat'
        )

        notebook = ttk.Notebook(win, style='TNotebook'); notebook.pack(expand=True, fill="both", padx=10, pady=10)

        tab_main = ttk.Frame(notebook, style='Settings.TFrame', padding=15)
        tab_ui = ttk.Frame(notebook, style='Settings.TFrame', padding=15)
        tab_hotkeys = ttk.Frame(notebook, style='Settings.TFrame', padding=15)
        notebook.add(tab_main, text="  Основные  ")
        notebook.add(tab_ui, text="  Внешний вид  ")
        notebook.add(tab_hotkeys, text="  Горячие клавиши  ")

        # --- Содержимое "Основные" ---
        lf_save = ttk.LabelFrame(tab_main, text="Папка для сохранения", style="Settings.TLabelframe", padding=10); lf_save.pack(pady=10, fill="x")
        dir_frame = ttk.Frame(lf_save, style='Settings.TFrame'); dir_frame.pack(fill='x', expand=True)
        # --- Применяем наш новый стиль ---
        self.save_dir_entry = ttk.Entry(dir_frame, style='Settings.TEntry')
        self.save_dir_entry.insert(0, self.settings["save_directory"]); self.save_dir_entry.pack(side='left', fill='x', expand=True, ipady=4)
        ttk.Button(dir_frame, text="...", command=self._browse_save_directory, width=3, style='Settings.TButton').pack(side='left', padx=(5,0))

        lf_system = ttk.LabelFrame(tab_main, text="Системные опции", style="Settings.TLabelframe", padding=10); lf_system.pack(pady=10, fill="x")
        self.autostart_var=tk.BooleanVar(value=self.settings.get("autostart", False)); ttk.Checkbutton(lf_system, text="Запускать при включении компьютера", var=self.autostart_var, style="Settings.TCheckbutton").pack(anchor="w", pady=2)
        self.start_minimized_var=tk.BooleanVar(value=self.settings.get("start_minimized", True)); ttk.Checkbutton(lf_system,text="Запускать свернутым в трей", var=self.start_minimized_var, style="Settings.TCheckbutton").pack(anchor="w", pady=2)
        self.hide_on_screenshot_var=tk.BooleanVar(value=self.settings.get("hide_on_screenshot", True)); ttk.Checkbutton(lf_system,text="Скрывать окно при создании скриншота", var=self.hide_on_screenshot_var, style="Settings.TCheckbutton").pack(anchor="w", pady=2)
        
        # --- Содержимое "Внешний вид" ---
        lf_theme = ttk.LabelFrame(tab_ui, text="Тема оформления", style="Settings.TLabelframe", padding=10); lf_theme.pack(pady=10, fill="x")
        self.theme_var=tk.StringVar(value=self.settings["theme"])
        theme_frame = ttk.Frame(lf_theme, style='Settings.TFrame'); theme_frame.pack(pady=(10, 5))
        for theme_name in THEMES.keys():
            # --- ИЗМЕНЕНИЕ 2: Добавляем команду для мгновенного обновления ---
            rb = ttk.Radiobutton(theme_frame, text=theme_name, variable=self.theme_var, 
                                 value=theme_name, command=lambda: self._on_theme_change(win))
            rb.pack(side="left", padx=15)
            
        # --- Содержимое "Горячие клавиши" ---
        lf_hk = ttk.LabelFrame(tab_hotkeys, text="Назначение клавиш", style="Settings.TLabelframe", padding=10); lf_hk.pack(pady=10, fill="x")
        hk_full_frame = ttk.Frame(lf_hk, style='Settings.TFrame'); hk_full_frame.pack(fill='x', expand=True, padx=5, pady=5)
        ttk.Label(hk_full_frame, text="Полный экран:", style='Settings.TLabel').pack(side='left', padx=(0,10))
        # --- Применяем наш новый стиль ---
        self.hotkey_full_screen_entry = ttk.Entry(hk_full_frame, style='Settings.TEntry')
        self.hotkey_full_screen_entry.insert(0, self.settings["hotkey_full_screen"]); self.hotkey_full_screen_entry.pack(side='left', fill='x', expand=True, ipady=4)
        hk_area_frame = ttk.Frame(lf_hk, style='Settings.TFrame'); hk_area_frame.pack(fill='x', expand=True, padx=5, pady=(5,10))
        ttk.Label(hk_area_frame, text="Выделение области:", style='Settings.TLabel', width=18).pack(side='left', padx=(0,10))
        # --- Применяем наш новый стиль ---
        self.hotkey_select_area_entry = ttk.Entry(hk_area_frame, style='Settings.TEntry')
        self.hotkey_select_area_entry.insert(0, self.settings["hotkey_select_area"]); self.hotkey_select_area_entry.pack(side='left', fill='x', expand=True, ipady=4)
        
        btn_frame = ttk.Frame(win, style='Settings.TFrame'); btn_frame.pack(side="bottom", pady=15)
        ttk.Button(btn_frame, text="Сохранить", command=lambda: self._save_and_close(win), style='Settings.TButton', width=12).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Отмена", command=win.destroy, style='Settings.TButton', width=12).pack(side="left", padx=5)

    # --- ИЗМЕНЕНИЕ 3: Новый метод для перезапуска окна настроек ---
    def _on_theme_change(self, window_to_close):
        """Вызывается при смене темы для мгновенного обновления окна настроек."""
        new_theme = self.theme_var.get()
        # Если тема не изменилась, ничего не делаем
        if self.settings['theme'] == new_theme:
            return
        
        # Обновляем настройку темы в памяти
        self.settings['theme'] = new_theme
        
        # Закрываем текущее окно и сразу же открываем новое
        window_to_close.destroy()
        self.open_settings_window()

    def _browse_save_directory(self):
        new_dir=filedialog.askdirectory(initialdir=self.save_dir_entry.get())
        if new_dir:
            self.save_dir_entry.delete(0, tk.END)
            self.save_dir_entry.insert(0, new_dir)
            
    def _save_and_close(self, window):
        # Сохраняем все настройки из виджетов
        new_theme = self.theme_var.get()
        self.settings.update({
            "save_directory": self.save_dir_entry.get(),
            "theme": new_theme,
            "hide_on_screenshot": self.hide_on_screenshot_var.get(),
            "hotkey_full_screen": self.hotkey_full_screen_entry.get().lower(),
            "hotkey_select_area": self.hotkey_select_area_entry.get().lower(),
            "autostart": self.autostart_var.get(),
            "start_minimized": self.start_minimized_var.get()
        })
        
        if IS_WINDOWS: self.manage_autostart()
        self.save_settings()
        
        # Применяем изменения к главному приложению
        self.app.screenshot_dir=self.settings["save_directory"]
        os.makedirs(self.app.screenshot_dir, exist_ok=True, mode=0o777)
        # Если тема реально изменилась, перезагружаем UI главного окна
        if self.app.theme_name != new_theme:
            self.app.theme_name = new_theme
            self.app._load_all_icons()
            self.app.setup_ui() # Перерисовываем UI, чтобы подхватить новые иконки и стили

        self.app.load_screenshots()
        self.app.rehook_hotkeys()
        
        window.destroy()
        
    def manage_autostart(self):
        # ... (код этого метода без изменений) ...
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