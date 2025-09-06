# main.py
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import datetime
import threading
import sys
import io
import shutil
import base64

# --- Локальные импорты ---
from constants import APP_NAME, THEMES
from settings_manager import SettingsManager
from selection import SimpleSelection
from assets import ICON_BASE64

# --- Сторонние библиотеки ---
from pystray import Icon as PyTrayIcon, MenuItem as PyTrayMenuItem
import keyboard
from pyzbar.pyzbar import decode as qr_decode

# --- Импорты для Windows ---
IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import win32clipboard, winreg

class ScreenshotApp:
    def __init__(self, master):
        self.master = master
        master.app = self
        self.settings_manager = SettingsManager(self)
        
        self.app_icon_pil = None # PIL Image для трея
        self.app_icon_tk = None  # tk.PhotoImage для окна
        self._load_app_icon() # Сначала загружаем иконки

        if self.app_icon_tk:
            master.iconphoto(True, self.app_icon_tk)
        
        master.title(APP_NAME)
        master.geometry("950x650")
        master.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.screenshot_dir = self.settings_manager.settings["save_directory"]
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        self.tray_icon = None; self.full_screen_hotkey=None; self.area_hotkey=None
        self.current_image = None; self.current_image_path = None
        self.selection_tool = SimpleSelection(self)
        
        self.setup_ui()
        self._setup_tray_icon()
        self.rehook_hotkeys()
        self.apply_theme(self.settings_manager.settings["theme"])
        self.load_screenshots()
        
        if self.settings_manager.settings["start_minimized"]:
            master.withdraw()

    def _load_app_icon(self):
        # *** ГЛАВНОЕ И ОКОНЧАТЕЛЬНОЕ ИСПРАВЛЕНИЕ ОШИБКИ ИКОНКИ ***
        try:
            icon_data = base64.b64decode(ICON_BASE64)
            
            # 1. Создаем ОРИГИНАЛЬНЫЙ PIL.Image. Он будет использоваться ТОЛЬКО для pystray.
            self.app_icon_pil = Image.open(io.BytesIO(icon_data))
            
            # 2. Создаем PhotoImage из ОТДЕЛЬНОЙ КОПИИ для Tkinter, чтобы не "портить" оригинал.
            self.app_icon_tk = ImageTk.PhotoImage(self.app_icon_pil.copy())
            
        except Exception as e:
            print(f"Не удалось загрузить иконку приложения: {e}")
            self.app_icon_pil = None
            self.app_icon_tk = None

    def setup_ui(self):
        self.control_frame=tk.Frame(self.master); self.control_frame.pack(side="top",fill="x",padx=10,pady=5); tk.Button(self.control_frame,text="Скриншот экрана",command=self.take_full_screenshot).pack(side="left",padx=2); tk.Button(self.control_frame,text="Скриншот области",command=self.selection_tool.start_selection).pack(side="left",padx=2); tk.Button(self.control_frame,text="Настройки",command=self.settings_manager.open_settings_window).pack(side="right",padx=2); tk.Button(self.control_frame,text="Обновить",command=self.load_screenshots).pack(side="right",padx=2); self.main_frame=tk.Frame(self.master); self.main_frame.pack(fill="both",expand=True,padx=10,pady=10); self.left_frame=tk.Frame(self.main_frame,width=320); self.left_frame.pack(side="left",fill="y",padx=(0,10)); self.left_frame.pack_propagate(False); self.list_label=tk.Label(self.left_frame,text="Сохраненные скриншоты"); self.list_label.pack(pady=(0,5)); list_frame=tk.Frame(self.left_frame); list_frame.pack(fill="both",expand=True); scrollbar=tk.Scrollbar(list_frame); scrollbar.pack(side="right",fill="y"); self.screenshot_listbox=tk.Listbox(list_frame,yscrollcommand=scrollbar.set,selectmode=tk.EXTENDED,exportselection=False); self.screenshot_listbox.pack(fill="both",expand=True); scrollbar.config(command=self.screenshot_listbox.yview); self.screenshot_listbox.bind("<<ListboxSelect>>", self.on_screenshot_select); actions_frame=tk.Frame(self.left_frame); actions_frame.pack(side="bottom",fill="x",pady=(10,0)); tk.Button(actions_frame,text="Экспорт",command=self.export_selected).pack(side="left",expand=True,fill="x",padx=2); tk.Button(actions_frame,text="Удалить",command=self.delete_selected).pack(side="left",expand=True,fill="x",padx=2); self.right_frame=tk.Frame(self.main_frame); self.right_frame.pack(side="right",fill="both",expand=True); self.image_display_frame=tk.Frame(self.right_frame,relief="sunken",bd=1); self.image_display_frame.pack(fill="both",expand=True); self.image_canvas=tk.Canvas(self.image_display_frame,highlightthickness=0); self.image_canvas.pack(fill="both",expand=True); self.image_canvas.bind("<Configure>", self.resize_image_event); self.info_panel=tk.Frame(self.right_frame); self.info_panel.pack(fill="x",pady=(5,0)); self.info_label=tk.Label(self.info_panel,text="Выберите файл для просмотра",justify="left"); self.info_label.pack(anchor="w")

    def apply_theme(self, theme_name):
        theme=THEMES.get(theme_name,THEMES["Dark"]); self.master.config(bg=theme["bg"]); frames = [self.control_frame,self.main_frame,self.left_frame,self.right_frame,self.info_panel] + [child for child in self.left_frame.winfo_children() if isinstance(child, tk.Frame)];
        for frame in frames: frame.config(bg=theme["bg"])
        buttons = [widget for widget in self.control_frame.winfo_children() if isinstance(widget,tk.Button)]+[widget for widget in self.left_frame.winfo_children()[-1].winfo_children() if isinstance(widget, tk.Button)];
        for btn in buttons: btn.config(bg=theme["button_bg"],fg=theme["button_fg"],relief="flat",padx=10,pady=3,font=("Arial",9),highlightthickness=0)
        self.list_label.config(bg=theme["bg"],fg=theme["fg"]); self.info_label.config(bg=theme["bg"],fg=theme["fg"]); self.image_display_frame.config(bg=theme["preview_bg"],highlightbackground=theme["border_color"]); self.image_canvas.config(bg=theme["preview_bg"]); self.screenshot_listbox.config(bg=theme["list_bg"],fg=theme["list_fg"],selectbackground=theme["select_bg"],selectforeground=theme["select_fg"],highlightthickness=0,bd=0)

    def process_selected_area(self, image, action):
        self.master.deiconify()
        if not image or action == "cancel": return
        actions={"save":(self.save_screenshot,"Скриншот сохранен"), "copy":(self.copy_image_to_clipboard,"Скопировано в буфер"), "scan_qr":(self.scan_qr_code,None)}
        if action in actions: func,msg=actions[action]; func(image); msg and self.show_toast(msg)

    def on_screenshot_select(self, event):
        indices=self.screenshot_listbox.curselection();
        if not indices: self._clear_preview(); return
        filepath=self.screenshot_files[indices[-1]]; self.current_image_path=filepath
        try: self.current_image=Image.open(filepath); self.display_image(); self.info_label.config(text=f"{os.path.basename(filepath)} | {self.current_image.width}x{self.current_image.height} | {os.path.getsize(filepath)/1024:.1f} KB")
        except: self.info_label.config(text="Не удалось открыть файл"); self._clear_preview()
        
    def show_toast(self, message):
        toast=tk.Toplevel(self.master); toast.overrideredirect(True); toast.attributes("-alpha",0.0); toast.geometry(f"+{self.master.winfo_x()+self.master.winfo_width()-250}+{self.master.winfo_y()+self.master.winfo_height()-70}"); tk.Label(toast,text=message,bg="#111",fg="white",padx=20,pady=10).pack(); self.fade_in(toast); self.master.after(2000, lambda: self.fade_out(toast))
    
    def fade_in(self, widget, alpha=0.0):
        if alpha<0.9: alpha+=0.05; widget.attributes("-alpha",alpha); self.master.after(15,lambda: self.fade_in(widget,alpha))
        
    def fade_out(self, widget, alpha=0.9):
        if alpha>0.0: alpha-=0.05; widget.attributes("-alpha",alpha); self.master.after(15,lambda: self.fade_out(widget,alpha))
        else: widget.destroy()
        
    def hide_window(self): self.master.withdraw(); self.show_toast("Приложение свернуто в трей")
    def show_window(self): self.master.deiconify(); self.master.focus_force()
    def on_quit(self): self.rehook_hotkeys(True); self.tray_icon.stop(); self.master.destroy()
    def take_full_screenshot(self):
        delay=150 if self.settings_manager.settings["hide_on_screenshot"] else 1; (self.master.withdraw() if delay > 1 else None); self.master.after(delay, self._capture_full)
        
    def _capture_full(self): s=ImageGrab.grab(all_screens=True); self.save_screenshot(s); self.show_toast("Скриншот экрана сохранен"); self.master.deiconify()
    def rehook_hotkeys(self, unhook_only=False):
        if hasattr(self,'full_screen_hotkey') and self.full_screen_hotkey: keyboard.remove_hotkey(self.full_screen_hotkey)
        if hasattr(self,'area_hotkey') and self.area_hotkey: keyboard.remove_hotkey(self.area_hotkey)
        if unhook_only: return
        s=self.settings_manager.settings
        try: self.full_screen_hotkey=keyboard.add_hotkey(s["hotkey_full_screen"], self.take_full_screenshot)
        except Exception as e: print(f"Не удалось назначить клавишу '{s['hotkey_full_screen']}': {e}")
        try: self.area_hotkey=keyboard.add_hotkey(s["hotkey_select_area"], self.selection_tool.start_selection)
        except Exception as e: print(f"Не удалось назначить клавишу '{s['hotkey_select_area']}': {e}")
        
    def save_screenshot(self, image): f=f"screenshot_{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}.png"; p=os.path.join(self.screenshot_dir,f); image.convert("RGB").save(p); self.load_screenshots()
    def load_screenshots(self):
        self.screenshot_listbox.delete(0,tk.END); self.screenshot_files=[];
        try: paths=[os.path.join(self.screenshot_dir,f) for f in os.listdir(self.screenshot_dir) if f.lower().endswith(('.png','.jpg','.jpeg','.bmp'))]; paths.sort(key=os.path.getmtime,reverse=True); self.screenshot_files=paths; [self.screenshot_listbox.insert(tk.END, os.path.basename(p)) for p in self.screenshot_files]
        except FileNotFoundError: os.makedirs(self.screenshot_dir, exist_ok=True)
        self._clear_preview()

    def display_image(self):
        if not self.current_image: return;
        w,h=self.image_canvas.winfo_width(),self.image_canvas.winfo_height();
        if w<10 or h<10: self.master.after(50, self.display_image); return
        img=self.current_image.copy(); img.thumbnail((w,h), Image.Resampling.LANCZOS); self.tk_photo=ImageTk.PhotoImage(img); self.image_canvas.delete("all"); self.image_canvas.create_image(w/2,h/2,anchor="center",image=self.tk_photo)
    
    def resize_image_event(self,e): self.display_image()
    def _clear_preview(self): self.current_image=None; self.current_image_path=None; self.image_canvas.delete("all"); self.info_label.config(text="Выберите файл для просмотра")
    def delete_selected(self):
        indices = self.screenshot_listbox.curselection();
        if not indices: return
        files_to_delete = [self.screenshot_files[i] for i in indices];
        if messagebox.askyesno("Удаление", f"Удалить {len(indices)} выбранных файлов?"):
            if self.current_image_path in files_to_delete: self._clear_preview()
            for f in files_to_delete:
                try: os.remove(f)
                except Exception as e: print(f"Не удалось удалить {f}: {e}")
            self.load_screenshots()
            
    def export_selected(self):
        indices = self.screenshot_listbox.curselection();
        if not indices: return
        d=filedialog.askdirectory(title="Выберите папку для экспорта");
        if d: count=sum(1 for i in indices if shutil.copy(self.screenshot_files[i], d)); self.show_toast(f"Экспортировано {count} файлов")
        
    def copy_image_to_clipboard(self, image):
        if not IS_WINDOWS: return self.show_toast("Копирование доступно только в Windows")
        output = io.BytesIO(); image.convert("RGB").save(output, "BMP"); data=output.getvalue()[14:]; output.close()
        try: win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data); win32clipboard.CloseClipboard()
        except Exception as e: self.show_toast(f"Ошибка буфера обмена: {e}")
        
    def scan_qr_code(self, image):
        decoded=qr_decode(image);
        if not decoded: messagebox.showinfo("QR Сканнер","QR-коды не найдены",parent=self.master); return
        result = "\n".join([o.data.decode("utf-8") for o in decoded]); win = tk.Toplevel(self.master); win.title("Результат сканирования"); win.transient(self.master); win.grab_set(); tk.Label(win, text="Обнаруженные данные:").pack(padx=10, pady=(10,5)); text_widget=tk.Text(win, height=5, width=60); text_widget.pack(padx=10); text_widget.insert(tk.END, result);
        def copy_and_close(): self.master.clipboard_clear(); self.master.clipboard_append(result); win.destroy()
        tk.Button(win, text="Копировать в буфер и закрыть", command=copy_and_close).pack(pady=10)
    
    def _setup_tray_icon(self):
        image = self.app_icon_pil if self.app_icon_pil else Image.new('RGB', (64, 64), 'black')
        menu=(PyTrayMenuItem('Показать', self.show_window), 
              PyTrayMenuItem('Скриншот экрана', self.take_full_screenshot), 
              PyTrayMenuItem('Скриншот области', self.selection_tool.start_selection), 
              PyTrayMenuItem('Выход', self.on_quit));
        
        self.tray_icon = PyTrayIcon(APP_NAME, image, menu=menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenshotApp(root)
    root.mainloop()