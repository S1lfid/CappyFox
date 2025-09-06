# settings_manager.py
import os
import json
import sys
from constants import THEMES, APP_NAME

# Определяем IS_WINDOWS внутри модуля, чтобы он был независимым
IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import winreg

class SettingsManager:
    def __init__(self, app):
        self.app = app; self.settings_file = "settings.json"
        self.default_settings = { "save_directory": os.path.join(os.path.expanduser("~"), "Screenshots"), "image_format": "png", "theme": "Dark", "hide_on_screenshot": True, "hotkey_full_screen": "print screen", "hotkey_select_area": "ctrl+print screen", "autostart": False, "start_minimized": True }
        self.settings = self.load_settings()

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    s = json.load(f)
                    if 'theme' in s: s['theme'] = s['theme'].title()
                    return {**self.default_settings, **s}
        except (json.JSONDecodeError, IOError): pass
        return self.default_settings
        
    def save_settings(self):
        with open(self.settings_file, "w", encoding="utf-8") as f: json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def open_settings_window(self):
        import tkinter as tk # Импортируем tkinter только там, где он нужен
        win = tk.Toplevel(self.app.master); win.title("Настройки"); win.geometry("450x550"); win.resizable(False, False); win.transient(self.app.master); win.grab_set(); theme_cfg=THEMES[self.settings["theme"]]; win.config(bg=theme_cfg["bg"])
        lf_save=tk.LabelFrame(win, text="Сохранение",bg=theme_cfg["bg"],fg=theme_cfg["label_frame_fg"],padx=10,pady=10); lf_save.pack(pady=10,padx=15,fill="x"); lf_ui=tk.LabelFrame(win, text="Интерфейс",bg=theme_cfg["bg"],fg=theme_cfg["label_frame_fg"],padx=10,pady=10); lf_ui.pack(pady=10,padx=15,fill="x"); lf_sys=tk.LabelFrame(win, text="Система",bg=theme_cfg["bg"],fg=theme_cfg["label_frame_fg"],padx=10,pady=10); lf_sys.pack(pady=10,padx=15,fill="x"); lf_hk=tk.LabelFrame(win, text="Горячие клавиши",bg=theme_cfg["bg"],fg=theme_cfg["label_frame_fg"],padx=10,pady=10); lf_hk.pack(pady=10,padx=15,fill="x")
        tk.Label(lf_save,text="Папка:",bg=theme_cfg["bg"],fg=theme_cfg["fg"]).grid(row=0,column=0,sticky="w",pady=2); self.save_dir_entry=tk.Entry(lf_save,bg=theme_cfg["list_bg"],fg=theme_cfg["list_fg"],insertbackground=theme_cfg["fg"]); self.save_dir_entry.insert(0,self.settings["save_directory"]); self.save_dir_entry.grid(row=0,column=1,sticky="ew",padx=5); tk.Button(lf_save,text="...",command=self._browse_save_directory,bg=theme_cfg["button_bg"],fg=theme_cfg["button_fg"]).grid(row=0,column=2); lf_save.columnconfigure(1,weight=1)
        tk.Label(lf_ui,text="Тема:",bg=theme_cfg["bg"],fg=theme_cfg["fg"]).grid(row=0,column=0,sticky="w",pady=2); self.theme_var=tk.StringVar(value=self.settings["theme"]); theme_menu=tk.OptionMenu(lf_ui,self.theme_var,*THEMES.keys()); theme_menu.config(bg=theme_cfg["button_bg"],fg=theme_cfg["button_fg"],activebackground=theme_cfg["button_bg"],activeforeground=theme_cfg["button_fg"],highlightthickness=0); theme_menu["menu"].config(bg=theme_cfg["button_bg"],fg=theme_cfg["button_fg"]); theme_menu.grid(row=0,column=1,sticky="ew"); lf_ui.columnconfigure(1,weight=1)
        self.autostart_var=tk.BooleanVar(value=self.settings["autostart"]); tk.Checkbutton(lf_sys,text="Запускать при включении компьютера",var=self.autostart_var,bg=theme_cfg["bg"],fg=theme_cfg["fg"],selectcolor=theme_cfg["control_bg"],activebackground=theme_cfg["bg"]).pack(anchor="w"); self.start_minimized_var=tk.BooleanVar(value=self.settings["start_minimized"]); tk.Checkbutton(lf_sys,text="Запускать свернутым в трей",var=self.start_minimized_var,bg=theme_cfg["bg"],fg=theme_cfg["fg"],selectcolor=theme_cfg["control_bg"],activebackground=theme_cfg["bg"]).pack(anchor="w"); self.hide_on_screenshot_var=tk.BooleanVar(value=self.settings["hide_on_screenshot"]); tk.Checkbutton(lf_sys,text="Скрывать окно при создании скриншота",var=self.hide_on_screenshot_var,bg=theme_cfg["bg"],fg=theme_cfg["fg"],selectcolor=theme_cfg["control_bg"],activebackground=theme_cfg["bg"]).pack(anchor="w")
        tk.Label(lf_hk,text="Полный экран:",bg=theme_cfg["bg"],fg=theme_cfg["fg"]).grid(row=0,column=0,sticky="w",pady=2); self.hotkey_full_screen_entry=tk.Entry(lf_hk,bg=theme_cfg["list_bg"],fg=theme_cfg["list_fg"],insertbackground=theme_cfg["fg"]); self.hotkey_full_screen_entry.insert(0,self.settings["hotkey_full_screen"]); self.hotkey_full_screen_entry.grid(row=0,column=1,sticky="ew",padx=5)
        tk.Label(lf_hk,text="Выделение области:",bg=theme_cfg["bg"],fg=theme_cfg["fg"]).grid(row=1,column=0,sticky="w",pady=2); self.hotkey_select_area_entry=tk.Entry(lf_hk,bg=theme_cfg["list_bg"],fg=theme_cfg["list_fg"],insertbackground=theme_cfg["fg"]); self.hotkey_select_area_entry.insert(0,self.settings["hotkey_select_area"]); self.hotkey_select_area_entry.grid(row=1,column=1,sticky="ew",padx=5); lf_hk.columnconfigure(1,weight=1)
        btn_frame=tk.Frame(win,bg=theme_cfg["bg"]); btn_frame.pack(side="bottom",pady=15); tk.Button(btn_frame,text="Сохранить",command=lambda:self._save_and_close(win),bg=theme_cfg["button_bg"],fg=theme_cfg["button_fg"],width=12).pack(side="left",padx=5); tk.Button(btn_frame,text="Отмена",command=win.destroy,bg=theme_cfg["button_bg"],fg=theme_cfg["button_fg"],width=12).pack(side="left",padx=5)
    def _browse_save_directory(self):
        from tkinter import filedialog
        new_dir=filedialog.askdirectory(initialdir=self.save_dir_entry.get());
        if new_dir: self.save_dir_entry.delete(0,tk.END); self.save_dir_entry.insert(0,new_dir)
    def _save_and_close(self, window):
        self.settings.update({"save_directory":self.save_dir_entry.get(), "theme":self.theme_var.get(), "hide_on_screenshot":self.hide_on_screenshot_var.get(), "hotkey_full_screen":self.hotkey_full_screen_entry.get().lower(), "hotkey_select_area":self.hotkey_select_area_entry.get().lower(), "autostart":self.autostart_var.get(), "start_minimized":self.start_minimized_var.get()})
        if IS_WINDOWS: self.manage_autostart()
        self.save_settings()
        self.app.apply_theme(self.settings["theme"]); self.app.screenshot_dir=self.settings["save_directory"]; os.makedirs(self.app.screenshot_dir,exist_ok=True); self.app.load_screenshots(); self.app.rehook_hotkeys(); window.destroy()
    def manage_autostart(self):
        key_path=r"Software\Microsoft\Windows\CurrentVersion\Run"; script_path=os.path.abspath(sys.argv[0]); exe_path=f'"{sys.executable}" "{script_path}"';
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
                if self.settings["autostart"]: winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
                else:
                    try: winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError: pass
        except Exception: pass